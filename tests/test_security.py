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
