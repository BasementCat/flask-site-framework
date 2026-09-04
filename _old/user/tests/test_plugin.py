from unittest import TestCase
from unittest.mock import patch, MagicMock
import logging

from werkzeug.exceptions import NotFound, Unauthorized, Forbidden
from sqlalchemy.exc import NoResultFound, MultipleResultsFound
from flask import session

from bc_fsf_user import UserPlugin
from . import MockUser, MockPublish, mock_app


logging.getLogger('bc_fsf_user').setLevel(99999)


class PluginDecUserLoadTest(TestCase):
    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__no_user_id_name(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={},
            )
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__user_id_and_name(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_user_cls.query.get.return_value = None
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={'user_id': 1, 'username': 'test'},
            )
        mock_user_cls.query.get.assert_called_once_with(1)
        mock_user_cls.query.filter.assert_not_called()
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__user_name(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_user_cls.query.filter().one.return_value = None
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={'username': 'test'},
            )
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_called()
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__alt_user_name_key(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_user_cls.query.filter().one.return_value = None
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={'user_name_key': 'user_name'},
                call_args=[],
                call_kwargs={'user_name': 'test'},
            )
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_called()
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__alt_user_id_key(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_user_cls.query.get.return_value = None
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={'user_id_key': 'uid'},
                call_args=[],
                call_kwargs={'uid': 1},
            )
        mock_user_cls.query.get.assert_called_once_with(1)
        mock_user_cls.query.filter.assert_not_called()
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__not_found(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_user_cls.query.filter().one.return_value = MockUser()
        mock_user_cls.query.filter().one.side_effect = NoResultFound()
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={'username': 'test'},
            )
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_called()
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__multiple_found(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_user_cls.query.filter().one.return_value = MockUser()
        mock_user_cls.query.filter().one.side_effect = MultipleResultsFound()
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={'username': 'test'},
            )
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_called()
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__no_user__no_abort(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_user_cls.query.get.return_value = None
        plugin.dec_user_load(
            callback,
            dec_args=[],
            dec_kwargs={'abort_on_missing': False},
            call_args=[],
            call_kwargs={'user_id': 1},
        )
        mock_user_cls.query.get.assert_called_once_with(1)
        mock_user_cls.query.filter.assert_not_called()
        callback.assert_called_once_with(user=None, user_id=1)

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__current__none(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        mock_event.publish.return_value = None
        with self.assertRaises(NotFound):
            plugin.dec_user_load(
                callback,
                dec_args=[],
                dec_kwargs={'current': True},
                call_args=[],
                call_kwargs={},
            )
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_not_called()
        callback.assert_not_called()

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__current(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        user = MockUser()
        mock_event.publish.return_value = user
        plugin.dec_user_load(
            callback,
            dec_args=[],
            dec_kwargs={'current': True},
            call_args=[],
            call_kwargs={},
        )
        mock_user_cls.query.get.assert_not_called()
        mock_user_cls.query.filter.assert_not_called()
        callback.assert_called_once_with(user=user)

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        user = MockUser()
        mock_user_cls.query.get.return_value = user
        plugin.dec_user_load(
            callback,
            dec_args=[],
            dec_kwargs={},
            call_args=[],
            call_kwargs={'user_id': 1},
        )
        callback.assert_called_once_with(user_id=1, user=user)

    @patch('bc_fsf_user.User')
    @patch('bc_fsf_user.event')
    def test_user_load__alt_user_key(self, mock_event, mock_user_cls):
        plugin = UserPlugin()
        callback = MagicMock()
        user = MockUser()
        mock_user_cls.query.get.return_value = user
        plugin.dec_user_load(
            callback,
            dec_args=[],
            dec_kwargs={'user_key': 'foo'},
            call_args=[],
            call_kwargs={'user_id': 1},
        )
        callback.assert_called_once_with(user_id=1, foo=user)


@patch('bc_fsf_user.flash')
@patch('bc_fsf_user.redirect')
@patch('bc_fsf_user.url_for')
class PluginDecUserCanTest(TestCase):
    def test_user_can__no_user__valid(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': None, 'user.can': True}):
            res = plugin.dec_user_can(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={},
            )
            callback.assert_called()

    def test_user_can__no_user__invalid(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': None, 'user.can': False}):
            res = plugin.dec_user_can(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={},
            )
            callback.assert_not_called()
            self.assertEqual(session['url_after_login'], 'http://localhost/')
            mock_flash.assert_called_once_with('You do not have permission; please log in first', 'danger')
            mock_url_for.assert_called_once_with('user.login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    def test_user_can__no_user__required__valid(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': None, 'user.can': True}):
            res = plugin.dec_user_can(
                callback,
                dec_args=[],
                dec_kwargs={'require_user': True},
                call_args=[],
                call_kwargs={},
            )
            callback.assert_not_called()
            self.assertEqual(session['url_after_login'], 'http://localhost/')
            mock_flash.assert_called_once_with('You do not have permission; please log in first', 'danger')
            mock_url_for.assert_called_once_with('user.login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    def test_user_can__no_user__required__invalid(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': None, 'user.can': False}):
            res = plugin.dec_user_can(
                callback,
                dec_args=[],
                dec_kwargs={'require_user': True},
                call_args=[],
                call_kwargs={},
            )
            callback.assert_not_called()
            self.assertEqual(session['url_after_login'], 'http://localhost/')
            mock_flash.assert_called_once_with('You do not have permission; please log in first', 'danger')
            mock_url_for.assert_called_once_with('user.login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    def test_user_can__user__valid(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': user, 'user.can': True}):
            res = plugin.dec_user_can(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={},
            )
            callback.assert_called()

    def test_user_can__user__valid__apc(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': user, 'user.can': True, 'user.after_permission_check': 'foobar'}):
            res = plugin.dec_user_can(
                callback,
                dec_args=[],
                dec_kwargs={},
                call_args=[],
                call_kwargs={},
            )
            callback.assert_not_called()
            self.assertEqual(res, 'foobar')

    def test_user_can__user__invalid(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': user, 'user.can': False}):
            with self.assertRaises(Unauthorized):
                res = plugin.dec_user_can(
                    callback,
                    dec_args=[],
                    dec_kwargs={},
                    call_args=[],
                    call_kwargs={},
                )
            callback.assert_not_called()
            mock_flash.assert_not_called()
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()

    def test_user_can__user__invalid__abort(self, mock_url_for, mock_redirect, mock_flash):
        plugin = UserPlugin()
        user = MockUser()
        callback = MagicMock()
        with mock_app({'SECRET_KEY': 'notsecret'}) as app, \
            app.test_request_context('/') as r, \
            app.test_client() as c, \
            MockPublish('bc_fsf_user.event.publish', {'user.current': None, 'user.can': False}):
            with self.assertRaises(Forbidden):
                res = plugin.dec_user_can(
                    callback,
                    dec_args=[],
                    dec_kwargs={'always_abort': True},
                    call_args=[],
                    call_kwargs={},
                )
            callback.assert_not_called()
            mock_flash.assert_not_called()
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()
