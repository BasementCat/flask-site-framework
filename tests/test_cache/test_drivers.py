from unittest import TestCase
from unittest.mock import patch, MagicMock
import threading
import time
import pickle

from flask import Flask

from flask_site_framework import cache


class TestMemoryCacheDriver(TestCase):
    def test_init(self):
        d = cache.MemoryCacheDriver()
        self.assertEqual(d.data, {})
        self.assertTrue(isinstance(d.lock, threading.Lock))

    def test_cache(self):
        d = cache.MemoryCacheDriver()
        with self.assertRaises(KeyError):
            d.get('foo')
        with self.assertRaises(KeyError):
            d.delete('foo')
        with self.assertRaises(KeyError):
            d.get('foo')
        d.set('foo', 'bar')
        self.assertEqual(d.get('foo'), 'bar')
        d.set('foo', 'baz')
        self.assertEqual(d.get('foo'), 'baz')
        self.assertTrue(d.contains('foo'))
        d.delete('foo')
        with self.assertRaises(KeyError):
            d.get('foo')
        self.assertFalse(d.contains('foo'))
        d.set('foo', 'quux', time.time() + 0.25)
        self.assertEqual(d.get('foo'), 'quux')
        self.assertTrue(d.contains('foo'))
        time.sleep(0.3)
        with self.assertRaises(KeyError):
            d.get('foo')
        self.assertFalse(d.contains('foo'))


@patch('flask_site_framework.cache.FlaskRedis')
class TestRedisCacheDriver(TestCase):
    def test_require_config(self, mock_fr):
        config = {'REDIS_URL': {}}
        d = cache.RedisCacheDriver()
        config = d.require_config(config)
        self.assertTrue(config['REDIS_URL']['required'])
        mock_fr.assert_not_called()

    def test_get_flask_plugins(self, mock_fr):
        d = cache.RedisCacheDriver()
        res = d.get_flask_plugins()
        mock_fr.assert_called_once_with()
        self.assertEqual(d.redis, mock_fr.return_value)
        self.assertEqual(res, [mock_fr.return_value])

    def test_set(self, mock_fr):
        d = cache.RedisCacheDriver()
        d.get_flask_plugins()
        d.set('foo', 'bar')
        mock_fr.return_value.set.assert_called_once_with('foo', pickle.dumps('bar'))

    def test_set_with_exp(self, mock_fr):
        d = cache.RedisCacheDriver()
        d.get_flask_plugins()
        d.set('foo', 'bar', 100)
        mock_fr.return_value.set.assert_called_once_with('foo', pickle.dumps('bar'), pxat=100000)

    def test_get_nx(self, mock_fr):
        mock_fr.return_value.get.return_value = None
        d = cache.RedisCacheDriver()
        d.get_flask_plugins()
        with self.assertRaises(KeyError):
            d.get('foo')
        mock_fr.return_value.get.assert_called_once_with('foo')

    def test_get_exists(self, mock_fr):
        mock_fr.return_value.get.return_value = pickle.dumps('bar')
        d = cache.RedisCacheDriver()
        d.get_flask_plugins()
        self.assertEqual(d.get('foo'), 'bar')
        mock_fr.return_value.get.assert_called_once_with('foo')

    def test_delete_nx(self, mock_fr):
        with patch('flask_site_framework.cache.RedisCacheDriver.contains', return_value=0) as mock_contains:
            d = cache.RedisCacheDriver()
            d.get_flask_plugins()
            with self.assertRaises(KeyError):
                d.delete('foo')
            mock_fr.return_value.delete.assert_not_called()
            mock_contains.assert_called_once_with('foo')

    def test_delete_exists(self, mock_fr):
        with patch('flask_site_framework.cache.RedisCacheDriver.contains', return_value=1) as mock_contains:
            d = cache.RedisCacheDriver()
            d.get_flask_plugins()
            d.delete('foo')
            mock_fr.return_value.delete.assert_called_once_with('foo')
            mock_contains.assert_called_once_with('foo')

    def test_contains_nx(self, mock_fr):
        mock_fr.return_value.exists.return_value = 0
        d = cache.RedisCacheDriver()
        d.get_flask_plugins()
        self.assertFalse(d.contains('foo'))
        mock_fr.return_value.exists.assert_called_once_with('foo')

    def test_contains_exists(self, mock_fr):
        mock_fr.return_value.exists.return_value = 1
        d = cache.RedisCacheDriver()
        d.get_flask_plugins()
        self.assertTrue(d.contains('foo'))
        mock_fr.return_value.exists.assert_called_once_with('foo')