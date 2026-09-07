from unittest import TestCase
from unittest.mock import patch, MagicMock

from src.flask_site_framework import FlaskConfigPlugin


@patch('src.flask_site_framework.Plugin.__init__')
class TestInit(TestCase):
    def test_super_called(self, mock_super_init):
        p = FlaskConfigPlugin()
        mock_super_init.assert_called_once_with(app=None, url_prefix=None)
        self.assertEqual(p.env_prefix, 'FLASK')
    
    def test_super_called_with_args_env_prefix_set(self, mock_super_init):
        p = FlaskConfigPlugin(app='foo', url_prefix='bar', env_prefix='baz')
        mock_super_init.assert_called_once_with(app='foo', url_prefix='bar')
        self.assertEqual(p.env_prefix, 'baz')


class TestGetConfig(TestCase):
    def test_value_returned(self):
        p = FlaskConfigPlugin()
        self.assertGreater(len(p.get_config()), 0)


@patch('src.flask_site_framework.load_dotenv')
@patch('src.flask_site_framework.Plugin.init_app')
class TestInitApp(TestCase):
    def test_calls(self, mock_init_app, mock_load_dotenv):
        p = FlaskConfigPlugin()
        mock_app = MagicMock()
        p.init_app(mock_app)
        mock_load_dotenv.assert_called_once_with()
        mock_app.config.from_prefixed_env.assert_called_once_with(p.env_prefix)
        mock_init_app.assert_called_once_with(mock_app)

    def test_call_order(self, mock_init_app, mock_load_dotenv):
        p = FlaskConfigPlugin()
        calls = []
        def mock_call(name):
            def mock_call_impl(*a, **ka):
                calls.append(name)
            return mock_call_impl
        mock_app = MagicMock()
        mock_load_dotenv.side_effect = mock_call('load_dotenv')
        mock_app.config.from_prefixed_env.side_effect = mock_call('from_prefixed_env')
        mock_init_app.side_effect = mock_call('init_app')
        p.init_app(mock_app)
        self.assertEqual(calls, ['load_dotenv', 'from_prefixed_env', 'init_app'])
