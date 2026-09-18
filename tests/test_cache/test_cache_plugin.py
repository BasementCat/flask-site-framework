from unittest import TestCase
from unittest.mock import patch, MagicMock, ANY

from flask_site_framework import cache


@patch('flask_site_framework.Plugin.__init__')
@patch('flask_site_framework.cache.MemoryCacheDriver')
class TestCachePlugin_Init(TestCase):
    def test_init_no_driver(self, mock_mcd, mock_super_init):
        p = cache.CachePlugin()
        self.assertEqual(p.driver, mock_mcd.return_value)
        mock_super_init.assert_called_once_with(app=None)

    def test_init_custom_driver(self, mock_mcd, mock_super_init):
        app = MagicMock()
        driver = MagicMock()
        p = cache.CachePlugin(app=app, driver=driver)
        self.assertEqual(p.driver, driver)
        mock_super_init.assert_called_once_with(app=app)


class TestCachePlugin_GetConfig(TestCase):
    def test_get_config(self):
        driver = MagicMock()
        p = cache.CachePlugin(driver=driver)
        res = p.get_config()
        self.assertEqual(res, driver.require_config.return_value)
        driver.require_config.assert_called_once_with({'REDIS_URL': {'description': ANY}})


class TestCachePlugin_GetFlaskPlugins(TestCase):
    def test_get_flask_plugins(self):
        driver = MagicMock()
        p = cache.CachePlugin(driver=driver)
        res = p.get_flask_plugins()
        self.assertEqual(res, driver.get_flask_plugins.return_value)
        driver.get_flask_plugins.assert_called_once_with()


@patch('flask_site_framework.Plugin.init_app')
class TestCachePlugin_InitApp(TestCase):
    def test_init_app(self, mock_super_init_app):
        driver = MagicMock()
        p = cache.CachePlugin(driver=driver)
        app = MagicMock()
        p.init_app(app)
        self.assertEqual(app._cache_driver, driver)
        mock_super_init_app.assert_called_once_with(app)
