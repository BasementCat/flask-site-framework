import os
from unittest import TestCase
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager
import functools
from importlib import reload

from flask import abort, redirect, url_for, session, request
from sqlalchemy import exc as sql_exc

from flask_site_framework.user import view
from flask_site_framework.user.process import exc
from . import mock_app, mock_blueprint, mock_real_app


@contextmanager
def mock_user_cb(module, *permissions, user=None, curuser=None):
    def mock_load(current=False, user_key='user', abort_on_missing=True, *args, **kwargs):
        def mock_load_impl(callback):
            @functools.wraps(callback)
            def mock_load_wrap(*args, **kwargs):
                kwargs[user_key] = curuser if current else user
                if not kwargs[user_key] and abort_on_missing:
                    abort(404, "No matching user was found")
                return callback(*args, **kwargs)
            return mock_load_wrap
        return mock_load_impl

    def mock_can(*perms, always_abort=False, **kwargs):
        def mock_can_impl(callback):
            @functools.wraps(callback)
            def mock_can_wrap(*args, **kwargs):
                for p in perms:
                    if p in permissions:
                        return callback(*args, **kwargs)
                if curuser:
                    abort(401, "You do not have permission to view this page")
                else:
                    if always_abort:
                        abort(403, "You do not have permission to view this page")
                    session['url_after_login'] = request.url
                    return redirect(url_for('user.login'))
            return mock_can_wrap
        return mock_can_impl

    patch('flask_site_framework.user.user_load', mock_load).start()
    patch('flask_site_framework.user.user_can', mock_can).start()
    reload(module)
    yield module
    patch.stopall()
    reload(module)


def mock_user_view(*permissions, upd_config=None, has_user=False, has_curuser=False):
    def mock_user_view_dec(callback):
        @functools.wraps(callback)
        def mock_user_view_wrap(*args, **kwargs):
            def user_can(*perms, **kwargs):
                for p in perms:
                    if p in permissions:
                        return True
                return False
            def mk_user(val, with_perms=False):
                if val is False:
                    return None
                else:
                    if val is True:
                        val = {}
                    val.update({
                        'update_password': None,
                        'update_repassword': None,
                        'old_password': None,
                    })
                    if with_perms:
                        val['can'] = user_can
                    return MagicMock(**val)
            user = mk_user(has_user)
            curuser = mk_user(has_curuser, with_perms=True)
            with mock_user_cb(view, *permissions, user=user, curuser=curuser) as testview:
                config = {
                    'SECRET_KEY': 'ljsdflk',
                    'SITE_TIMEZONE': 'America/Chicago',
                    'USERS_ALLOW_SIGNUP': True,
                    'TESTING': True,
                    'WTF_CSRF_ENABLED': False,
                    'USERS_ADMIN_APPROVAL': False,
                }
                config.update(upd_config or {})
                with mock_real_app(config) as app:
                    app.plugins = {
                        'user': MagicMock(
                            permissions={
                                'orig perms': {'name': 'orig perms'},
                                'test perms': {'name': 'test perms'},
                            },
                            roles={
                                'orig roles': {'name': 'orig roles'},
                                'test roles': {'name': 'test roles'},
                            },
                        )
                    }
                    with mock_blueprint(app, testview.bp) as client:
                        return callback(*args, app=app, client=client, user=user, curuser=curuser, **kwargs)
        return mock_user_view_wrap
    return mock_user_view_dec


@patch('flask_site_framework.user.view.redirect')
class TestRedirAfterLogin(TestCase):
    def test_redir__empty(self, mock_redir):
        with mock_app({'SECRET_KEY': 'asdf'}) as app, app.test_request_context():
            res = view.redir_after_login()
            mock_redir.assert_called_once_with('/')
            self.assertIsNone(session.get('url_after_login'))

    def test_redir__present(self, mock_redir):
        with mock_app({'SECRET_KEY': 'asdf'}) as app, app.test_request_context():
            session['url_after_login'] = '/foo'
            res = view.redir_after_login()
            mock_redir.assert_called_once_with('/foo')
            self.assertIsNone(session.get('url_after_login'))


