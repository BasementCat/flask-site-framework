from unittest import TestCase
from unittest.mock import patch, MagicMock
from contextlib import contextmanager

from flask import session

from bc_fsf_user import view
from . import mock_app, mock_blueprint, mock_user_cb, mock_real_app


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


# @contextmanager
# def mock_user_view(upd_config, *permissions, user=None, curuser=None):
#     with mock_user_cb(view, *permissions, user=user, curuser=curuser) as testview:
#         config = {
#             'SECRET_KEY': 'ljsdflk',
#             'SITE_TIMEZONE': 'America/Chicago',
#             'USERS_ALLOW_SIGNUP': True,
#             'TESTING': True,
#             'WTF_CSRF_ENABLED': False,
#         }
#         config.update(upd_config)
#         with mock_real_app(config) as app:
#             app.plugins = {'user': MagicMock}
#             with mock_blueprint(app, testview.bp) as client:
#                 yield app, client


# # TODO: patching before reimport (mock_user_view)
# @patch('bc_fsf_user.view.event')
# @patch('bc_fsf_user.view.redirect')
# @patch('bc_fsf_user.view.url_for')
# @patch('bc_fsf_user.view.flash')
# class TestView__Signup(TestCase):
#     def test_signup__get(self, mock_flash, mock_url_for, mock_redirect, mock_event):
#         with mock_user_view({}, 'signup') as (app, client):
#             res = client.get('/signup')
#             self.assertIn(b'Sign Up', res.data)

#     def test_signup__get__disabled(self, mock_flash, mock_url_for, mock_redirect, mock_event):
#         with mock_user_view({'USERS_ALLOW_SIGNUP': False}) as (app, client):
#             res = client.get('/signup')
#             self.assertIn('Location', res.headers)
#             self.assertEqual(res.headers['Location'], '/login')

#     def test_signup__missing_fields(self, mock_flash, mock_url_for, mock_redirect, mock_event):
#         with mock_user_view({}, 'signup') as (app, client):
#             data = {}
#             res = client.post('/signup', data=data)
#             self.assertNotIn(b'token is missing', res.data)
#             self.assertIn(b'field is required', res.data)

#     @patch('bc_fsf_user.forms.User')
#     def test_signup__create__exists(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event):
#         with mock_user_view({}, 'signup') as (app, client):
#             mock_user_cls.query.filter().count.return_value = 1
#             data = {
#                 'username': 'foo',
#                 'email': 'bar',
#                 'update_password': 'baz',
#                 'update_repassword': 'baz',
#                 'timezone': 'America/Chicago',
#                 'name': 'asdf',
#                 'bio': 'qwerty',
#             }
#             props = {
#                 'username': 'foo',
#                 'email': 'bar',
#                 'password': 'baz',
#                 'timezone': 'America/Chicago',
#                 'name': 'asdf',
#                 'bio': 'qwerty',
#             }
#             res = client.post('/signup', data=data)
#             self.assertNotIn(b'token is missing', res.data)
#             self.assertNotIn(b'field is required', res.data)
#             mock_event.publish.assert_not_called()
#             mock_url_for.assert_not_called()
#             mock_redirect.assert_not_called()
#             self.assertIn(b'must be unique', res.data)

#     @patch('bc_fsf_user.forms.User')
#     def test_signup__create__no_user__warn_error(self, mock_user_cls, mock_flash, mock_url_for, mock_redirect, mock_event):
#         with mock_user_view({}, 'signup') as (app, client):
#             mock_user_cls.query.filter().count.return_value = 0
#             data = {
#                 'username': 'foo',
#                 'email': 'bar',
#                 'update_password': 'baz',
#                 'update_repassword': 'baz',
#                 'timezone': 'America/Chicago',
#                 'name': 'asdf',
#                 'bio': 'qwerty',
#             }
#             props = {
#                 'username': 'foo',
#                 'email': 'bar',
#                 'password': 'baz',
#                 'timezone': 'America/Chicago',
#                 'name': 'asdf',
#                 'bio': 'qwerty',
#             }
#             mock_event.publish.return_value = (None, props, ['test warn'], ['test err'], {})
#             res = client.post('/signup', data=data)
#             # mock_event.publish.assert_called_once_with('user.create', (props, None, None))
#             self.assertNotIn(b'token is missing', res.data)
#             self.assertNotIn(b'field is required', res.data)
#             mock_event.publish.assert_not_called()
#             mock_url_for.assert_not_called()
#             mock_redirect.assert_not_called()
#             self.assertIn(b'test warn', res.data)
#             self.assertIn(b'test err', res.data)

    # def test_signup__create(self, mock_flash, mock_url_for, mock_redirect, mock_event):
    #     with mock_user_view({}, 'signup') as (app, client):
    #         pass

# def _validate_unique(self, model_field, form_field):
#             query = User.query.filter(model_field.like(form_field.data))
#             if user and user.id:
#                 query = query.filter(User.id != user.id)
#             return query.count() == 0

# @bp.route('/signup', methods=['GET', 'POST'])
# @require('user.can', 'signup')
# def signup():
#     form = UserForm(None, 'signup')
#     if form.validate_on_submit():
#         data = {
#             'username': form.username.data,
#             'email': form.email.data,
#             'password': form.update_password.data,
#             'timezone': form.timezone.data,
#             'name': form.name.data,
#             'bio': form.bio.data,
#         }
#         user, props, warnings, errors, meta = event.publish('user.create', (data, None, None))
#         for e in errors:
#             flash(e, 'danger')
#         for w in warnings:
#             flash(w, 'warn')
#         if user:
#             if current_app.config['USERS_ADMIN_APPROVAL']:
#                 flash("You will not be able to log in until an administrator approves your account", 'info')

#             if meta.get('did_email_confirmation') is True:
#                 flash("You have been sent an email to confirm your email address - please follow the instructions in the email before you can log in", 'info')
#             elif meta.get('did_email_confirmation') is False:
#                 flash("There was an error sending your confirmation email", 'danger')

#             if meta.get('did_email_confirmation') is None and not current_app.config['USERS_ADMIN_APPROVAL']:
#                 flash("Your account is created and you may now log in", 'success')

#             return redirect(url_for('.login'))

#     return render_template('user/signup.html.j2', form=form)


# class TestView__Login(TestCase):
#     pass

# # @bp.route('/login', methods=['GET', 'POST'])
# # @require('user.can', 'login', always_abort=True)
# # def login():
# #     form = LoginForm()
# #     user = form.validate_on_submit()
# #     if user:
# #         event.publish('user.login', user)
# #         # TOTP redirection done by user.can - not on this url but next
# #         return redir_after_login()
# #     elif user is None:
# #         flash("Invalid username or password", 'danger')

# #     return render_template('user/login.html.j2', form=form)

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
