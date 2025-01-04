import os
from unittest import TestCase
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager
import functools
from importlib import reload

from flask import abort, redirect, url_for, session, request

from bc_fsf_user import view
from . import mock_app, mock_blueprint, mock_real_app


@contextmanager
def mock_require(module, callbacks=None, default=None):
    callbacks = callbacks or {}
    def default_callback(dec, *args, **kwargs):
        def default_impl(cb):
            return cb
        return default_impl
    default = default or default_callback

    def handle_callback(dec, *args, **kwargs):
        if dec in callbacks:
            return callbacks[dec](*args, **kwargs)
        else:
            return default(dec, *args, **kwargs)

    patch('bc_fsf_base.require', handle_callback).start()
    reload(module)
    yield module
    patch.stopall()
    reload(module)


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

    with mock_require(module, {'user.load': mock_load, 'user.can': mock_can}) as relmod:
        yield relmod


def mock_user_view(*permissions, upd_config=None, has_user=False, has_curuser=False):
    def mock_user_view_dec(callback):
        @functools.wraps(callback)
        def mock_user_view_wrap(*args, **kwargs):
            user = MagicMock() if has_user else None
            curuser = MagicMock if has_curuser else None
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
                    app.plugins = {'user': MagicMock}
                    with mock_blueprint(app, testview.bp) as client:
                        return callback(*args, app=app, client=client, user=user, curuser=curuser, **kwargs)
        return mock_user_view_wrap
    return mock_user_view_dec