class TestView__Signup(TestCase):
    @mock_user_view('signup')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    def test_signup__get(self, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        res = client.get('/signup')
        self.assertIn(b'Sign Up', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    def test_signup__get__disabled(self, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        res = client.get('/signup')
        self.assertIn('Location', res.headers)
        self.assertEqual(res.headers['Location'], '/login')

    @mock_user_view('signup')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    def test_signup__missing_fields(self, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        data = {}
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertIn(b'field is required', res.data)

    @mock_user_view('signup')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_signup__create__exists(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        mock_user_cls.query.filter().count.return_value = 1
        data = {
            'username': 'foo',
            'email': 'bar',
            'update_password': 'baz',
            'update_repassword': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        props = {
            'username': 'foo',
            'email': 'bar',
            'password': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_not_called()
        mock_url_for.assert_not_called()
        mock_redirect.assert_not_called()
        self.assertIn(b'must be unique', res.data)

    @mock_user_view('signup')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_signup__create__no_user__warn_error(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        mock_user_cls.query.filter().count.return_value = 0
        data = {
            'username': 'foo',
            'email': 'bar',
            'update_password': 'baz',
            'update_repassword': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        props = {
            'username': 'foo',
            'email': 'bar',
            'password': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        mock_event.publish.return_value = (None, props, ['test warn'], ['test err'], {})
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_called_once_with('user.create', (None, props, None, None, None))
        mock_url_for.assert_not_called()
        mock_redirect.assert_not_called()
        mock_flash.assert_has_calls([
            call('test err', 'danger'),
            call('test warn', 'warn'),
        ])

    @mock_user_view('signup')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_signup__create(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        mock_user_cls.query.filter().count.return_value = 0
        data = {
            'username': 'foo',
            'email': 'bar',
            'update_password': 'baz',
            'update_repassword': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        props = {
            'username': 'foo',
            'email': 'bar',
            'password': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        cr_user = MagicMock()
        mock_event.publish.return_value = (cr_user, props, [], [], {})
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_called_once_with('user.create', (None, props, None, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("Your account is created and you may now log in", 'success'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_signup__create__admin_approval(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        mock_user_cls.query.filter().count.return_value = 0
        data = {
            'username': 'foo',
            'email': 'bar',
            'update_password': 'baz',
            'update_repassword': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        props = {
            'username': 'foo',
            'email': 'bar',
            'password': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        cr_user = MagicMock()
        mock_event.publish.return_value = (cr_user, props, [], [], {})
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_called_once_with('user.create', (None, props, None, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You will not be able to log in until an administrator approves your account", 'info'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_signup__create__email_conf__success(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        mock_user_cls.query.filter().count.return_value = 0
        data = {
            'username': 'foo',
            'email': 'bar',
            'update_password': 'baz',
            'update_repassword': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        props = {
            'username': 'foo',
            'email': 'bar',
            'password': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        cr_user = MagicMock()
        mock_event.publish.return_value = (cr_user, props, [], [], {'did_email_confirmation': True})
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_called_once_with('user.create', (None, props, None, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You will not be able to log in until an administrator approves your account", 'info'),
            call("You have been sent an email to confirm your email address - please follow the instructions in the email before you can log in", 'info'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_signup__create__email_conf__failed(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        mock_user_cls.query.filter().count.return_value = 0
        data = {
            'username': 'foo',
            'email': 'bar',
            'update_password': 'baz',
            'update_repassword': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        props = {
            'username': 'foo',
            'email': 'bar',
            'password': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        cr_user = MagicMock()
        mock_event.publish.return_value = (cr_user, props, [], [], {'did_email_confirmation': False})
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_called_once_with('user.create', (None, props, None, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You will not be able to log in until an administrator approves your account", 'info'),
            call("There was an error sending your confirmation email", 'danger'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': False})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redirect')
    @patch('flask_site_framework.user.view.url_for')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_signup__create__email_conf__no_admin(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        mock_user_cls.query.filter().count.return_value = 0
        data = {
            'username': 'foo',
            'email': 'bar',
            'update_password': 'baz',
            'update_repassword': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        props = {
            'username': 'foo',
            'email': 'bar',
            'password': 'baz',
            'timezone': 'America/Chicago',
            'name': 'asdf',
            'bio': 'qwerty',
        }
        cr_user = MagicMock()
        mock_event.publish.return_value = (cr_user, props, [], [], {'did_email_confirmation': True})
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_called_once_with('user.create', (None, props, None, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You have been sent an email to confirm your email address - please follow the instructions in the email before you can log in", 'info'),
        ])


class TestView__Login(TestCase):
    @mock_user_view('login')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_get(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.get('/login')
        self.assertIn(b'Log In', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_no_perm(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.get('/login')
        self.assertEqual(res.status_code, 403)

    @mock_user_view('login')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_no_data(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.post('/login', data={})
        self.assertIn(b'field is required', res.data)

    @mock_user_view('login')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_invalid_data(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.post('/login', data={'username_or_email': 'foo', 'password': 'bar'})
        self.assertNotIn(b'field is required', res.data)
        mock_flash.assert_called_once_with('Invalid username or password', 'danger')

    @mock_user_view('login')
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_login(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        mock_user = MagicMock(password='bar')
        mock_user_cls.query.filter().one.return_value = mock_user
        mock_redir_login.return_value = 'foobar'
        mock_event.publish.return_value = None
        res = client.post('/login', data={'username_or_email': 'foo', 'password': 'bar'})
        self.assertNotIn(b'field is required', res.data)
        mock_event.publish.assert_has_calls([
            call('user.login', mock_user),
            call('user.after_permission_check', None, mock_user),
        ])
        mock_redir_login.assert_called_once_with()
        self.assertEqual(res.data, b'foobar')


class TestView__TOTPLogin(TestCase):
    @mock_user_view('login', upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_get__no_user(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            res = client.get('/login/totp')
            self.assertEqual(res.status_code, 404)
            self.assertFalse(session.get('totp_login'))

    @mock_user_view('login', has_curuser={'totp_secret': 'foobar', 'validate_totp': lambda c: c == '123456'}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_get(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            res = client.get('/login/totp')
            self.assertIn(b'TOTP Login', res.data)

    @mock_user_view(has_curuser={'totp_secret': 'foobar', 'validate_totp': lambda c: c == '123456'}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_no_perm(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            res = client.get('/login/totp')
            self.assertEqual(res.status_code, 401)
            self.assertFalse(session.get('totp_login'))

    @mock_user_view('login', has_curuser={'totp_secret': 'foobar', 'validate_totp': lambda c: c == '123456'}, upd_config={'USERS_ALLOW_TOTP': False})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_disabled(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            mock_redir_login.return_value = 'foobar'
            res = client.get('/login/totp')
            mock_redir_login.assert_called_once_with()
            self.assertEqual(res.data, b'foobar')
            self.assertFalse(session.get('totp_login'))

    @mock_user_view('login', has_curuser={'totp_secret': None, 'validate_totp': lambda c: c == '123456'}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_no_secret(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            mock_redir_login.return_value = 'foobar'
            res = client.get('/login/totp')
            mock_redir_login.assert_called_once_with()
            self.assertEqual(res.data, b'foobar')
            self.assertFalse(session.get('totp_login'))

    @mock_user_view('login', has_curuser={'totp_secret': 'foobar', 'validate_totp': lambda c: c == '123456'}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_no_data(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            res = client.post('/login/totp', data={})
            self.assertIn(b'field is required', res.data)
            self.assertFalse(session.get('totp_login'))

    @mock_user_view('login', has_curuser={'totp_secret': 'foobar', 'validate_totp': lambda c: c == '123456'}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_invalid_data(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            res = client.post('/login/totp', data={'code': '112233'})
            self.assertIn(b'Invalid code', res.data)
            self.assertFalse(session.get('totp_login'))

    @mock_user_view('login', has_curuser={'totp_secret': 'foobar', 'validate_totp': lambda c: c == '123456'}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.event')
    @patch('flask_site_framework.user.view.redir_after_login')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    def test_success(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        with client:
            mock_redir_login.return_value = 'foobar'
            res = client.post('/login/totp', data={'code': '123456'})
            mock_redir_login.assert_called_once_with()
            self.assertEqual(res.data, b'foobar')
            self.assertTrue(session.get('totp_login'))


class TestView__Edit(TestCase):
    @mock_user_view(has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_get__no_perm(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        res = client.get('/edit/9999')
        self.assertEqual(res.status_code, 401)
        mock_flash.assert_not_called()
        mock_db.session.commit.assert_not_called()

    @mock_user_view('edit_user', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 2})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_get__perm(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        res = client.get('/edit/9999')
        self.assertEqual(res.status_code, 200)
        mock_flash.assert_not_called()
        mock_db.session.commit.assert_not_called()

    @mock_user_view('edit_user', has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__base__no_curuser(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        data = {
            'username': 'test username',
            'email': 'orig email',
            'old_password': 'orig password',
            'bio': 'test bio',
            'timezone': 'America/Denver',
            'is_approved': False,
            'is_disabled': 'test is_disabled',
            'roles': ['test roles'],
            'permissions': ['test perms'],
        }
        res = client.post('/edit/9999', data=data)
        self.assertEqual(res.status_code, 200)
        mock_flash.assert_not_called()
        mock_db.session.commit.assert_not_called()
        self.assertIn(b'user is logged in', res.data)
        self.assertEqual(user.username, 'orig username')
        self.assertEqual(user.email, 'orig email')
        self.assertEqual(user.new_email, None)
        self.assertEqual(user.password, 'orig password')
        self.assertEqual(user.bio, 'orig bio')
        self.assertEqual(user.timezone, 'America/Chicago')
        self.assertEqual(user.is_approved, True)
        self.assertEqual(user.is_disabled, None)
        self.assertEqual(user.roles, ['orig roles'])
        self.assertEqual(user.permissions, ['orig perms'])

    @mock_user_view('edit_user', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__base__missing_fields(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        mock_user_cls.query.filter().filter().count.return_value = 0
        data = {
            'username': 'test username',
            'bio': 'test bio',
            'is_approved': False,
            'is_disabled': 'test is_disabled',
            'roles': ['test roles'],
            'permissions': ['test perms'],
            'email': '',
            'timezone': '',
        }
        res = client.post('/edit/9999', data=data)
        self.assertEqual(res.status_code, 200)
        mock_flash.assert_not_called()
        mock_db.session.commit.assert_not_called()
        self.assertIn(b'field is required', res.data)
        self.assertEqual(user.username, 'orig username')
        self.assertEqual(user.email, 'orig email')
        self.assertEqual(user.new_email, None)
        self.assertEqual(user.password, 'orig password')
        self.assertEqual(user.bio, 'orig bio')
        self.assertEqual(user.timezone, 'America/Chicago')
        self.assertEqual(user.is_approved, True)
        self.assertEqual(user.is_disabled, None)
        self.assertEqual(user.roles, ['orig roles'])
        self.assertEqual(user.permissions, ['orig perms'])

    @mock_user_view('edit_user', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__base(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        mock_user_cls.query.filter().filter().count.return_value = 0
        data = {
            'username': 'test username',
            'email': 'orig email',
            'old_password': 'orig password',
            'bio': 'test bio',
            'timezone': 'America/Denver',
            'is_approved': False,
            'is_disabled': 'test is_disabled',
            'roles': ['test roles'],
            'permissions': ['test perms'],
        }
        res = client.post('/edit/9999', data=data)
        self.assertEqual(res.status_code, 200)
        mock_flash.assert_called_once_with("Your changes have been saved", 'success')
        mock_db.session.commit.assert_called_once_with()
        self.assertNotIn(b'field is required', res.data)
        self.assertEqual(user.username, 'orig username')
        self.assertEqual(user.email, 'orig email')
        self.assertEqual(user.new_email, None)
        self.assertEqual(user.password, 'orig password')
        self.assertEqual(user.bio, 'test bio')
        self.assertEqual(user.timezone, 'America/Denver')
        self.assertEqual(user.is_approved, True)
        self.assertEqual(user.is_disabled, None)
        self.assertEqual(user.roles, ['orig roles'])
        self.assertEqual(user.permissions, ['orig perms'])

    @mock_user_view('edit_user', 'edit_user_admin', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__admin__perm(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        mock_user_cls.query.filter().filter().count.return_value = 0
        data = {
            'username': 'test username',
            'email': 'orig email',
            'old_password': 'orig password',
            'bio': 'test bio',
            'timezone': 'America/Denver',
            'is_approved': '',
            'is_disabled': 'test is_disabled',
            'roles': ['test roles'],
            'permissions': ['test perms'],
        }
        res = client.post('/edit/9999', data=data)
        self.assertEqual(res.status_code, 200)
        mock_flash.assert_called_once_with("Your changes have been saved", 'success')
        mock_db.session.commit.assert_called_once_with()
        self.assertNotIn(b'field is required', res.data)
        self.assertEqual(user.username, 'test username')
        self.assertEqual(user.email, 'orig email')
        self.assertEqual(user.new_email, None)
        self.assertEqual(user.password, 'orig password')
        self.assertEqual(user.bio, 'test bio')
        self.assertEqual(user.timezone, 'America/Denver')
        self.assertEqual(user.is_approved, False)
        self.assertEqual(user.is_disabled, 'test is_disabled')
        self.assertEqual(user.roles, ['test roles'])
        self.assertEqual(user.permissions, ['test perms'])

    @mock_user_view('edit_user', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__password(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        mock_user_cls.query.filter().filter().count.return_value = 0
        data = {
            'old_password': 'orig password',
            'update_password': 'test password',
            'update_repassword': 'test password',
        }
        res = client.post('/edit/9999', data=data)
        self.assertEqual(res.status_code, 200)
        mock_flash.assert_called_once_with("Your changes have been saved", 'success')
        mock_db.session.commit.assert_called_once_with()
        self.assertNotIn(b'field is required', res.data)
        self.assertEqual(user.password, 'test password')

    @mock_user_view('edit_user', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__new_email(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        mock_user_cls.query.filter().filter().count.return_value = 0
        data = {
            'old_password': 'orig password',
            'email': 'test email',
        }
        with patch('flask_site_framework.user.forms.email.begin_email_confirmation') as mock_begin_email_conf:
            res = client.post('/edit/9999', data=data)
            self.assertEqual(res.status_code, 200)
            mock_flash.assert_called_once_with("Your changes have been saved", 'success')
            mock_db.session.commit.assert_called_once_with()
            self.assertNotIn(b'field is required', res.data)
            self.assertEqual(user.email, 'orig email')
            self.assertEqual(user.new_email, None)
            mock_begin_email_conf.assert_called_once_with(user, 'test email')

    @mock_user_view('edit_user', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__new_email__fail__inprogress(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        mock_user_cls.query.filter().filter().count.return_value = 0
        data = {
            'old_password': 'orig password',
            'email': 'test email',
        }
        with patch('flask_site_framework.user.forms.email.begin_email_confirmation') as mock_begin_email_conf:
            mock_begin_email_conf.side_effect = exc.ProcessInProgress('foobar')
            res = client.post('/edit/9999', data=data)
            self.assertEqual(res.status_code, 200)
            mock_flash.assert_has_calls([
                call("foobar", 'danger'),
                call("Your changes have been saved", 'success'),
            ])
            mock_db.session.commit.assert_called_once_with()
            self.assertNotIn(b'field is required', res.data)
            self.assertEqual(user.email, 'orig email')
            self.assertEqual(user.new_email, None)
            mock_begin_email_conf.assert_called_once_with(user, 'test email')

    @mock_user_view('edit_user', has_curuser={'id': 1, 'password': 'orig password'}, has_user={'id': 1, 'username': 'orig username', 'email': 'orig email', 'new_email': None, 'password': 'orig password', 'bio': 'orig bio', 'timezone': 'America/Chicago', 'is_approved': True, 'is_disabled': None, 'roles': ['orig roles'], 'permissions': ['orig perms']})
    @patch('flask_site_framework.user.view.db')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.forms.User')
    @patch('flask_site_framework.user.forms.event')
    def test_edit__new_email__fail__failedtosend(self, mock_event, mock_user_cls, mock_flash, mock_db, app, client, user, curuser):
        mock_event.publish.return_value = curuser
        mock_user_cls.query.filter().filter().count.return_value = 0
        data = {
            'old_password': 'orig password',
            'email': 'test email',
        }
        with patch('flask_site_framework.user.forms.email.begin_email_confirmation') as mock_begin_email_conf:
            mock_begin_email_conf.side_effect = exc.FailedToSendEmail('foobar')
            res = client.post('/edit/9999', data=data)
            self.assertEqual(res.status_code, 200)
            mock_flash.assert_has_calls([
                call("foobar", 'danger'),
                call("Your changes have been saved", 'success'),
            ])
            mock_db.session.commit.assert_called_once_with()
            self.assertNotIn(b'field is required', res.data)
            self.assertEqual(user.email, 'orig email')
            self.assertEqual(user.new_email, None)
            mock_begin_email_conf.assert_called_once_with(user, 'test email')


class TestView__ConfirmEmail(TestCase):
    @mock_user_view()
    @patch('flask_site_framework.user.view.email')
    @patch('flask_site_framework.user.view.flash')
    def test_invalid_code(self, mock_flash, mock_email, client, **kwargs):
        mock_email.complete_email_confirmation.side_effect = exc.InvalidCode('err')
        res = client.get('/confirm-email/confirm/code')
        mock_email.complete_email_confirmation.assert_called_once_with('code', confirm=True)
        mock_flash.assert_not_called()
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'err', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.email')
    @patch('flask_site_framework.user.view.flash')
    def test_inprogress(self, mock_flash, mock_email, client, **kwargs):
        mock_email.complete_email_confirmation.side_effect = exc.ProcessInProgress('err')
        res = client.get('/confirm-email/confirm/code')
        mock_email.complete_email_confirmation.assert_called_once_with('code', confirm=True)
        mock_flash.assert_not_called()
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'err', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.email')
    @patch('flask_site_framework.user.view.flash')
    def test_confirm(self, mock_flash, mock_email, client, **kwargs):
        mock_email.complete_email_confirmation.return_value = True
        res = client.get('/confirm-email/confirm/code')
        mock_email.complete_email_confirmation.assert_called_once_with('code', confirm=True)
        mock_flash.assert_called_once_with("Your email address is confirmed and you may now log in.", 'success')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers['Location'], '/login')

    @mock_user_view()
    @patch('flask_site_framework.user.view.email')
    @patch('flask_site_framework.user.view.flash')
    def test_deny(self, mock_flash, mock_email, client, **kwargs):
        mock_email.complete_email_confirmation.return_value = False
        res = client.get('/confirm-email/confirm/code')
        mock_email.complete_email_confirmation.assert_called_once_with('code', confirm=True)
        mock_flash.assert_called_once_with("Your email address change has been cancelled", 'info')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers['Location'], '/login')


class TestView__ResetPassword(TestCase):
    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_begin(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        res = client.get('/reset-password')
        mock_logger.error.assert_not_called()
        mock_user_cls.query.filter.assert_not_called()
        mock_flash.assert_not_called()
        mock_pw_proc.check_complete_password_reset.assert_not_called()
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()
        self.assertIn(b'Reset Password', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_begin_missing_data(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        res = client.post('/reset-password', data={})
        mock_logger.error.assert_not_called()
        mock_user_cls.query.filter.assert_not_called()
        mock_flash.assert_not_called()
        mock_pw_proc.check_complete_password_reset.assert_not_called()
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()
        self.assertIn(b'field is required', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_begin_no_user(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user_cls.query.filter().one.side_effect = sql_exc.NoResultFound
        res = client.post('/reset-password', data={'username_or_email': 'foobar'})
        mock_logger.error.assert_not_called()
        mock_user_cls.query.filter.assert_has_calls([
            call(),
            call(mock_user_cls.username.like().__or__()),
        ])
        mock_user_cls.query.filter().one.assert_called_once_with()
        mock_flash.assert_called_once_with("No matching user was found", 'danger')
        mock_pw_proc.check_complete_password_reset.assert_not_called()
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_begin_multiple_users(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user_cls.query.filter().one.side_effect = sql_exc.MultipleResultsFound
        res = client.post('/reset-password', data={'username_or_email': 'foobar'})
        mock_logger.error.assert_called_once_with("Multiple users found for %s", 'foobar')
        mock_user_cls.query.filter.assert_has_calls([
            call(),
            call(mock_user_cls.username.like().__or__()),
        ])
        mock_user_cls.query.filter().one.assert_called_once_with()
        mock_flash.assert_called_once_with("No matching user was found", 'danger')
        mock_pw_proc.check_complete_password_reset.assert_not_called()
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_begin_failed_to_send(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user = MagicMock()
        mock_user_cls.query.filter().one.return_value = mock_user
        mock_pw_proc.begin_password_reset.side_effect = exc.FailedToSendEmail('test failed to send')
        res = client.post('/reset-password', data={'username_or_email': 'foobar'})
        mock_logger.error.assert_not_called()
        mock_flash.assert_not_called()
        mock_pw_proc.check_complete_password_reset.assert_not_called()
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_called_once_with(mock_user)
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'test failed to send', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_begin_success(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user = MagicMock()
        mock_user_cls.query.filter().one.return_value = mock_user
        res = client.post('/reset-password', data={'username_or_email': 'foobar'})
        mock_logger.error.assert_not_called()
        mock_flash.assert_not_called()
        mock_pw_proc.check_complete_password_reset.assert_not_called()
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_called_once_with(mock_user)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers['Location'], '/login')

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_complete_invalid_code(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_pw_proc.check_complete_password_reset.side_effect = exc.InvalidCode('test inv code')
        res = client.get('/reset-password/confirm/test-code')
        mock_flash.assert_not_called()
        mock_pw_proc.check_complete_password_reset.assert_called_once_with('test-code', confirm=True)
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()
        self.assertEqual(res.status_code, 400)
        self.assertIn(b'test inv code', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_complete_deny(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user = MagicMock()
        mock_pw_proc.check_complete_password_reset.return_value = (mock_user, False)
        res = client.get('/reset-password/deny/test-code')
        mock_flash.assert_called_once_with("Your password reset has been cancelled", 'info')
        mock_pw_proc.check_complete_password_reset.assert_called_once_with('test-code', confirm=False)
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers['Location'], '/login')

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_complete_confirm__missing_data(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user = MagicMock()
        mock_pw_proc.check_complete_password_reset.return_value = (mock_user, True)
        res = client.post('/reset-password/confirm/test-code', data={})
        mock_flash.assert_not_called()
        mock_pw_proc.check_complete_password_reset.assert_called_once_with('test-code', confirm=True)
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()
        self.assertIn(b'field is required', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_complete_confirm__mismatched_pw(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user = MagicMock()
        mock_pw_proc.check_complete_password_reset.return_value = (mock_user, True)
        res = client.post('/reset-password/confirm/test-code', data={'password': 'foo', 'repassword': 'bar'})
        mock_flash.assert_not_called()
        mock_pw_proc.check_complete_password_reset.assert_called_once_with('test-code', confirm=True)
        mock_pw_proc.complete_password_reset.assert_not_called()
        mock_pw_proc.begin_password_reset.assert_not_called()
        self.assertIn(b'Both passwords must match', res.data)

    @mock_user_view()
    @patch('flask_site_framework.user.view.password')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.User')
    @patch('flask_site_framework.user.view.logger')
    def test_complete_confirm(self, mock_logger, mock_user_cls, mock_flash, mock_pw_proc, client, **kwargs):
        mock_user = MagicMock()
        mock_pw_proc.check_complete_password_reset.return_value = (mock_user, True)
        res = client.post('/reset-password/confirm/test-code', data={'password': 'foo', 'repassword': 'foo'})
        mock_flash.assert_called_once_with("Your password has been reset and you may now log in.", 'success')
        mock_pw_proc.check_complete_password_reset.assert_called_once_with('test-code', confirm=True)
        mock_pw_proc.complete_password_reset.assert_called_once_with(mock_user, 'foo')
        mock_pw_proc.begin_password_reset.assert_not_called()
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.headers['Location'], '/login')


class TestView__TOTPSetup(TestCase):
    @mock_user_view(has_user=True, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_no_perm(self, mock_redir, mock_flash, mock_totp, user, client, **kwargs):
        with client:
            res = client.get('/edit/1/totp')
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertEqual(res.status_code, 302)
            self.assertEqual(res.headers['Location'], '/login')

    @mock_user_view('edit_user', has_user=True, upd_config={'USERS_ALLOW_TOTP': False})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_disabled(self, mock_redir, mock_flash, mock_totp, user, client, **kwargs):
        with client:
            res = client.get('/edit/1/totp')
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertEqual(res.status_code, 404)

    @mock_user_view('edit_user', has_user=True, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_begin__complete(self, mock_redir, mock_flash, mock_totp, user, client, **kwargs):
        with client:
            mock_totp.begin_totp_setup.side_effect = exc.ProcessComplete
            res = client.get('/edit/1/totp')
            mock_totp.begin_totp_setup.assert_called_once_with(user)
            mock_redir.assert_called_once_with()
            self.assertEqual(res.data, b'testredir')

    @mock_user_view('edit_user', has_user=True, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_begin__inprogress(self, mock_redir, mock_flash, mock_totp, user, client, **kwargs):
        with client:
            mock_totp.begin_totp_setup.side_effect = exc.ProcessInProgress
            res = client.get('/edit/1/totp')
            mock_totp.begin_totp_setup.assert_called_once_with(user)
            mock_redir.assert_not_called()
            self.assertIn(b'TOTP Setup', res.data)

    @mock_user_view('edit_user', has_user=True, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_begin(self, mock_redir, mock_flash, mock_totp, user, client, **kwargs):
        with client:
            res = client.get('/edit/1/totp')
            mock_totp.begin_totp_setup.assert_called_once_with(user)
            mock_redir.assert_not_called()
            self.assertIn(b'TOTP Setup', res.data)
            mock_totp.get_totp_qr.assert_called_once_with(user, secret=user.new_totp_secret)

    @mock_user_view('edit_user', has_user=True, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.forms.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_complete__missing_data(self, mock_redir, mock_flash, mock_form_totp, mock_totp, user, client, **kwargs):
        with client:
            res = client.post('/edit/1/totp', data={})
            mock_redir.assert_not_called()
            mock_flash.assert_not_called()
            mock_totp.begin_totp_setup.assert_called_once_with(user)
            mock_form_totp.complete_totp_setup.assert_not_called()
            self.assertIn(b'field is required', res.data)

    @mock_user_view('edit_user', has_user=True, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.forms.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_complete__invalid_code(self, mock_redir, mock_flash, mock_form_totp, mock_totp, user, client, **kwargs):
        with client:
            mock_form_totp.complete_totp_setup.side_effect = exc.InvalidCode('test inv code')
            res = client.post('/edit/1/totp', data={'code': '123456'})
            mock_redir.assert_not_called()
            mock_flash.assert_not_called()
            mock_totp.begin_totp_setup.assert_called_once_with(user)
            mock_form_totp.complete_totp_setup.assert_called_once_with(user, '123456')
            self.assertIn(b'test inv code', res.data)

    @mock_user_view('edit_user', has_user=True, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.forms.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_complete__not_inprogress(self, mock_redir, mock_flash, mock_form_totp, mock_totp, user, client, **kwargs):
        with client:
            mock_form_totp.complete_totp_setup.side_effect = exc.ProcessNotInProgress('test not inprogress')
            res = client.post('/edit/1/totp', data={'code': '123456'})
            mock_redir.assert_not_called()
            mock_flash.assert_not_called()
            mock_totp.begin_totp_setup.assert_called_once_with(user)
            mock_form_totp.complete_totp_setup.assert_called_once_with(user, '123456')
            self.assertIn(b'test not inprogress', res.data)

    @mock_user_view('edit_user', has_user={'is_logged_in': False}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.forms.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_complete__user_notloggedin(self, mock_redir, mock_flash, mock_form_totp, mock_totp, user, client, **kwargs):
        with client:
            res = client.post('/edit/1/totp', data={'code': '123456'})
            mock_redir.assert_called_once_with()
            mock_flash.assert_called_once_with("TOTP setup is complete", 'success')
            mock_totp.begin_totp_setup.assert_not_called()
            mock_form_totp.complete_totp_setup.assert_called_once_with(user, '123456')
            self.assertIsNone(session.get('totp_login'))
            self.assertEqual(res.data, b'testredir')

    @mock_user_view('edit_user', has_user={'is_logged_in': True}, upd_config={'USERS_ALLOW_TOTP': True})
    @patch('flask_site_framework.user.view.totp')
    @patch('flask_site_framework.user.forms.totp')
    @patch('flask_site_framework.user.view.flash')
    @patch('flask_site_framework.user.view.redir_after_login', return_value='testredir')
    def test_complete(self, mock_redir, mock_flash, mock_form_totp, mock_totp, user, client, **kwargs):
        with client:
            res = client.post('/edit/1/totp', data={'code': '123456'})
            mock_redir.assert_called_once_with()
            mock_flash.assert_called_once_with("TOTP setup is complete", 'success')
            mock_totp.begin_totp_setup.assert_not_called()
            mock_form_totp.complete_totp_setup.assert_called_once_with(user, '123456')
            self.assertTrue(session.get('totp_login'))
            self.assertEqual(res.data, b'testredir')
