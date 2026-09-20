from unittest import TestCase
from unittest.mock import patch, MagicMock
import logging

from werkzeug.exceptions import NotFound, Unauthorized, Forbidden
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from flask import session

from flask_site_framework.user import user_load, user_can
from . import MockUser, MockPublish, mock_app


logging.getLogger('flask_site_framework.user').setLevel(99999)


class PluginDecUserLoadTest(TestCase):
    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__no_user_id_name(self, mock_event, mock_user_cls):
        mock_event.publish.return_value = None
        callback = MagicMock()
        callback_w = user_load()(callback)
        with self.assertRaises(NotFound):
            callback_w()
        callback.assert_not_called()
        mock_event.publish.assert_called_once_with('user.current')
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_not_called()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__user_id_and_name(self, mock_event, mock_user_cls):
        mock_event.publish.return_value = None
        mock_user_cls.query.get.return_value = None
        callback = MagicMock()
        callback_w = user_load(current=False)(callback)
        with self.assertRaises(NotFound):
            callback_w(user_id=1, username='test')
        callback.assert_not_called()
        mock_user_cls.query.get.assert_called_once_with(1)
        mock_user_cls.query.filter.assert_not_called()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__user_name(self, mock_event, mock_user_cls):
        mock_event.publish.return_value = None
        mock_user_cls.query.filter.return_value.one.side_effect = NoResultFound
        callback = MagicMock()
        callback_w = user_load(current=False)(callback)
        with self.assertRaises(NotFound):
            callback_w(username='test')
        callback.assert_not_called()
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.username.like.assert_called_once_with('test')
        mock_user_cls.email.like.assert_called_once_with('test')
        flt = mock_user_cls.username.like.return_value | mock_user_cls.email.like.return_value
        mock_user_cls.query.filter.assert_called_once_with(flt)
        mock_user_cls.query.filter.return_value.one.assert_called_once_with()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__alt_user_name_key(self, mock_event, mock_user_cls):
        mock_event.publish.return_value = None
        mock_user_cls.query.filter.return_value.one.side_effect = NoResultFound
        callback = MagicMock()
        callback_w = user_load(current=False, user_name_key='user_name')(callback)
        with self.assertRaises(NotFound):
            callback_w(user_name='test')
        callback.assert_not_called()
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.username.like.assert_called_once_with('test')
        mock_user_cls.email.like.assert_called_once_with('test')
        flt = mock_user_cls.username.like.return_value | mock_user_cls.email.like.return_value
        mock_user_cls.query.filter.assert_called_once_with(flt)
        mock_user_cls.query.filter.return_value.one.assert_called_once_with()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__alt_user_id_key(self, mock_event, mock_user_cls):
        mock_event.publish.return_value = None
        mock_user_cls.query.get.return_value = None
        callback = MagicMock()
        callback_w = user_load(current=False, user_id_key='uid')(callback)
        with self.assertRaises(NotFound):
            callback_w(uid=1)
        callback.assert_not_called()
        mock_user_cls.query.get.assert_called_once_with(1)
        mock_user_cls.query.filter.assert_not_called()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__multiple_found(self, mock_event, mock_user_cls):
        mock_event.publish.return_value = None
        mock_user_cls.query.filter.return_value.one.side_effect = MultipleResultsFound
        callback = MagicMock()
        callback_w = user_load(current=False)(callback)
        with self.assertRaises(NotFound):
            callback_w(username='test')
        callback.assert_not_called()
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.username.like.assert_called_once_with('test')
        mock_user_cls.email.like.assert_called_once_with('test')
        flt = mock_user_cls.username.like.return_value | mock_user_cls.email.like.return_value
        mock_user_cls.query.filter.assert_called_once_with(flt)
        mock_user_cls.query.filter.return_value.one.assert_called_once_with()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__no_user__no_abort(self, mock_event, mock_user_cls):
        mock_event.publish.return_value = None
        mock_user_cls.query.get.return_value = None
        callback = MagicMock()
        callback_w = user_load(current=False, abort_on_missing=False)(callback)
        res = callback_w(user_id=1)
        self.assertEqual(res, callback.return_value)
        callback.assert_called_once_with(user=None, user_id=1)
        mock_user_cls.query.get.assert_called_once_with(1)
        mock_user_cls.query.filter.assert_not_called()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__current(self, mock_event, mock_user_cls):
        user = MockUser()
        mock_event.publish.return_value = user
        mock_user_cls.query.get.return_value = None
        callback = MagicMock()
        callback_w = user_load()(callback)
        res = callback_w(user_id=1)
        self.assertEqual(res, callback.return_value)
        callback.assert_called_once_with(user=user, user_id=1)
        mock_event.publish.assert_called_once_with('user.current')
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_not_called()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load(self, mock_event, mock_user_cls):
        user = MockUser()
        mock_event.publish.return_value = None
        mock_user_cls.query.get.return_value = user
        callback = MagicMock()
        callback_w = user_load(current=False)(callback)
        res = callback_w(user_id=1)
        self.assertEqual(res, callback.return_value)
        callback.assert_called_once_with(user=user, user_id=1)
        mock_event.publish.assert_not_called()
        mock_user_cls.query.get.assert_called_once_with(1)
        mock_user_cls.query.filter.assert_not_called()

    @patch('flask_site_framework.user.User')
    @patch('flask_site_framework.user.event')
    def test_user_load__alt_user_key(self, mock_event, mock_user_cls):
        user = MockUser()
        mock_event.publish.return_value = None
        mock_user_cls.query.get.return_value = None
        mock_user_cls.query.filter.return_value.one.return_value = user
        callback = MagicMock()
        callback_w = user_load(current=False)(callback)
        res = callback_w(username='test')
        self.assertEqual(res, callback.return_value)
        callback.assert_called_once_with(user=user, username='test')
        mock_event.publish.assert_not_called()
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_called_once()


