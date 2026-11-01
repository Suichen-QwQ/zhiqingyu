import importlib.util
import logging
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(TEMP.name) / 'prototype.db').replace('\\', '/')
sys.path.insert(0, str(ROOT / 'prototype-backend'))
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine, SessionLocal
from app.models import AIConfig, Session as ChatSession, Message, DailySummary
from app.core.provider_factory import get_llm_provider
from app.core.providers.openai_provider import OpenAIProvider
from app.services.daily_summary_service import DailySummaryService


class PrototypeTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        self.client = TestClient(app, base_url='http://127.0.0.1')
        self.addCleanup(self.client.close)

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
        TEMP.cleanup()

    def test_keys_never_appear_in_config_responses(self):
        key = 'fake-private-key-review'
        body = {'provider': 'openai', 'api_key': key, 'base_url': 'https://one.example/v1', 'model': 'test'}
        result = self.client.post('/api/ai-config', json=body)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()['data']['has_key'])
        for response in (result, self.client.get('/api/ai-config'),
                         self.client.put('/api/ai-config/openai', json={'model': 'changed'}),
                         self.client.post('/api/ai-config/openai/activate')):
            self.assertNotIn(key, response.text)
            self.assertNotIn('"api_key"', response.text)

    def test_address_changes_require_new_credentials(self):
        self.client.post('/api/ai-config', json={'provider': 'openai', 'api_key': 'fake-original', 'base_url': 'https://one.example/v1'})
        response = self.client.put('/api/ai-config/openai', json={'base_url': 'https://two.example/v1'})
        self.assertEqual(response.json()['error']['code'], 'NEW_KEY_REQUIRED')
        with SessionLocal() as db:
            self.assertEqual(db.query(AIConfig).first().base_url, 'https://one.example/v1')
        response = self.client.put('/api/ai-config/openai', json={'base_url': 'https://two.example/v1', 'api_key': 'fake-new'})
        self.assertIsNone(response.json()['error'])

    def test_foreign_sites_and_untrusted_hosts_are_denied(self):
        for method, path, headers in [('GET', '/api/ai-config', {'Origin': 'https://evil.example'}),
                                     ('POST', '/api/ai-config', {'Origin': 'https://evil.example'}),
                                     ('GET', '/api/sessions', {'Host': 'evil.example'}),
                                     ('GET', '/api/sessions', {'Sec-Fetch-Site': 'cross-site'})]:
            self.assertEqual(self.client.request(method, path, headers=headers).status_code, 403)
        self.assertEqual(self.client.get('/api/sessions', headers={'Origin': 'http://127.0.0.1:5525'}).status_code, 200)

    def test_missing_saved_key_does_not_reuse_environment_key(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fake-environment-secret'}):
            with self.assertRaises(ValueError):
                OpenAIProvider(api_key='', base_url='https://other.example/v1')
            with SessionLocal() as db:
                db.add(AIConfig(id='openai', provider='openai', is_active=True, api_key='', base_url='https://other.example/v1'))
                db.commit()
                with self.assertRaises(RuntimeError):
                    get_llm_provider(db)

    def test_openai_transport_does_not_follow_redirects(self):
        with patch('app.core.providers.openai_provider.OpenAI') as factory:
            provider = OpenAIProvider(api_key='fake-key', base_url='https://one.example/v1')
            transport = factory.call_args.kwargs['http_client']
            self.assertFalse(transport.follow_redirects)
            self.assertEqual(transport.timeout.connect, 60.0)
            transport.close()

    def test_configuration_failures_do_not_return_secret_exception_text(self):
        with patch('sqlalchemy.orm.Session.commit', side_effect=RuntimeError('fake-secret-in-sql-parameters')):
            response = self.client.post('/api/ai-config', json={'provider': 'openai', 'api_key': 'fake-key'})
        self.assertNotIn('fake-secret-in-sql-parameters', response.text)
        self.assertEqual(response.json()['error']['code'], 'CREATE_CONFIG_ERROR')

    def test_chat_requires_a_user_turn_and_nonempty_history(self):
        for messages in ([], [{'role': 'assistant', 'content': 'reply'}], [{'role': 'system', 'content': 'system'}]):
            self.assertEqual(self.client.post('/api/chat', json={'messages': messages}).status_code, 422)

    def test_daily_summary_accepts_internal_system_prompts(self):
        from datetime import date
        from types import SimpleNamespace
        captured = []
        with SessionLocal() as db:
            db.add(ChatSession(id='summary-session'))
            db.add(Message(session_id='summary-session', role='user', content='a private test day'))
            db.add(DailySummary(date=date.today(), main_emotion='calm', avg_intensity=2))
            db.commit()
            provider = SimpleNamespace(generate_text=lambda messages: captured.append(messages) or 'generated diary')
            self.assertEqual(DailySummaryService(db, provider).generate_daily_summary(date.today()), 'generated diary')
            self.assertEqual(captured[0][0].role, 'system')

    def test_prompts_are_not_written_to_logs(self):
        from app.core.providers.base_provider import JsonChatLLMProvider
        from types import SimpleNamespace
        logger = logging.getLogger('private-prompt-test')
        with self.assertLogs(logger, level='DEBUG') as records:
            JsonChatLLMProvider._log_prompt(SimpleNamespace(logger=logger), 'test', 'private user transcript')
        self.assertNotIn('private user transcript', '\n'.join(records.output))

    def test_extra_configuration_credentials_are_not_returned(self):
        response = self.client.post('/api/ai-config', json={'provider': 'openai', 'api_key': 'fake-primary',
            'extra_config': {'temperature': 0.7, 'nested': {'secret': 'fake-extra-secret', 'enabled': True},
                             'headers': {'X-Custom': 'fake-header-secret'}}})
        self.assertNotIn('fake-extra-secret', response.text)
        self.assertNotIn('fake-header-secret', response.text)
        self.assertEqual(response.json()['data']['extra_config']['temperature'], 0.7)

    def test_latest_reply_is_included_in_daily_intensity(self):
        from datetime import date
        from types import SimpleNamespace
        from app.services.chat_service import ChatService
        from app.core.llm_provider import LLMResult
        from app.schemas.chat import ChatMessage
        from app.schemas.style import ConversationState
        with SessionLocal() as db:
            db.add(ChatSession(id='intensity-session'))
            db.add(Message(session_id='intensity-session', role='assistant', content='old', intensity=2, emotion='neutral'))
            db.add(DailySummary(date=date.today(), main_emotion='neutral', avg_intensity=2))
            db.commit()
            result = LLMResult(reply='new reply', emotion='neutral', intensity=8, topics=[], risk_level='low')
            with patch('app.services.chat_service.generate_reply_with_algorithm', return_value=(result, ConversationState())), \
                 patch('app.services.chat_service.parse_user_message', return_value=None), \
                 patch('app.services.chat_service.SafetyChecker.check_reply_quality', return_value=SimpleNamespace(passed=True)):
                ChatService(db, None).process_chat('intensity-session', [ChatMessage(role='user', content='new question')])
            self.assertAlmostEqual(db.query(DailySummary).first().avg_intensity, 6.0)

    def test_empty_read_endpoints_return_consistent_data(self):
        for path in ('/api/sessions', '/api/stats/overview?days=7', '/api/stats/tokens?days=7',
                     '/api/daily?from=2026-10-01&to=2026-11-01', '/api/daily/2026-11-01'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertIsNone(response.json()['error'], path)
            self.assertIsNotNone(response.json()['data'], path)

    def test_model_urls_reject_embedded_credentials(self):
        response = self.client.post('/api/ai-config', json={'provider': 'openai',
            'base_url': 'https://user:fake-password@example.test/v1', 'api_key': 'fake-key'})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('fake-password', response.text)

    def test_deleted_sessions_do_not_leave_messages(self):
        with SessionLocal() as db:
            db.add(ChatSession(id='delete-session'))
            db.add(Message(session_id='delete-session', role='user', content='delete me'))
            db.commit()
        response = self.client.delete('/api/sessions/delete-session')
        self.assertTrue(response.json()['data']['success'])
        with SessionLocal() as db:
            self.assertEqual(db.query(Message).count(), 0)


if __name__ == '__main__':
    unittest.main()