@patch('bc_fsf_user.view.redirect')
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
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    def test_signup__get(self, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        res = client.get('/signup')
        self.assertIn(b'Sign Up', res.data)

    @mock_user_view()
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    def test_signup__get__disabled(self, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        res = client.get('/signup')
        self.assertIn('Location', res.headers)
        self.assertEqual(res.headers['Location'], '/login')

    @mock_user_view('signup')
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    def test_signup__missing_fields(self, mock_flash, mock_url_for, mock_redirect, mock_event, app, client, user, curuser):
        data = {}
        res = client.post('/signup', data=data)
        self.assertNotIn(b'token is missing', res.data)
        self.assertIn(b'field is required', res.data)

    @mock_user_view('signup')
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
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
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
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
        mock_event.publish.assert_called_once_with('user.create', (props, None, None))
        mock_url_for.assert_not_called()
        mock_redirect.assert_not_called()
        mock_flash.assert_has_calls([
            call('test err', 'danger'),
            call('test warn', 'warn'),
        ])

    @mock_user_view('signup')
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
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
        mock_event.publish.assert_called_once_with('user.create', (props, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("Your account is created and you may now log in", 'success'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': True})
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
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
        mock_event.publish.assert_called_once_with('user.create', (props, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You will not be able to log in until an administrator approves your account", 'info'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': True})
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
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
        mock_event.publish.assert_called_once_with('user.create', (props, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You will not be able to log in until an administrator approves your account", 'info'),
            call("You have been sent an email to confirm your email address - please follow the instructions in the email before you can log in", 'info'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': True})
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
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
        mock_event.publish.assert_called_once_with('user.create', (props, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You will not be able to log in until an administrator approves your account", 'info'),
            call("There was an error sending your confirmation email", 'danger'),
        ])

    @mock_user_view('signup', upd_config={'USERS_ADMIN_APPROVAL': False})
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redirect')
    @patch('bc_fsf_user.view.url_for')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
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
        mock_event.publish.assert_called_once_with('user.create', (props, None, None))
        mock_url_for.assert_called_once_with('.login')
        mock_redirect.assert_called_once_with(mock_url_for())
        mock_flash.assert_has_calls([
            call("You have been sent an email to confirm your email address - please follow the instructions in the email before you can log in", 'info'),
        ])



class TestView__Login(TestCase):
    @mock_user_view('login')
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redir_after_login')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
    def test_get(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.get('/login')
        self.assertIn(b'Log In', res.data)

    @mock_user_view()
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redir_after_login')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
    def test_no_perm(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.get('/login')
        self.assertEqual(res.status_code, 403)

    @mock_user_view('login')
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redir_after_login')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
    def test_no_data(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.post('/login', data={})
        self.assertIn(b'field is required', res.data)

    @mock_user_view('login')
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redir_after_login')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
    def test_invalid_data(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        res = client.post('/login', data={'username_or_email': 'foo', 'password': 'bar'})
        self.assertNotIn(b'field is required', res.data)
        mock_flash.assert_called_once_with('Invalid username or password', 'danger')

    @mock_user_view('login')
    @patch('bc_fsf_user.view.event')
    @patch('bc_fsf_user.view.redir_after_login')
    @patch('bc_fsf_user.view.flash')
    @patch('bc_fsf_user.forms.User')
    def test_login(self, mock_user_cls, mock_flash, mock_redir_login, mock_event, app, client, user, curuser):
        mock_user = MagicMock(password='bar')
        mock_user_cls.query.filter().one.return_value = mock_user
        mock_redir_login.return_value = 'foobar'
        res = client.post('/login', data={'username_or_email': 'foo', 'password': 'bar'})
        self.assertNotIn(b'field is required', res.data)
        mock_redir_login.assert_called_once_with()
        self.assertEqual(res.data, b'foobar')

# class TestView__TOTPLogin(TestCase):
#     pass

# # @bp.route('/login', methods=['GET', 'POST'])
# # @require('user.load', current=True)
# # @require('user.can', 'login', always_abort=True, obj_key='user', skip_totp_setup=True)
# # def totp_login(user, *args, **kwargs):
# #     if not (current_app.config['USERS_ALLOW_TOTP'] and user.totp_secret):
# #         return redir_after_login()
# #     form = TOTPValidationForm()
# #     if form.validate_on_submit():
# #         if user.validate_totp(form.code.data):
# #             session['totp_login'] = True
# #             return redir_after_login()
# #         else:
# #             flash("Invalid code", 'danger')

# #     return render_template('user/totp_login.html.j2', form=form)

# class TestView__Edit(TestCase):
#     pass

# # @bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
# # @require('user.load')
# # @require('user.can', 'edit_user', 'edit_other_user', 'edit_user_admin', 'edit_other_user_admin', obj_key='user')
# # def edit(user, *args, **kwargs):
# #     # User form assumes current user has at least edit_user (and user is current), or edit_other_user    
# #     form = UserForm(user, 'edit')
# #     if form.validate_on_submit():
# #         form.populate_obj(user)
# #         db.session.commit()
# #         if user.new_email:
# #             user.begin_email_confirmation(user.new_email)
# #         flash("Your changes have been saved", 'success')

# #     return render_template('user/edit.html.j2', form=form, user=user)

# class TestView__ConfirmEmail(TestCase):
#     pass

# # @bp.get('/confirm-email/<any(confirm,deny):action>/<code>')
# # def confirm_email(action, code):
# #     try:
# #         res = User.complete_email_confirmation(code, confirm=(action == 'confirm'))
# #         if res:
# #             flash("Your email address is confirmed and you may now log in.", 'success')
# #         else:
# #             flash("Your email address change has been cancelled", 'info')
# #         return redirect(url_for('.login'))
# #     except RuntimeError as e:
# #         abort(400, str(e))

# class TestView__ResetPassword(TestCase):
#     pass

# # @bp.route('/reset-password', methods=['GET', 'POST'])
# # @bp.route('/reset-password/<any(confirm,deny):any>/<code>', methods=['GET', 'POST'])
# # def reset_password(action=None, code=None):
# #     try:
# #         if action:
# #             form = PasswordResetForm()
# #             if form.validate_on_submit():
# #                 user, status = User.check_complete_password_reset(code, confirm=(action == 'confirm'))
# #                 if not status:
# #                     abort(400, "Password reset cannot be completed")
# #                 user.complete_password_reset(form.password.data)
# #                 flash("Your password has been reset and you may now log in.", 'success')
# #                 return redirect(url_for('.login'))

# #             user, status = User.check_complete_password_reset(code, confirm=(action == 'confirm'))
# #             if not status:
# #                 flash("Your password reset has been cancelled", 'info')
# #                 return redirect(url_for('.login'))

# #         else:
# #             form = PasswordResetInitForm()
# #             if form.validate_on_submit():
# #                 user = None
# #                 try:
# #                     user = User.query.filter(User.username.like(form.username_or_email.data) | User.emaijl.like(form.username_or_email.data)).one()
# #                 except NoResultFound:
# #                     pass
# #                 except MultipleResultsFound:
# #                     logger.error("Multiple users found for %s", form.username_or_email.data)
# #                 if user:
# #                     user.begin_password_reset()
# #                     return redirect(url_for('.login'))
# #                 flash("No matching user was found", 'danger')

# #         return render_template('user/reset_password.html.j2', action=action or 'init', form=form)
# #     except RuntimeError as e:
# #         abort(400, str(e))

# class TestView__TOTPSetup(TestCase):
#     pass

# # @bp.route('/edit/<int:user_id>/totp', methods=['GET', 'POST'])
# # @require('user.load')
# # @require('user.can', 'edit_user', 'edit_other_user', 'edit_user_admin', 'edit_other_user_admin', obj_key='user', skip_totp_setup=True)
# # def totp_setup(user, *args, **kwargs):
# #     if not current_app.config['USERS_ALLOW_TOTP']:
# #         abort(404)

# #     form = TOTPValidationForm()
# #     if form.validate_on_submit():
# #         try:
# #             user.complete_totp_setup(form.code.data)
# #             if user.is_logged_in:
# #                 session['totp_login'] = True
# #             flash("TOTP setup is complete", 'success')
# #             return redir_after_login()
# #         except RuntimeError as e:
# #             flash(str(e), 'danger')

# #     try:
# #         user.begin_totp_setup()
# #     except RuntimeError:
# #         # setup already in progress; use the existing data
# #         pass

# #     return render_template('user/totp_setup.html.j2', user=user)
