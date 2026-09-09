from unittest import TestCase
from unittest.mock import patch, MagicMock

from flask import Flask

from src.flask_site_framework import cache


class TestWithDriverDecorator(TestCase):
    def test_no_driver_set(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            test_fn = MagicMock()
            wrapped = cache._with_driver(test_fn)
            wrapped('foo', bar='baz')
            test_fn.assert_called_once_with(None, 'foo', bar='baz')

    def test_driver_is_set(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            app._cache_driver = MagicMock()
            test_fn = MagicMock()
            wrapped = cache._with_driver(test_fn)
            wrapped('foo', bar='baz')
            test_fn.assert_called_once_with(app._cache_driver, 'foo', bar='baz')

class TestSet(TestCase):
    def test_no_driver_set(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            cache.set('foo', 'bar')
        # no assertions, but no error should be raised

    def test_no_expiry(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            cache.set('foo', 'bar')
            driver.set.assert_called_once_with('foo', 'bar', expires_at=None)

    def test_expires_in(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context(), patch('src.flask_site_framework.cache.time.time', return_value=100):
            driver = app._cache_driver = MagicMock()
            cache.set('foo', 'bar', expires_in=3)
            driver.set.assert_called_once_with('foo', 'bar', expires_at=103)

    def test_expires_at(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            cache.set('foo', 'bar', expires_at=3)
            driver.set.assert_called_once_with('foo', 'bar', expires_at=3)

    def test_expires_in_preferred(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context(), patch('src.flask_site_framework.cache.time.time', return_value=100):
            driver = app._cache_driver = MagicMock()
            cache.set('foo', 'bar', expires_in=3, expires_at=5)
            driver.set.assert_called_once_with('foo', 'bar', expires_at=103)


class TestGet(TestCase):
    def test_no_driver_set(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            self.assertIsNone(cache.get('foo'))

    def test_get_nx(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.get.side_effect = KeyError('foo')
            self.assertIsNone(cache.get('foo'))
            driver.get.assert_called_once_with('foo')

    def test_get_nx_with_raise(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.get.side_effect = KeyError('foo')
            with self.assertRaises(KeyError):
                cache.get('foo', raise_missing=True)
            driver.get.assert_called_once_with('foo')

    def test_get(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.get.return_value = 'bar'
            self.assertEqual(cache.get('foo', raise_missing=True), 'bar')
            driver.get.assert_called_once_with('foo')


class TestDelete(TestCase):
    def test_no_driver_set(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            self.assertTrue(cache.delete('foo'))

    def test_del_nx(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.delete.side_effect = KeyError('foo')
            self.assertFalse(cache.delete('foo'))
            driver.delete.assert_called_once_with('foo')

    def test_del_nx_with_raise(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.delete.side_effect = KeyError('foo')
            with self.assertRaises(KeyError):
                cache.delete('foo', raise_missing=True)
            driver.delete.assert_called_once_with('foo')

    def test_del(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            self.assertTrue(cache.delete('foo', raise_missing=True))
            driver.delete.assert_called_once_with('foo')


class TestContains(TestCase):
    def test_no_driver_set(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            self.assertFalse(cache.contains('foo'))

    def test_contains_nx(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.contains.return_value = False
            self.assertFalse(cache.contains('foo'))
            driver.contains.assert_called_once_with('foo')
            driver.get.assert_not_called()

    def test_contains(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.contains.return_value = True
            self.assertTrue(cache.contains('foo'))
            driver.contains.assert_called_once_with('foo')
            driver.get.assert_not_called()

    def test_contains_nx__not_implemented(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.contains.side_effect = NotImplementedError
            driver.get.side_effect = KeyError('foo')
            self.assertFalse(cache.contains('foo'))
            driver.contains.assert_called_once_with('foo')
            driver.get.assert_called_once_with('foo')

    def test_contains__not_implemented(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            driver.contains.side_effect = NotImplementedError
            self.assertTrue(cache.contains('foo'))
            driver.contains.assert_called_once_with('foo')
            driver.get.assert_called_once_with('foo')


@patch('src.flask_site_framework.cache.get')
@patch('src.flask_site_framework.cache.set')
class TestGetOrFetch(TestCase):
    def test_no_driver_set(self, mock_set, mock_get):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            fetch_fn = lambda: 'bar'
            self.assertEqual(cache.get_or_fetch('foo', fetch_fn), 'bar')
            mock_get.assert_not_called()
            mock_set.assert_not_called()

    def test_get_fetch_nx(self, mock_set, mock_get):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            mock_get.side_effect = KeyError('foo')
            fetch_fn = lambda: 'bar'
            self.assertEqual(cache.get_or_fetch('foo', fetch_fn), 'bar')
            mock_get.assert_called_once_with('foo', raise_missing=True)
            mock_set.assert_called_once_with('foo', 'bar', expires_in=None, expires_at=None)

    def test_get_fetch(self, mock_set, mock_get):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            mock_get.return_value = 'baz'
            fetch_fn = lambda: 'bar'
            self.assertEqual(cache.get_or_fetch('foo', fetch_fn), 'baz')
            mock_get.assert_called_once_with('foo', raise_missing=True)
            mock_set.assert_not_called()

    def test_get_fetch_exp(self, mock_set, mock_get):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = app._cache_driver = MagicMock()
            mock_get.side_effect = KeyError('foo')
            fetch_fn = lambda: 'bar'
            self.assertEqual(cache.get_or_fetch('foo', fetch_fn, expires_at=3, expires_in=5), 'bar')
            mock_get.assert_called_once_with('foo', raise_missing=True)
            mock_set.assert_called_once_with('foo', 'bar', expires_in=5, expires_at=3)


@patch('src.flask_site_framework.cache.hashlib')
class TestMakeKey(TestCase):
    def test_no_args(self, mock_hl):
        mock_hl.new.return_value.hexdigest.return_value = 'asdf'
        with self.assertRaises(ValueError):
            cache.make_key()
        mock_hl.new.assert_not_called()

    def test_no_kwargs(self, mock_hl):
        mock_hl.new.return_value.hexdigest.return_value = 'asdf'
        k = cache.make_key('foo', 'bar')
        mock_hl.new.assert_not_called()
        self.assertEqual(k, 'foo:bar')

    def test_with_kwargs(self, mock_hl):
        mock_hl.new.return_value.hexdigest.return_value = 'asdf'
        k = cache.make_key('foo', 'bar', foo='baz1', bar='baz2')
        mock_hl.new.assert_called_once_with('sha256', b'bar:baz2:foo:baz1')
        mock_hl.new.return_value.hexdigest.assert_called_once_with()
        self.assertEqual(k, 'foo:bar:asdf')
