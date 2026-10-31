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
