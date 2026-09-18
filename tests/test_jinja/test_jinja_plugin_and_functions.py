from unittest import TestCase
from unittest.mock import patch, MagicMock

from flask_site_framework.jinja import JinjaPlugin, jinja_filter, jinja_global
from flask_site_framework import jinja


@patch('flask_site_framework.Plugin.init_app')
class TestJinjaPlugin_InitApp(TestCase):
    def test_init_app(self, mock_super_init_app):
        mock_app = MagicMock()
        p = JinjaPlugin()
        with patch('flask_site_framework.jinja.bool') as mock_bool:
            p.init_app(mock_app)
            mock_super_init_app.assert_called_once_with(mock_app)
            mock_app.jinja_env.filters.update.assert_called_once_with(jinja.jinja_data['filters'])
            mock_app.jinja_env.globals.update.assert_called_once_with(jinja.jinja_data['globals'])
            mock_app.config.get.assert_called_once_with('TEMPLATES_AUTO_RELOAD')
            mock_bool.assert_called_once_with(mock_app.config.get.return_value)
            self.assertEqual(mock_app.jinja_env.auto_reload, mock_bool.return_value)


@patch('flask_site_framework.jinja.jinja_data', {'filters': {}, 'globals': {}})
class TestJinjaFilter(TestCase):
    def test_without_name(self):
        def mock_fn():pass
        jinja_filter()(mock_fn)
        self.assertEqual(jinja.jinja_data['filters']['mock_fn'], mock_fn)

    def test_with_name(self):
        def mock_fn():pass
        jinja_filter('test')(mock_fn)
        self.assertEqual(jinja.jinja_data['filters']['test'], mock_fn)


@patch('flask_site_framework.jinja.jinja_data', {'filters': {}, 'globals': {}})
class TestJinjaGlobal(TestCase):
    def test_without_name(self):
        def mock_fn():pass
        jinja_global()(mock_fn)
        self.assertEqual(jinja.jinja_data['globals']['mock_fn'], mock_fn)

    def test_with_name(self):
        def mock_fn():pass
        jinja_global('test')(mock_fn)
        self.assertEqual(jinja.jinja_data['globals']['test'], mock_fn)