@patch('flask_site_framework.user.flash')
@patch('flask_site_framework.user.redirect')
@patch('flask_site_framework.user.url_for')
class PluginDecUserCanTest(TestCase):
    def test_user_can__no_user__valid(self, mock_url_for, mock_redirect, mock_flash):
        user = MockUser()
        callback = MagicMock()
        callback_w = user_can()(callback)
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('flask_site_framework.user.event.publish', {'user.current': None, 'user.can': True}):
            res = callback_w()
            callback.assert_called()

    def test_user_can__no_user__invalid(self, mock_url_for, mock_redirect, mock_flash):
        user = MockUser()
        callback = MagicMock()
        callback_w = user_can()(callback)
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('flask_site_framework.user.event.publish', {'user.current': None, 'user.can': False}):
            res = callback_w()
            callback.assert_not_called()
            self.assertEqual(session['url_after_login'], 'http://localhost/')
            mock_flash.assert_called_once_with('You do not have permission; please log in first', 'danger')
            mock_url_for.assert_called_once_with('user.login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    def test_user_can__no_user__required__invalid(self, mock_url_for, mock_redirect, mock_flash):
        user = MockUser()
        callback = MagicMock()
        callback_w = user_can(require_user=True)(callback)
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('flask_site_framework.user.event.publish', {'user.current': None, 'user.can': False}):
            res = callback_w()
            callback.assert_not_called()
            self.assertEqual(session['url_after_login'], 'http://localhost/')
            mock_flash.assert_called_once_with('You do not have permission; please log in first', 'danger')
            mock_url_for.assert_called_once_with('user.login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    def test_user_can__user__valid(self, mock_url_for, mock_redirect, mock_flash):
        user = MockUser()
        callback = MagicMock()
        callback_w = user_can()(callback)
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('flask_site_framework.user.event.publish', {'user.current': user, 'user.can': True}):
            res = callback_w()
            callback.assert_called()

    def test_user_can__user__valid__apc(self, mock_url_for, mock_redirect, mock_flash):
        user = MockUser()
        callback = MagicMock()
        callback_w = user_can()(callback)
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('flask_site_framework.user.event.publish', {'user.current': user, 'user.can': True, 'user.after_permission_check': 'foobar'}):
            res = callback_w()
            callback.assert_not_called()
            self.assertEqual(res, 'foobar')

    def test_user_can__user__invalid(self, mock_url_for, mock_redirect, mock_flash):
        user = MockUser()
        callback = MagicMock()
        callback_w = user_can()(callback)
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('flask_site_framework.user.event.publish', {'user.current': user, 'user.can': False}):
            with self.assertRaises(Unauthorized):
                res = callback_w()
            callback.assert_not_called()
            mock_flash.assert_not_called()
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()

    def test_user_can__user__invalid__abort(self, mock_url_for, mock_redirect, mock_flash):
        user = MockUser()
        callback = MagicMock()
        callback_w = user_can(always_abort=True)(callback)
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('flask_site_framework.user.event.publish', {'user.current': None, 'user.can': False}):
            with self.assertRaises(Forbidden):
                res = callback_w()
            callback.assert_not_called()
            mock_flash.assert_not_called()
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()
