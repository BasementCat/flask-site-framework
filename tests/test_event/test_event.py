from unittest import TestCase
from unittest.mock import patch, MagicMock

from src.flask_site_framework.event import subscribe, subscribes_to, publish
from src.flask_site_framework import event


@patch('src.flask_site_framework.event.event_callbacks', {})
class TestSubscribe(TestCase):
    def test_default_priority(self):
        def test_fn1():pass
        def test_fn2():pass
        subscribe('foo', test_fn1)
        subscribe('foo', test_fn2)
        self.assertEqual(event.event_callbacks['foo'][100], [test_fn1, test_fn2])

    def test_custom_priority(self):
        def test_fn1():pass
        def test_fn2():pass
        subscribe('foo', test_fn1, priority=200)
        subscribe('foo', test_fn2, priority=200)
        self.assertEqual(event.event_callbacks['foo'][200], [test_fn1, test_fn2])


@patch('src.flask_site_framework.event.subscribe')
class TestSubscribesTo(TestCase):
    def test_default_priority(self, mock_subscribe):
        def test_fn():pass
        res = subscribes_to('foo')(test_fn)
        mock_subscribe.assert_called_once_with('foo', test_fn, priority=100)
        self.assertTrue(res is test_fn)

    def test_custom_priority(self, mock_subscribe):
        def test_fn():pass
        res = subscribes_to('foo', priority=200)(test_fn)
        mock_subscribe.assert_called_once_with('foo', test_fn, priority=200)
        self.assertTrue(res is test_fn)


@patch.dict('src.flask_site_framework.event.event_callbacks', clear=True)
class TestPublish(TestCase):
    def test_no_args(self):
        calls = []
        def mk_testfn(n):
            def testfn(e, v):
                calls.append(n)
                return str(v) + str(n)
            return testfn
        test_fn1 = MagicMock(side_effect=mk_testfn(1))
        test_fn2 = MagicMock(side_effect=mk_testfn(2))
        test_fn3 = MagicMock(side_effect=mk_testfn(3))
        subscribe('test', test_fn1, priority=300)
        subscribe('test', test_fn2, priority=200)
        subscribe('test', test_fn3)
        res = publish('test')
        test_fn1.assert_called_once_with('test', 'None32')
        test_fn2.assert_called_once_with('test', 'None3')
        test_fn3.assert_called_once_with('test', None)
        self.assertEqual(res, 'None321')
        self.assertEqual(calls, [3, 2, 1])

    def test_with_args(self):
        calls = []
        def mk_testfn(n):
            def testfn(e, v, *a, **ka):
                calls.append(n)
                return v + [n]
            return testfn
        test_fn1 = MagicMock(side_effect=mk_testfn(1))
        test_fn2 = MagicMock(side_effect=mk_testfn(2))
        test_fn3 = MagicMock(side_effect=mk_testfn(3))
        subscribe('test', test_fn1, priority=300)
        subscribe('test', test_fn2, priority=200)
        subscribe('test', test_fn3)
        res = publish('test', [], 'foo', bar='baz')
        test_fn1.assert_called_once_with('test', [3, 2], 'foo', bar='baz')
        test_fn2.assert_called_once_with('test', [3], 'foo', bar='baz')
        test_fn3.assert_called_once_with('test', [], 'foo', bar='baz')
        self.assertEqual(res, [3, 2, 1])
        self.assertEqual(calls, [3, 2, 1])

