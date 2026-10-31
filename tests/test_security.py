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
