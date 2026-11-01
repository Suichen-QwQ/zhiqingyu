import http.client
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
DATA = Path(TEMP.name)
STATIC = DATA / 'frontend'
(STATIC / 'assets').mkdir(parents=True)
(STATIC / 'index.html').write_text('index', encoding='utf-8')
(DATA / 'private.txt').write_text('private-test', encoding='utf-8')
(DATA / 'storage.json').write_text(json.dumps({'data': {'sessions': [{'msgs': ['private-test']}]}}))
os.environ.update({'ZQY_STATIC_DIR': str(STATIC), 'ZQY_STORAGE_FILE': str(DATA / 'storage.json'),
                   'ZQY_SETTINGS_FILE': str(DATA / 'settings.json'), 'ZQY_MEMORY_DIR': str(DATA / 'memory'),
                   'ZQY_RECALL_DIR': str(DATA / 'recall'), 'ZQY_MEMORY_FILE': str(DATA / 'memory.md'),
                   'ZQY_TTS_CACHE_DIR': str(DATA / 'tts'),
                   'DEEPSEEK_API_KEY': 'fake-review-key', 'DEEPSEEK_BASE_URL': 'http://127.0.0.1:19991'})
spec = importlib.util.spec_from_file_location('review_server', ROOT / 'backend-live' / 'chat_server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class SecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.port = cls.httpd.server_port
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()
        TEMP.cleanup()

    def setUp(self):
        settings = DATA / 'settings.json'
        if settings.exists():
            settings.unlink()
        (DATA / 'storage.json').write_text(json.dumps({'data': {'sessions': [{'msgs': ['private-test']}]}}))

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        conn.request(method, path, body=body, headers=headers or {})
        res = conn.getresponse()
        result = (res.status, dict(res.getheaders()), res.read())
        conn.close()
        return result

    def test_static_traversal_and_normal_resource(self):
        status, _, _ = self.request('GET', '/assets/%2e%2e/%2e%2e/private.txt')
        self.assertEqual(status, 404)
        self.assertEqual(self.request('GET', '/')[0], 200)

    def test_cross_origin_read_and_write_blocked(self):
        origin = {'Origin': 'https://attacker.example'}
        self.assertEqual(self.request('GET', '/api/storage', headers=origin)[0], 403)
        self.assertEqual(self.request('OPTIONS', '/api/storage', headers=origin)[0], 403)
        self.assertEqual(self.request('POST', '/api/storage', b'{}', origin)[0], 403)
        same = {'Origin': 'http://127.0.0.1:%s' % self.port}
        status, headers, body = self.request('GET', '/api/storage', headers=same)
        self.assertEqual(status, 200)
        self.assertIn(b'private-test', body)
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_probe_cannot_forward_existing_key_to_new_host(self):
        body = json.dumps({'base_url': 'http://127.0.0.1:19992'}).encode()
        status, _, _ = self.request('POST', '/api/settings/test', body, {'Content-Type': 'application/json'})
        self.assertEqual(status, 400)

    def test_stale_writes_are_rejected_without_losing_winner(self):
        status, _, body = self.request('GET', '/api/storage')
        revision = json.loads(body)['revision']
        def write(text, version):
            payload = {'expected_revision': version, 'data': {'sessions': [{'msgs': [text]}]}}
            return self.request('POST', '/api/storage', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
        first = write('first', revision)
        self.assertEqual(first[0], 200)
        second = write('stale', revision)
        self.assertEqual(second[0], 409)
        self.assertEqual(json.loads(second[2])['error_code'], 'storage_conflict')
        self.assertEqual(json.loads(self.request('GET', '/api/storage')[2])['data']['sessions'][0]['msgs'], ['first'])

    def test_simultaneous_clients_cannot_overwrite_each_other(self):
        from concurrent.futures import ThreadPoolExecutor
        revision = json.loads(self.request('GET', '/api/storage')[2])['revision']
        def write(value):
            payload = {'expected_revision': revision, 'data': {'sessions': [{'msgs': [value]}]}}
            return self.request('POST', '/api/storage', json.dumps(payload).encode(), {'Content-Type': 'application/json'})[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(write, ['a', 'b']))
        self.assertEqual(sorted(statuses), [200, 409])

    def test_clear_custom_key_does_not_reuse_server_key(self):
        server.save_model_settings({'base_url': 'https://custom.example/v1', 'api_key': 'fake-custom'})
        server.save_model_settings({'clear_key': True})
        self.assertEqual(server.model_settings()['base_url'], 'https://custom.example/v1')
        self.assertEqual(server.model_settings()['api_key'], '')
        self.assertEqual(server.model_chain()[0]['api_key'], '')

    def test_host_allowlist_and_proxy_headers(self):
        from unittest.mock import patch
        bad = {'Host': 'attacker.example', 'Origin': 'http://attacker.example'}
        self.assertEqual(self.request('GET', '/api/storage', headers=bad)[0], 403)
        spoof = {'Origin': 'https://127.0.0.1:%s' % self.port, 'X-Forwarded-Proto': 'https'}
        self.assertEqual(self.request('GET', '/api/storage', headers=spoof)[0], 403)
        with patch.object(server, 'ALLOWED_HOSTS', {'app.example'}), patch.object(server, 'TRUST_PROXY', True):
            headers = {'Host': 'app.example', 'Origin': 'https://app.example', 'X-Forwarded-Proto': 'https'}
            self.assertEqual(self.request('GET', '/api/storage', headers=headers)[0], 200)

    def test_chat_redirects_do_not_forward_credentials(self):
        from http.server import BaseHTTPRequestHandler, HTTPServer
        from urllib.error import HTTPError
        class Target(BaseHTTPRequestHandler):
            hits = 0
            def do_GET(self):
                Target.hits += 1
                self.send_response(200)
                self.end_headers()
            def log_message(self, *args):
                pass
        target = HTTPServer(('127.0.0.1', 0), Target)
        class Redirect(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(302)
                self.send_header('Location', 'http://127.0.0.1:%s/target' % target.server_port)
                self.end_headers()
            def log_message(self, *args):
                pass
        redirect = HTTPServer(('127.0.0.1', 0), Redirect)
        for instance in (target, redirect):
            threading.Thread(target=instance.serve_forever, daemon=True).start()
        try:
            candidate = {'base_url': 'http://127.0.0.1:%s' % redirect.server_port,
                         'api_key': 'fake-secret', 'model': 'm', 'reasoner_model': 'm', 'timeout': 3}
            with self.assertRaises(HTTPError):
                server._chat_one(candidate, [{'role': 'user', 'content': 'hi'}], False)
            with self.assertRaises(HTTPError):
                list(server._chat_stream_one(candidate, [{'role': 'user', 'content': 'hi'}], None, {}))
            self.assertEqual(Target.hits, 0)
        finally:
            for instance in (redirect, target):
                instance.shutdown()
                instance.server_close()

    def test_archive_default_import_does_not_overwrite_concurrent_save(self):
        import io
        import zipfile
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        (DATA / 'storage.json').unlink()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('storage.json', json.dumps({'sessions': [{'msgs': ['archive']}]}))
        checked, started, finished = threading.Event(), threading.Event(), threading.Event()
        real_read = server.read_storage
        def paused_read():
            result = real_read()
            checked.set()
            self.assertTrue(started.wait(3))
            self.assertFalse(finished.wait(0.2))
            return result
        def write():
            self.assertTrue(checked.wait(3))
            started.set()
            server.put_storage({'sessions': [{'msgs': ['live']}]})
            finished.set()
        with ThreadPoolExecutor(max_workers=2) as pool:
            with patch.object(server, 'read_storage', side_effect=paused_read):
                writer = pool.submit(write)
                imported = server.archive_import(buffer.getvalue(), False)
                writer.result(timeout=4)
        self.assertEqual(imported['storage'], 'restored')
        self.assertEqual(real_read()['data']['sessions'][0]['msgs'], ['live'])

    def test_service_without_model_key_starts_and_serves_settings(self):
        import subprocess
        import sys
        import socket
        import time
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        settings = DATA / 'unconfigured-settings.json'
        settings.write_text(json.dumps({'base_url': 'https://custom.example/v1', 'api_key': ''}))
        env = dict(os.environ, ZQY_SETTINGS_FILE=str(settings), ZQY_LISTEN_HOST='127.0.0.1', ZQY_LISTEN_PORT=str(port))
        child = subprocess.Popen([sys.executable, str(ROOT / 'backend-live/chat_server.py')], env=env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while True:
                self.assertIsNone(child.poll(), 'unconfigured server exited')
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                try:
                    conn.request('GET', '/api/settings')
                    response = conn.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertFalse(json.loads(response.read())['has_key'])
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
                finally:
                    conn.close()
        finally:
            child.terminate()
            child.wait(timeout=4)

    def test_missing_key_fails_before_model_network_request(self):
        from unittest.mock import patch
        candidate = {'api_key': ''}
        with patch.object(server.urllib.request, 'build_opener', side_effect=AssertionError('network called')):
            with self.assertRaises(server.LLMError):
                server._chat_one(candidate, [], False)
            with self.assertRaises(server.LLMError):
                list(server._chat_stream_one(candidate, [], None, {}))

    def test_settings_partial_update_preserves_fallback_keys(self):
        server.save_model_settings({'fallbacks': [{'base_url': server.BASE_URL, 'model': 'backup', 'api_key': 'fake-backup'}]})
        server.save_model_settings({'timeout': 30})
        self.assertEqual(server.saved_fallbacks()[0]['api_key'], 'fake-backup')
        server.save_model_settings({'clear_key': True})
        self.assertEqual(server.saved_fallbacks()[0]['model'], 'backup')
        server.save_model_settings({'fallbacks': []})
        self.assertEqual(server.saved_fallbacks(), [])

    def test_settings_file_stays_valid_until_atomic_replacement(self):
        from unittest.mock import patch
        server.save_model_settings({'base_url': 'https://custom.example/v1', 'api_key': 'fake-custom'})
        original = (DATA / 'settings.json').read_bytes()
        dump = server.json_dump
        def while_writing(*args, **kwargs):
            self.assertEqual((DATA / 'settings.json').read_bytes(), original)
            self.assertEqual(server.model_settings()['base_url'], 'https://custom.example/v1')
            return dump(*args, **kwargs)
        with patch.object(server, 'json_dump', side_effect=while_writing):
            self.assertTrue(server.save_model_settings({'timeout': 31}))
        self.assertEqual(server.model_settings()['timeout'], 31)
        self.assertEqual(list(DATA.glob('.zqy-settings-*.tmp')), [])
        with patch.object(server.os, 'replace', side_effect=OSError('test failure')):
            self.assertIsNone(server.save_model_settings({'timeout': 32}))
        self.assertEqual(server.model_settings()['timeout'], 31)
        self.assertEqual(list(DATA.glob('.zqy-settings-*.tmp')), [])

    def test_concurrent_partial_settings_updates_are_serialized(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(server.save_model_settings, payload) for payload in
                       ({'timeout': 37}, {'model': 'updated-model'})]
            self.assertTrue(all(f.result() for f in futures))
        self.assertEqual(server.model_settings()['timeout'], 37)
        self.assertEqual(server.model_settings()['model'], 'updated-model')

    def chunk_request(self, raw):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        try:
            conn.putrequest('POST', '/api/storage')
            conn.putheader('Transfer-Encoding', 'chunked')
            conn.endheaders()
            conn.send(raw)
            response = conn.getresponse()
            status, body = response.status, response.read()
            return status, body
        finally:
            conn.close()

    def test_chunk_metadata_limits(self):
        from unittest.mock import patch
        self.assertEqual(self.chunk_request(b'1;' + b'x'*8192 + b'\r\nx\r\n0\r\n\r\n')[0], 413)
        with patch.object(server, 'REQUEST_METADATA_MAX', 64):
            self.assertEqual(self.chunk_request((b'1;abcdefghij\r\nx\r\n')*6+b'0\r\n\r\n')[0], 413)
            self.assertEqual(self.chunk_request(b'0\r\n'+b'X-Test: '+b'x'*60+b'\r\n\r\n')[0], 413)
        self.assertEqual(self.chunk_request(b'nohex\r\n')[0], 400)
        self.assertEqual(self.chunk_request(b'1\r\nxXX0\r\n\r\n')[0], 400)
        # Valid chunking still reaches the storage revision check.
        self.assertEqual(self.chunk_request(b'2;test=ok\r\n{}\r\n0\r\nX-Test: ok\r\n\r\n')[0], 428)

    def test_chunk_read_deadline(self):
        from unittest.mock import patch
        with patch.object(server, 'REQUEST_BODY_TIMEOUT', 0.1):
            conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
            try:
                conn.putrequest('POST', '/api/storage')
                conn.putheader('Transfer-Encoding', 'chunked')
                conn.endheaders()
                conn.send(b'1;unfinished')
                response = conn.getresponse()
                self.assertEqual(response.status, 408)
                response.read()
            finally:
                conn.close()

    def test_archive_memory_import_shares_live_writer_lock(self):
        from concurrent.futures import ThreadPoolExecutor
        path = DATA / 'memory' / 'archive-race.json'
        path.parent.mkdir(exist_ok=True)
        started, finished = threading.Event(), threading.Event()
        def importing():
            started.set()
            result = server._archive_write(str(path), '{"items":[]}', False)
            finished.set()
            return result
        with ThreadPoolExecutor(max_workers=1) as pool:
            with server.MEM_LOCK:
                future = pool.submit(importing)
                self.assertTrue(started.wait(3))
                self.assertFalse(finished.wait(0.1))
                path.write_text('{"items":[{"text":"live memory"}]}')
            self.assertEqual(future.result(timeout=3), 'skipped_exists')
        self.assertIn('live memory', path.read_text())
        self.assertEqual(list(path.parent.glob('.zqy-import-*.tmp')), [])

    def test_upstream_plain_and_gzip_size_limits(self):
        import io
        import gzip
        class Response(io.BytesIO):
            headers = {}
        self.assertEqual(server._resp_bytes(Response(b'valid'), limit=8), b'valid')
        self.assertEqual(server._resp_bytes(Response(gzip.compress(b'valid')), limit=64), b'valid')
        with self.assertRaises(server.LLMError):
            server._resp_bytes(Response(b'x'*65), limit=64)
        with self.assertRaises(server.LLMError):
            server._resp_bytes(Response(gzip.compress(b'x'*4096)), limit=64)
        with self.assertRaises(server.LLMError):
            server._resp_bytes(Response(b'\x1f\x8bbroken'), limit=64)

    def test_stream_response_line_and_total_limits(self):
        import io
        import gzip
        from unittest.mock import patch
        class Response(io.BytesIO):
            headers = {}
        with patch.object(server, 'MODEL_RESPONSE_MAX', 64), patch.object(server, 'MODEL_LINE_MAX', 16):
            self.assertEqual(list(server._iter_resp_lines(Response(b'data: ok\n\n'))), ['data: ok', ''])
            self.assertEqual(list(server._iter_resp_lines(Response(gzip.compress(b'data: ok\n\n')))), ['data: ok', ''])
            with self.assertRaises(server.LLMError):
                list(server._iter_resp_lines(Response(b'x'*17+b'\n')))
            with self.assertRaises(server.LLMError):
                list(server._iter_resp_lines(Response(b'line\n'*14)))
            with self.assertRaises(server.LLMError):
                list(server._iter_resp_lines(Response(gzip.compress(b'line\n'*100))))

    def test_memory_merge_preserves_live_metadata_and_id_conflicts(self):
        from unittest.mock import patch
        with patch.object(server, 'MEMORY_V2', True):
            pid = 'atomic-merge-v2'
            server.replace_profile_memory(pid, [{'id': 'same-id', 'text': 'live fact', 'imp': 5, 'pinned': True}])
            self.assertTrue(server.merge_profile_memory(pid, [
                {'id': 'same-id', 'text': 'different imported fact', 'imp': 4},
                {'id': 'duplicate', 'text': 'live fact', 'imp': 1},
            ]))
            items = server._mem_load_v2(pid)['items']
            self.assertEqual(len(items), 2)
            self.assertEqual(len({item['id'] for item in items}), 2)
            live = next(item for item in items if item['text'] == 'live fact')
            self.assertEqual(live['imp'], 5)
            self.assertTrue(live['pinned'])

    def test_parallel_memory_merges_preserve_all_facts(self):
        from unittest.mock import patch
        from concurrent.futures import ThreadPoolExecutor
        with patch.object(server, 'MEMORY_V2', True):
            pid = 'parallel-merge'
            server.replace_profile_memory(pid, [{'text': 'initial fact'}])
            with ThreadPoolExecutor(max_workers=6) as pool:
                result = list(pool.map(lambda i: server.merge_profile_memory(pid, [{'text': 'unique fact %s' % i}]), range(12)))
            self.assertTrue(all(result))
            self.assertEqual(len(server._mem_load_v2(pid)['items']), 13)

    def test_legacy_memory_accepts_structured_backups_without_dict_stringification(self):
        from unittest.mock import patch
        with patch.object(server, 'MEMORY_V2', False):
            pid = 'legacy-merge'
            server.replace_profile_memory(pid, ['2026-10-31 10:00 initial fact'])
            self.assertTrue(server.merge_profile_memory(pid, [{'text': 'imported fact'}]))
            facts = [server._split_mem_item(item)[1] for item in server.profile_memory_items(pid)]
            self.assertEqual(set(facts), {'initial fact', 'imported fact'})
            self.assertTrue(server.replace_profile_memory(pid, [{'text': 'replacement fact'}]))
            self.assertEqual(server._split_mem_item(server.profile_memory_items(pid)[0])[1], 'replacement fact')

    def test_non_object_json_returns_400(self):
        for payload in ('[]', 'null', '42', '"string"'):
            for path in ('/api/answer', '/api/inbox', '/api/settings', '/api/chat'):
                status, _, _ = self.request('POST', path, payload.encode(), {'Content-Type': 'application/json'})
                self.assertEqual(status, 400)

    def test_invalid_storage_shapes_do_not_replace_saved_data(self):
        revision = server.read_storage()['revision']
        for data in (None, [], 'invalid', {'sessions': {}}, {'diary': []}, {'meta': []}):
            payload = json.dumps({'expected_revision': revision, 'data': data}).encode()
            status, _, _ = self.request('POST', '/api/storage', payload, {'Content-Type': 'application/json'})
            self.assertEqual(status, 400)
            self.assertEqual(server.read_storage()['revision'], revision)

    def test_invalid_archive_storage_is_reported_without_overwriting(self):
        import io
        import zipfile
        revision = server.read_storage()['revision']
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('storage.json', json.dumps({'sessions': 42}))
        result = server.archive_import(data.getvalue(), True)
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_code'], 'archive_invalid_storage')
        self.assertEqual(server.read_storage()['revision'], revision)

    def test_stale_memory_model_result_cannot_resurrect_cleared_facts(self):
        from unittest.mock import patch
        for mode in (False, True):
            pid = 'cleared-model-%s' % mode
            with patch.object(server, 'MEMORY_V2', mode):
                server.clear_profile_memory(pid)
                def cleared_during_model(*args, **kwargs):
                    server.clear_profile_memory(pid)
                    return {'content': json.dumps({'add': ['stale fact'], 'forget': [], 'update': []})}
                with patch.object(server, '_chat_small', side_effect=cleared_during_model):
                    result = server.manage_memory(pid, 'test message')
                self.assertEqual(result['added'], [])
                self.assertEqual(server.profile_memory_items(pid), [])

    def test_memory_model_result_does_not_overwrite_concurrent_add(self):
        from unittest.mock import patch
        pid = 'concurrent-model'
        server.replace_profile_memory(pid, ['initial fact'])
        def live_add(*args, **kwargs):
            server.write_profile_memory(pid, 'new live fact')
            return {'content': json.dumps({'add': ['model stale fact'], 'forget': [0], 'update': []})}
        with patch.object(server, '_chat_small', side_effect=live_add):
            result = server.manage_memory(pid, 'test message')
        self.assertEqual(result['forgot'], [])
        facts = [server._split_mem_item(item)[1] for item in server.profile_memory_items(pid)]
        self.assertIn('initial fact', facts)
        self.assertIn('new live fact', facts)
        self.assertNotIn('model stale fact', facts)

    def test_old_turn_and_fallback_cannot_write_after_memory_reset(self):
        from unittest.mock import patch
        pid = 'old-turn'
        epoch = server.memory_control_epoch(pid)
        server.clear_profile_memory(pid)
        with patch.object(server, 'manage_memory', side_effect=AssertionError('stale turn reached model')):
            self.assertEqual(server.update_turn_memory(pid, 'old message', epoch)['added'], [])
        epoch = server.memory_control_epoch(pid)
        def reset_during_fallback(*args):
            server.clear_profile_memory(pid)
            return 'stale fallback fact'
        with patch.object(server, 'manage_memory', return_value=None), patch.object(server, '_extract_fact', side_effect=reset_during_fallback):
            self.assertEqual(server.update_turn_memory(pid, 'old message', epoch)['added'], [])
        self.assertEqual(server.profile_memory_items(pid), [])

    def test_bad_memory_replace_cannot_clear_existing_facts(self):
        pid = 'invalid-replace'
        server.replace_profile_memory(pid, ['keep this fact'])
        for items in ({}, None, 'wrong shape'):
            payload = json.dumps({'profile_id': pid, 'action': 'replace', 'items': items}).encode()
            status, _, _ = self.request('POST', '/api/memory', payload, {'Content-Type': 'application/json'})
            self.assertEqual(status, 400)
            self.assertEqual(server.profile_memory_items(pid), ['keep this fact'])

    def test_current_turn_memory_updates_still_persist_in_both_modes(self):
        from unittest.mock import patch
        for mode in (False, True):
            pid = 'valid-model-%s' % mode
            with patch.object(server, 'MEMORY_V2', mode):
                server.replace_profile_memory(pid, ['original fact'])
                epoch = server.memory_control_epoch(pid)
                model = {'content': json.dumps({'forget': [], 'update': [{'index': 0, 'fact': 'updated fact'}], 'add': ['new fact']})}
                with patch.object(server, '_chat_small', return_value=model):
                    result = server.update_turn_memory(pid, 'new message', epoch)
                facts = [server._split_mem_item(item)[1] for item in server.profile_memory_items(pid)]
                self.assertEqual(set(facts), {'updated fact', 'new fact'})
                self.assertEqual(result['updated'], ['updated fact'])
                self.assertTrue(result['added'])

    def test_archive_preflight_rejects_bad_later_entry_before_writing_storage(self):
        import io
        import zipfile
        revision = server.read_storage()['revision']
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.writestr('storage.json', json.dumps({'sessions': [{'msgs': ['new data']}]}))
            zf.writestr('memories/invalid.json', json.dumps({'items': 'not an array'}))
        result = server.archive_import(archive.getvalue(), True)
        self.assertFalse(result['ok'])
        self.assertEqual(server.read_storage()['revision'], revision)

    def test_archive_empty_and_failed_storage_write_are_not_success(self):
        import io
        import zipfile
        from unittest.mock import patch
        for files in ({'unrecognized.txt': 'ignored'}, {'manifest.json': '{}'}):
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w') as zf:
                for key, value in files.items():
                    zf.writestr(key, value)
            self.assertFalse(server.archive_import(archive.getvalue(), True)['ok'])
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.writestr('storage.json', json.dumps({'sessions': []}))
        with patch.object(server, 'put_storage', return_value=None):
            self.assertFalse(server.archive_import(archive.getvalue(), True)['ok'])

    def test_archive_export_does_not_silently_omit_unreadable_storage(self):
        from unittest.mock import patch
        with patch.object(server, 'read_storage', side_effect=OSError('simulated read failure')):
            status, _, body = self.request('GET', '/api/archive')
        self.assertEqual(status, 500)
        self.assertIn(b'no complete backup', body)

    def test_inbox_ownership_late_messages_and_capacity(self):
        from unittest.mock import patch
        sid = 'owned-inbox'
        owner = server._inbox_begin(sid)
        self.assertIsNot(owner, False)
        self.assertIs(server._inbox_begin(sid), False)
        for i in range(server.INBOX_MAX):
            self.assertTrue(server.inbox_queue(sid, 'message %s' % i)['queued'])
        self.assertFalse(server.inbox_queue(sid, 'overflow')['queued'])
        self.assertFalse(server.inbox_queue(sid, 'x'*(server.INBOX_ITEM_CHARS+1))['queued'])
        self.assertEqual(len(server._inbox_take(sid, owner)), server.INBOX_MAX)
        self.assertFalse(server.inbox_queue(sid, 'late')['queued'])
        with server.INBOX_LOCK:
            server.INBOX[sid]['until'] = 0
        replacement = server._inbox_begin(sid)
        server._inbox_end(sid, owner)
        self.assertTrue(server.inbox_queue(sid, 'new owner message')['queued'])
        self.assertEqual(server._inbox_take(sid, owner), [])
        self.assertEqual(server._inbox_take(sid, replacement), ['new owner message'])
        server._inbox_end(sid, replacement)
        self.assertNotIn(sid, server.INBOX)

    def test_sse_disconnect_explicitly_closes_retained_generator(self):
        closed = []
        def events():
            try:
                yield 'event: delta\ndata: {}\n\n'
                yield 'event: done\ndata: {}\n\n'
            finally:
                closed.append(True)
        class BrokenWriter:
            def write(self, body):
                raise BrokenPipeError()
        handler = object.__new__(server.Handler)
        handler.send_response = lambda *args: None
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        handler.wfile = BrokenWriter()
        retained = events()
        handler._send_sse(retained)
        self.assertEqual(closed, [True])
        self.assertEqual(list(retained), [])

    def test_legacy_memory_archive_round_trip_is_immediately_readable(self):
        import io
        import zipfile
        from unittest.mock import patch
        pid = 'legacy-archive-roundtrip'
        with patch.object(server, 'MEMORY_V2', False):
            server.replace_profile_memory(pid, ['2026-11-01 09:00 legacy archive fact'])
            archive = server.archive_export(pid)
            with zipfile.ZipFile(io.BytesIO(archive)) as zf:
                memory = json.loads(zf.read('memories/' + pid + '.json'))
                self.assertEqual(memory['items'][0]['text'], 'legacy archive fact')
            server.clear_profile_memory(pid)
            result = server.archive_import(archive, True)
            self.assertTrue(result['ok'])
            self.assertIn('legacy archive fact', server.profile_memory_items(pid)[0])
            with patch.object(server, 'MEMORY_V2', True):
                self.assertEqual(server._mem_load_v2(pid)['items'][0]['text'], 'legacy archive fact')

    def test_memory_archive_preserves_active_legacy_data_over_stale_json(self):
        import io
        import zipfile
        from unittest.mock import patch
        pid = 'stale-json-archive'
        with patch.object(server, 'MEMORY_V2', True):
            server.replace_profile_memory(pid, [{'text': 'stale structured fact'}])
        with patch.object(server, 'MEMORY_V2', False):
            server.replace_profile_memory(pid, ['current legacy fact'])
            archive = server.archive_export(pid)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            data = json.loads(zf.read('memories/' + pid + '.json'))
        self.assertEqual([item['text'] for item in data['items']], ['current legacy fact'])

    def test_default_memory_archive_import_does_not_shadow_existing_legacy_file(self):
        import io
        import zipfile
        from unittest.mock import patch
        pid = 'keep-legacy-on-import'
        with patch.object(server, 'MEMORY_V2', False):
            server.replace_profile_memory(pid, ['live legacy fact'])
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w') as zf:
                zf.writestr('memories/' + pid + '.json', json.dumps({'items': [{'text': 'imported fact'}]}))
            result = server.archive_import(archive.getvalue(), False)
            self.assertTrue(result['ok'])
            self.assertEqual(result['memories'][0]['result'], 'skipped_exists')
            self.assertEqual(server.profile_memory_items(pid), ['live legacy fact'])
            self.assertFalse(os.path.exists(server._mem_json_path(pid)))

    def test_memory_archive_preserves_long_facts_and_all_imported_entries(self):
        import io
        import zipfile
        from unittest.mock import patch
        pid = 'full-legacy-archive'
        facts = ['2026-11-01 09:00 fact %s %s' % (i, 'x'*150) for i in range(server.MEM_MAX_ITEMS+3)]
        with patch.object(server, 'MEMORY_V2', False):
            with server.MEM_LOCK:
                server._atomic_write_memory(pid, facts)
            archive = server.archive_export(pid)
            server.clear_profile_memory(pid)
            self.assertTrue(server.archive_import(archive, True)['ok'])
            restored = server.profile_memory_items(pid)
        self.assertEqual(restored, facts)

    def test_overlapping_stream_rejected_and_inner_generator_closed(self):
        from unittest.mock import patch
        closed = []
        def inner():
            try:
                yield 'event: delta\ndata: {}\n\n'
                yield 'event: done\ndata: {}\n\n'
            finally:
                closed.append(True)
        retained = inner()
        with patch.object(server, '_stream_chat_inner', return_value=retained):
            first = server.stream_chat({'session_id': 'duplicate-stream'})
            next(first)
            second = list(server.stream_chat({'session_id': 'duplicate-stream'}))
            self.assertIn('session_busy', ''.join(second))
            first.close()
        self.assertEqual(closed, [True])
        self.assertNotIn('duplicate-stream', server.INBOX)

    def test_demo_model_full_sse_flow(self):
        import subprocess
        import sys
        import socket
        import time
        from unittest.mock import patch
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        demo = subprocess.Popen([sys.executable, str(ROOT / 'scripts/demo_llm.py'), str(port)],
                                env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while True:
                self.assertIsNone(demo.poll())
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                        break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.05)
            with patch.object(server, 'BASE_URL', 'http://127.0.0.1:%s/v1' % port):
                payload = json.dumps({'message': 'hello', 'stream': True, 'session_id': 'demo-smoke',
                                      'profile_id': 'demo-smoke', 'search': False, 'memorize': False}).encode()
                status, _, raw = self.request('POST', '/api/chat', payload, {'Content-Type': 'application/json'})
            self.assertEqual(status, 200)
            self.assertIn(b'event: delta', raw)
            self.assertIn(b'event: done', raw)
            self.assertNotIn(b'"failed": true', raw)
            self.assertNotIn('demo-smoke', server.INBOX)
        finally:
            demo.terminate()
            demo.wait(timeout=5)

    def test_archive_reserved_profile_names_keep_their_memory_namespace(self):
        import io
        import zipfile
        revision = server.read_storage()['revision']
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.writestr('memories/storage.json', json.dumps({'items': [{'text': 'scoped memory'}]}))
            zf.writestr('memories/manifest.json', json.dumps({'items': [{'text': 'another memory'}]}))
        result = server.archive_import(archive.getvalue(), True)
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['memories']), 2)
        self.assertEqual(server.read_storage()['revision'], revision)
        self.assertEqual(server._archive_key('wrapped/memories/storage.json'), 'memories/storage.json')
        self.assertEqual(server._archive_key('memories/../storage.json'), '')
        self.assertEqual(server._archive_key('memories/user.name.json'), '')

    def test_corrupt_settings_never_send_a_request_to_default_provider(self):
        from unittest.mock import patch
        (DATA / 'settings.json').write_text('{broken json')
        with patch.object(server.urllib.request, 'build_opener', side_effect=AssertionError('network request attempted')):
            with self.assertRaises(server.SettingsReadError):
                server._chat([], False)
        status, _, body = self.request('GET', '/api/settings')
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body)['error_code'], 'settings_unreadable')
        self.assertEqual(self.request('GET', '/')[0], 200)
        self.assertEqual(self.request('GET', '/health')[0], 200)

    def test_corrupt_settings_require_explicit_complete_repair_and_keep_backup(self):
        original = b'{broken settings with fake-old-key'
        (DATA / 'settings.json').write_bytes(original)
        with self.assertRaises(ValueError):
            server.save_model_settings({'timeout': 40})
        self.assertEqual((DATA / 'settings.json').read_bytes(), original)
        result = server.save_model_settings({'base_url': 'https://repaired.example/v1', 'model': 'repaired-model',
                                             'api_key': 'fake-repaired-key',
                                             'fallbacks': [{'base_url': 'https://backup.example/v1', 'model': 'b', 'api_key': 'fake-backup'}]})
        self.assertEqual(result['model'], 'repaired-model')
        self.assertEqual(server.model_settings()['api_key'], 'fake-repaired-key')
        self.assertEqual(len(server.saved_fallbacks()), 1)
        self.assertTrue(any(p.read_bytes() == original for p in DATA.glob('.zqy-settings-corrupt-*.bak')))

    def test_invalid_settings_shapes_fail_closed(self):
        for value in ([], {'base_url': 42}, {'api_key': ['wrong']}, {'fallbacks': {}}):
            (DATA / 'settings.json').write_text(json.dumps(value))
            with self.assertRaises(server.SettingsReadError):
                server.model_settings()

    def test_corrupt_storage_is_not_reported_as_empty_or_silently_replaced(self):
        for raw in (b'{broken', b'[]', b'{"data":[]}', b'{}'):
            (DATA / 'storage.json').write_bytes(raw)
            status, _, body = self.request('GET', '/api/storage')
            self.assertEqual(status, 503)
            self.assertEqual(json.loads(body)['error_code'], 'storage_unreadable')
            self.assertNotIn('revision', json.loads(body))
            payload = json.dumps({'data': {'sessions': []}, 'expected_revision': None}).encode()
            self.assertEqual(self.request('POST', '/api/storage', payload, {'Content-Type': 'application/json'})[0], 503)
            self.assertEqual((DATA / 'storage.json').read_bytes(), raw)

    def test_explicit_archive_restore_can_repair_corrupt_storage(self):
        import io
        import zipfile
        (DATA / 'storage.json').write_bytes(b'{broken')
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as zf:
            zf.writestr('storage.json', json.dumps({'sessions': [{'msgs': ['recovered']}]}))
        refused = server.archive_import(archive.getvalue(), False)
        self.assertFalse(refused['ok'])
        self.assertEqual(refused['error_code'], 'storage_unreadable')
        self.assertEqual((DATA / 'storage.json').read_bytes(), b'{broken')
        self.assertTrue(server.archive_import(archive.getvalue(), True)['ok'])
        self.assertEqual(server.read_storage()['data']['sessions'][0]['msgs'], ['recovered'])
        self.assertTrue(any(p.read_bytes() == b'{broken' for p in DATA.glob('.zqy-storage-corrupt-*.bak')))

    def test_missing_memory_id_never_falls_back_to_another_item(self):
        from unittest.mock import patch
        pid = 'stable-memory-target'
        with patch.object(server, 'MEMORY_V2', True):
            self.assertTrue(server.replace_profile_memory(pid, [{'id': 'keep', 'text': 'keep this fact'}]))
            self.assertFalse(server.delete_profile_memory(pid, item_id='gone', index=0, text='keep this fact'))
            self.assertEqual([x['id'] for x in server.memory_snapshot(pid)['items_v2']], ['keep'])
        with patch.object(server, 'MEMORY_V2', False):
            self.assertFalse(server.delete_profile_memory(pid, item_id='gone', index=0))
            self.assertEqual(len(server.profile_memory_items(pid)), 1)

    def test_legacy_memory_edits_reject_changed_snapshot(self):
        from unittest.mock import patch
        pid = 'legacy-edit-conflict'
        def post(data):
            data['profile_id'] = pid
            return self.request('POST', '/api/memory', json.dumps(data).encode(), {'Content-Type': 'application/json'})
        with patch.object(server, 'MEMORY_V2', False):
            server.replace_profile_memory(pid, ['old fact', 'another fact'])
            initial = server.profile_memory_items(pid)
            server.write_profile_memory(pid, 'new fact')
            current = server.profile_memory_items(pid)
            for action in ({'action': 'delete', 'index': 0}, {'action': 'replace', 'items': ['edited fact']}):
                status, _, body = post(dict(action, expected_items=initial))
                self.assertEqual(status, 409)
                self.assertEqual(json.loads(body)['error_code'], 'memory_conflict')
                self.assertEqual(server.profile_memory_items(pid), current)
            self.assertEqual(post({'action': 'delete', 'index': 0, 'expected_items': None})[0], 400)
            status, _, body = post({'action': 'delete', 'index': 0, 'expected_items': current})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)['ok'])
            self.assertEqual(server.profile_memory_items(pid), current[1:])
            self.assertTrue(json.loads(post({'action': 'replace', 'items': ['edited fact'],
                                            'expected_items': current[1:]})[2])['ok'])
            self.assertEqual(server.profile_memory_items(pid), ['edited fact'])

    def test_revision_required(self):
        status, _, _ = self.request('POST', '/api/storage', b'{"data":{}}', {'Content-Type': 'application/json'})
        self.assertEqual(status, 428)

    def test_fallback_different_host_does_not_receive_primary_key(self):
        from unittest.mock import patch
        fallback = server._chain_entry({'id': 'fb1', 'base_url': 'https://other.example/v1', 'model': 'm', 'api_key': ''})
        with patch.object(server, 'saved_fallbacks', return_value=[fallback]):
            self.assertEqual(len(server.model_chain()), 1)
        fallback['base_url'] = server.BASE_URL
        with patch.object(server, 'saved_fallbacks', return_value=[fallback]):
            self.assertEqual(server.model_chain()[1]['api_key'], 'fake-review-key')

    def test_changing_primary_host_requires_new_key(self):
        with self.assertRaises(ValueError):
            server.save_model_settings({'base_url': 'https://other.example/v1'})

    def test_concurrent_writes_use_independent_temp_files(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: server.put_storage({'value': i}), range(16)))
        self.assertTrue(all(results))
        self.assertIn(server.read_storage()['data']['value'], range(16))

    def test_oversized_content_length_rejected_before_body(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        conn.putrequest('POST', '/api/storage')
        conn.putheader('Content-Length', str(server.ARCHIVE_MAX_BYTES + 1))
        conn.endheaders()
        res = conn.getresponse()
        self.assertEqual(res.status, 413)
        res.read()
        conn.close()

    def test_oversized_chunk_rejected_before_body(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=4)
        conn.putrequest('POST', '/api/storage')
        conn.putheader('Transfer-Encoding', 'chunked')
        conn.endheaders()
        conn.send(('%x\r\n' % (server.ARCHIVE_MAX_BYTES + 1)).encode())
        res = conn.getresponse()
        self.assertEqual(res.status, 413)
        res.read()
        conn.close()


if __name__ == '__main__':
    unittest.main()
