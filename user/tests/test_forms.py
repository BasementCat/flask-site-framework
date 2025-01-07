from unittest import TestCase
from unittest.mock import MagicMock, patch, call

from wtforms.validators import ValidationError
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from bc_fsf_user import forms
from bc_fsf_user.process import exc
from . import mock_app, MockUser


class TestHelper(TestCase):
    def test_list_tz(self):
        tz = list(forms.list_timezones())
        self.assertGreater(len(tz), 0)
        self.assertEqual(tz[0], ('', 'Select a Timezone'))
        self.assertTrue(tz[1][0].startswith('America'))

    def test_required_if__pass__empty(self):
        mock_form = MagicMock(
            password=MagicMock(data=None, label=MagicMock(text='password')),
            repassword=MagicMock(data=None, label=MagicMock(text='repassword')),
        )
        ri = forms.ValidateRequiredIf('password')
        res = ri(mock_form, mock_form.repassword)
        self.assertIsNone(res)

    def test_required_if__pass__full(self):
        mock_form = MagicMock(
            password=MagicMock(data='foo', label=MagicMock(text='password')),
            repassword=MagicMock(data='bar', label=MagicMock(text='repassword')),
        )
        ri = forms.ValidateRequiredIf('password')
        res = ri(mock_form, mock_form.repassword)
        self.assertIsNone(res)

    def test_required_if__fail(self):
        mock_form = MagicMock(
            password=MagicMock(data='foo', label=MagicMock(text='password')),
            repassword=MagicMock(data=None, label=MagicMock(text='repassword')),
        )
        other_field = getattr(mock_form, 'password')
        ri = forms.ValidateRequiredIf('password')
        with self.assertRaisesRegex(ValidationError, 'if password is present'):
            ri(mock_form, mock_form.repassword)


@patch('bc_fsf_user.forms.User')
class TestLoginForm(TestCase):
    def test_validate__empty(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context():
            form = forms.LoginForm()
            res = form.validate_on_submit()
            self.assertFalse(res)
            mock_user_cls.query.filter.assert_not_called()
            mock_user_cls.query.filter().one.assert_not_called()
            mock_user_cls.query.first.assert_not_called()

    def test_validate__invalid_username__missing(self, mock_user_cls):
        mock_user_cls.query.filter().one.side_effect = NoResultFound
        mock_user_cls.query.first.return_value = None
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'username_or_email': 'foo', 'password': 'bar', 'submit': 'Log In'}):
            form = forms.LoginForm()
            self.assertEqual(form.username_or_email.data, 'foo')
            self.assertEqual(form.password.data, 'bar')
            res = form.validate_on_submit()
            self.assertFalse(res)
            mock_user_cls.query.filter.assert_called()
            mock_user_cls.query.filter().one.assert_called_once()
            mock_user_cls.query.first.assert_called_once()

    def test_validate__invalid_username__missing__firstuser__invalidpassword(self, mock_user_cls):
        mock_user_cls.query.filter().one.side_effect = NoResultFound
        user = MockUser(password='foo')
        mock_user_cls.query.first.return_value = user
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'username_or_email': 'foo', 'password': 'bar', 'submit': 'Log In'}):
            form = forms.LoginForm()
            self.assertEqual(form.username_or_email.data, 'foo')
            self.assertEqual(form.password.data, 'bar')
            res = form.validate_on_submit()
            self.assertFalse(res)
            mock_user_cls.query.filter.assert_called()
            mock_user_cls.query.filter().one.assert_called_once()
            mock_user_cls.query.first.assert_called_once()

    def test_validate__invalid_username__missing__firstuser__validpassword(self, mock_user_cls):
        mock_user_cls.query.filter().one.side_effect = NoResultFound
        user = MockUser(password='bar')
        mock_user_cls.query.first.return_value = user
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'username_or_email': 'foo', 'password': 'bar', 'submit': 'Log In'}):
            form = forms.LoginForm()
            self.assertEqual(form.username_or_email.data, 'foo')
            self.assertEqual(form.password.data, 'bar')
            res = form.validate_on_submit()
            self.assertFalse(res)
            mock_user_cls.query.filter.assert_called()
            mock_user_cls.query.filter().one.assert_called_once()
            mock_user_cls.query.first.assert_called_once()

    def test_validate__invalid_username__multiple(self, mock_user_cls):
        mock_user_cls.query.filter().one.side_effect = MultipleResultsFound
        user = MockUser(password='foo')
        mock_user_cls.query.first.return_value = user
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'username_or_email': 'foo', 'password': 'bar', 'submit': 'Log In'}):
            form = forms.LoginForm()
            self.assertEqual(form.username_or_email.data, 'foo')
            self.assertEqual(form.password.data, 'bar')
            res = form.validate_on_submit()
            self.assertFalse(res)
            mock_user_cls.query.filter.assert_called()
            mock_user_cls.query.filter().one.assert_called_once()
            mock_user_cls.query.first.assert_not_called()

    def test_validate__invalid_password(self, mock_user_cls):
        user = MockUser(password='foo')
        mock_user_cls.query.filter().one.return_value = user
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'username_or_email': 'foo', 'password': 'bar', 'submit': 'Log In'}):
            form = forms.LoginForm()
            self.assertEqual(form.username_or_email.data, 'foo')
            self.assertEqual(form.password.data, 'bar')
            res = form.validate_on_submit()
            self.assertFalse(res)
            mock_user_cls.query.filter.assert_called()
            mock_user_cls.query.filter().one.assert_called_once()
            mock_user_cls.query.first.assert_not_called()

    def test_validate(self, mock_user_cls):
        user = MockUser(password='bar')
        mock_user_cls.query.filter().one.return_value = user
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'username_or_email': 'foo', 'password': 'bar', 'submit': 'Log In'}):
            form = forms.LoginForm()
            self.assertEqual(form.username_or_email.data, 'foo')
            self.assertEqual(form.password.data, 'bar')
            res = form.validate_on_submit()
            self.assertTrue(res)
            mock_user_cls.query.filter.assert_called()
            mock_user_cls.query.filter().one.assert_called_once()
            mock_user_cls.query.first.assert_not_called()


@patch('bc_fsf_user.forms.totp')
class TestTOTPValidationForm__Setup(TestCase):
    def test_validate_code__not_inprogress(self, mock_totp):
        mock_totp.complete_totp_setup.side_effect = exc.ProcessNotInProgress('foo')
        user = MockUser(validate_totp=lambda c: c == '123456')
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'code': '123456'}):
            form = forms.TOTPValidationForm(user=user, setup=True)
            with self.assertRaisesRegex(ValidationError, 'foo'):
                res = form.validate_code(form.code)
            mock_totp.complete_totp_setup.assert_called_once_with(user, '123456')

    def test_validate_code__invalid_code(self, mock_totp):
        mock_totp.complete_totp_setup.side_effect = exc.InvalidCode('bar')
        user = MockUser(validate_totp=lambda c: c == '123456')
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'code': '123456'}):
            form = forms.TOTPValidationForm(user=user, setup=True)
            with self.assertRaisesRegex(ValidationError, 'bar'):
                res = form.validate_code(form.code)
            mock_totp.complete_totp_setup.assert_called_once_with(user, '123456')

    def test_validate_code(self, mock_totp):
        user = MockUser(validate_totp=lambda c: c == '123456')
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'code': '123456'}):
            form = forms.TOTPValidationForm(user=user, setup=True)
            res = form.validate_code(form.code)
            mock_totp.complete_totp_setup.assert_called_once_with(user, '123456')


class TestTOTPValidationForm__Login(TestCase):
    def test_validate_code__invalid_code(self):
        user = MockUser(validate_totp=lambda c: c == '123456')
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'code': '112233'}):
            form = forms.TOTPValidationForm(user=user)
            with self.assertRaisesRegex(ValidationError, 'Invalid code'):
                res = form.validate_code(form.code)

    def test_validate_code(self):
        user = MockUser(validate_totp=lambda c: c == '123456')
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False}) as app, app.test_request_context('/test', method="POST", data={'code': '123456'}):
            form = forms.TOTPValidationForm(user=user)
            res = form.validate_code(form.code)
            self.assertIsNone(res)


class TestUserForm(TestCase):
    def test_fields__signup(self):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock
            app.plugins = {'user': mock_user_plugin}
            form = forms.UserForm(None, 'signup')
            self.assertTrue(hasattr(form, 'username'))
            self.assertTrue(hasattr(form, 'email'))
            self.assertTrue(hasattr(form, 'update_password'))
            self.assertTrue(hasattr(form, 'update_repassword'))
            self.assertFalse(hasattr(form, 'old_password'))
            self.assertTrue(hasattr(form, 'name'))
            self.assertTrue(hasattr(form, 'bio'))
            self.assertTrue(hasattr(form, 'timezone'))
            self.assertFalse(hasattr(form, 'is_approved'))
            self.assertFalse(hasattr(form, 'is_disabled'))
            self.assertFalse(hasattr(form, 'roles'))
            self.assertFalse(hasattr(form, 'permissions'))

    def test_fields__edit(self):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock
            app.plugins = {'user': mock_user_plugin}
            mock_user = MockUser()
            form = forms.UserForm(mock_user, 'edit')
            self.assertFalse(hasattr(form, 'username'))
            self.assertTrue(hasattr(form, 'email'))
            self.assertTrue(hasattr(form, 'update_password'))
            self.assertTrue(hasattr(form, 'update_repassword'))
            self.assertTrue(hasattr(form, 'old_password'))
            self.assertTrue(hasattr(form, 'name'))
            self.assertTrue(hasattr(form, 'bio'))
            self.assertTrue(hasattr(form, 'timezone'))
            self.assertFalse(hasattr(form, 'is_approved'))
            self.assertFalse(hasattr(form, 'is_disabled'))
            self.assertFalse(hasattr(form, 'roles'))
            self.assertFalse(hasattr(form, 'permissions'))

    @patch('bc_fsf_user.forms.event')
    def test_fields__edit__admin(self, mock_event):
        mock_curuser = MagicMock()
        mock_curuser.can.return_value = True
        mock_event.publish.return_value = mock_curuser
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MockUser()
            form = forms.UserForm(mock_user, 'edit')
            self.assertTrue(hasattr(form, 'username'))
            self.assertTrue(hasattr(form, 'email'))
            self.assertTrue(hasattr(form, 'update_password'))
            self.assertTrue(hasattr(form, 'update_repassword'))
            self.assertTrue(hasattr(form, 'old_password'))
            self.assertTrue(hasattr(form, 'name'))
            self.assertTrue(hasattr(form, 'bio'))
            self.assertTrue(hasattr(form, 'timezone'))
            self.assertTrue(hasattr(form, 'is_approved'))
            self.assertTrue(hasattr(form, 'is_disabled'))
            self.assertTrue(hasattr(form, 'roles'))
            self.assertTrue(hasattr(form, 'permissions'))

    @patch('bc_fsf_user.forms.User')
    def test_validators__unique__exists__signup(self, mock_user_cls):
        mock_user_cls.query.filter().count.return_value = 1
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            form = forms.UserForm(None, 'signup')
            mock_model_field = MagicMock()
            mock_form_field = MagicMock(data='bar')
            res = form._validate_unique(mock_model_field, mock_form_field)
            self.assertFalse(res)
            mock_model_field.like.assert_called_once_with('bar')
            mock_user_cls.query.filter.assert_has_calls([
                call(),
                call(mock_model_field.like()),
            ])
            mock_user_cls.query.filter().count.assert_called_once()

    @patch('bc_fsf_user.forms.User')
    def test_validators__unique__exists__edit(self, mock_user_cls):
        mock_user_cls.query.filter().count.return_value = 1
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            mock_model_field = MagicMock()
            mock_form_field = MagicMock(data='bar')
            res = form._validate_unique(mock_model_field, mock_form_field)
            self.assertFalse(res)
            mock_model_field.like.assert_called_once_with('bar')
            mock_user_cls.query.filter.assert_has_calls([
                call(mock_model_field.like()),
                call().filter(True),
                call().filter().count(),
                call().filter().count().__eq__(0)
            ])
            mock_user_cls.query.filter().filter().count.assert_called_once()

    @patch('bc_fsf_user.forms.User')
    def test_validators__unique(self, mock_user_cls):
        mock_user_cls.query.filter().filter().count.return_value = 0
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            mock_model_field = MagicMock()
            mock_form_field = MagicMock(data='bar')
            res = form._validate_unique(mock_model_field, mock_form_field)
            self.assertTrue(res)
            mock_model_field.like.assert_called_once_with('bar')
            mock_user_cls.query.filter.assert_has_calls([
                call(),
                call().filter(),
                call(mock_model_field.like()),
                call().filter(True),
                call().filter().count(),
            ])
            mock_user_cls.query.filter().filter().count.assert_called_once()

    def test_validators__username__nousername(self):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            mock_validate_uq = MagicMock()
            form._validate_unique = mock_validate_uq
            mock_form_field = MagicMock(data='bar')
            form.validate_username(mock_form_field)
            mock_validate_uq.assert_not_called()

    @patch('bc_fsf_user.forms.User')
    def test_validators__username__withusername__exists(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            form = forms.UserForm(None, 'signup')
            mock_validate_uq = MagicMock()
            mock_validate_uq.return_value = False
            form._validate_unique = mock_validate_uq
            mock_form_field = MagicMock(data='bar')
            with self.assertRaisesRegex(ValidationError, 'Username must be unique'):
                form.validate_username(mock_form_field)
            mock_validate_uq.assert_called_once_with(mock_user_cls.username, mock_form_field)

    @patch('bc_fsf_user.forms.User')
    def test_validators__username__withusername__uq(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            form = forms.UserForm(None, 'signup')
            mock_validate_uq = MagicMock()
            mock_validate_uq.return_value = True
            form._validate_unique = mock_validate_uq
            mock_form_field = MagicMock(data='bar')
            form.validate_username(mock_form_field)
            mock_validate_uq.assert_called_once_with(mock_user_cls.username, mock_form_field)

    @patch('bc_fsf_user.forms.User')
    def test_validators__email__exists(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            form = forms.UserForm(None, 'signup')
            mock_validate_uq = MagicMock()
            mock_validate_uq.return_value = False
            form._validate_unique = mock_validate_uq
            mock_form_field = MagicMock(data='bar')
            with self.assertRaisesRegex(ValidationError, 'Email must be unique'):
                form.validate_email(mock_form_field)
            mock_validate_uq.assert_called_once_with(mock_user_cls.email, mock_form_field)

    @patch('bc_fsf_user.forms.User')
    def test_validators__email__uq(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            form = forms.UserForm(None, 'signup')
            mock_validate_uq = MagicMock()
            mock_validate_uq.return_value = True
            form._validate_unique = mock_validate_uq
            mock_form_field = MagicMock(data='bar')
            form.validate_email(mock_form_field)
            mock_validate_uq.assert_called_once_with(mock_user_cls.email, mock_form_field)


    def test_validators__old_password__no_curuser(self):
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            mock_form_field = MagicMock(data='bar')
            with self.assertRaisesRegex(ValidationError, 'No user is logged in'):
                form.validate_old_password(mock_form_field)

    @patch('bc_fsf_user.forms.event')
    def test_validators__old_password__invalid_password(self, mock_event):
        mock_curuser = MagicMock(password='foo')
        mock_event.publish.return_value = mock_curuser
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            mock_form_field = MagicMock(data='bar')
            with self.assertRaisesRegex(ValidationError, 'Password is not valid'):
                form.validate_old_password(mock_form_field)

    @patch('bc_fsf_user.forms.event')
    def test_validators__old_password(self, mock_event):
        mock_curuser = MagicMock(password='bar')
        mock_event.publish.return_value = mock_curuser
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={}, permissions={})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            mock_form_field = MagicMock(data='bar')
            res = form.validate_old_password(mock_form_field)
            self.assertIsNone(res)

    @patch('bc_fsf_user.forms.event')
    def test_init(self, mock_event):
        mock_curuser = MagicMock(password='bar')
        mock_curuser.can.return_value = False
        mock_event.publish.return_value = mock_curuser
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={'foo': {'name': 'Foo', 'description': 'Foo desc'}}, permissions={'bar': {'name': 'Bar', 'description': 'Bar desc'}})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            self.assertFalse(hasattr(form, 'roles'))
            self.assertFalse(hasattr(form, 'permissions'))
            self.assertEqual(form.timezone.default, 'America/Chicago')

    @patch('bc_fsf_user.forms.event')
    def test_init__admin(self, mock_event):
        mock_curuser = MagicMock(password='bar')
        mock_curuser.can.return_value = True
        mock_event.publish.return_value = mock_curuser
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={'foo': {'name': 'Foo', 'description': 'Foo desc'}}, permissions={'bar': {'name': 'Bar', 'description': 'Bar desc'}})
            app.plugins = {'user': mock_user_plugin}
            mock_user = MagicMock()
            form = forms.UserForm(mock_user, 'edit')
            self.assertEqual(form.permissions.choices, [('bar', 'Bar')])
            self.assertEqual(form.roles.choices, [('foo', 'Foo')])
            self.assertEqual(form.timezone.default, 'America/Chicago')

    @patch('bc_fsf_user.forms.event')
    def test_populate__signup(self, mock_event):
        mock_curuser = MagicMock(password='bar')
        mock_curuser.can.return_value = False
        mock_event.publish.return_value = mock_curuser
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app, app.test_request_context():
            mock_user_plugin = MagicMock(roles={'foo': {'name': 'Foo', 'description': 'Foo desc'}}, permissions={'bar': {'name': 'Bar', 'description': 'Bar desc'}})
            app.plugins = {'user': mock_user_plugin}
            form = forms.UserForm(None, 'signup')
            with self.assertRaisesRegex(RuntimeError, 'for signup'):
                mock_user = MagicMock()
                form.populate_obj(mock_user)

    @patch('bc_fsf_user.forms.event')
    @patch('bc_fsf_user.forms.email')
    def test_populate__edit__self(self, mock_email, mock_event):
        mock_curuser = MagicMock(password='bar')
        mock_curuser.can.return_value = False
        mock_event.publish.return_value = mock_curuser
        mock_user = MagicMock(
            username='test username 1',
            email='test email 1',
            password='test password 1',
            name='test name 1',
            is_approved=True,
            is_disabled=None,
            new_email=None,
            email_confirmation_code=None,
            email_confirmation_expiration=None,
            password_reset_code=None,
            password_reset_expiration=None,
            new_totp_secret=None,
            new_totp_backup_codes=None,
            totp_secret=None,
            totp_backup_codes=None,
            bio='test bio 1',
            roles=['test roles 1'],
            permissions=['test permissions 1'],
            timezone='test timezone 1',
        )
        formdata = dict(
            username='test username 2',
            email='test email 2',
            update_password='test password 2',
            update_repassword='test password 2',
            old_password='test password 1',
            name='test name 2',
            bio='test bio 2',
            timezone='test timezone 2',
            is_approved='',
            is_disabled='test disabled reason',
            roles=['test roles 2'],
            permissions=['test permissions 2'],
        )
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app:
            with app.test_request_context(method='POST', data=formdata):
                mock_user_plugin = MagicMock(roles={'foo': {'name': 'Foo', 'description': 'Foo desc'}}, permissions={'bar': {'name': 'Bar', 'description': 'Bar desc'}})
                app.plugins = {'user': mock_user_plugin}
                form = forms.UserForm(mock_user, 'edit')
                form.populate_obj(mock_user)
                mock_email.begin_email_confirmation.assert_called_once_with(mock_user, 'test email 2')
                self.assertEqual(mock_user.username, 'test username 1')
                self.assertEqual(mock_user.email, 'test email 1')
                self.assertEqual(mock_user.new_email, None)
                self.assertEqual(mock_user.password, 'test password 2')
                self.assertEqual(mock_user.name, 'test name 2')
                self.assertEqual(mock_user.is_approved, True)
                self.assertEqual(mock_user.is_disabled, None)
                self.assertEqual(mock_user.email_confirmation_code, None)
                self.assertEqual(mock_user.email_confirmation_expiration, None)
                self.assertEqual(mock_user.password_reset_code, None)
                self.assertEqual(mock_user.password_reset_expiration, None)
                self.assertEqual(mock_user.new_totp_secret, None)
                self.assertEqual(mock_user.new_totp_backup_codes, None)
                self.assertEqual(mock_user.totp_secret, None)
                self.assertEqual(mock_user.totp_backup_codes, None)
                self.assertEqual(mock_user.bio, 'test bio 2')
                self.assertEqual(mock_user.roles, ['test roles 1'])
                self.assertEqual(mock_user.permissions, ['test permissions 1'])
                self.assertEqual(mock_user.timezone, 'test timezone 2')

    @patch('bc_fsf_user.forms.event')
    @patch('bc_fsf_user.forms.email')
    def test_populate__edit__admin(self, mock_email, mock_event):
        mock_curuser = MagicMock(password='bar')
        mock_curuser.can.return_value = True
        mock_event.publish.return_value = mock_curuser
        mock_user = MagicMock(
            username='test username 1',
            email='test email 1',
            password='test password 1',
            name='test name 1',
            is_approved=True,
            is_disabled=None,
            new_email=None,
            email_confirmation_code=None,
            email_confirmation_expiration=None,
            password_reset_code=None,
            password_reset_expiration=None,
            new_totp_secret=None,
            new_totp_backup_codes=None,
            totp_secret=None,
            totp_backup_codes=None,
            bio='test bio 1',
            roles=['test roles 1'],
            permissions=['test permissions 1'],
            timezone='test timezone 1',
        )
        formdata = dict(
            username='test username 2',
            email='test email 2',
            update_password='test password 2',
            update_repassword='test password 2',
            old_password='test password 1',
            name='test name 2',
            bio='test bio 2',
            timezone='test timezone 2',
            is_approved='',
            is_disabled='test disabled reason',
            roles=['test roles 2'],
            permissions=['test permissions 2'],
        )
        with mock_app({'SECRET_KEY': 'alsdkfj', 'WTF_CSRF_ENABLED': False, 'SITE_TIMEZONE': 'America/Chicago'}) as app:
            with app.test_request_context(method='POST', data=formdata):
                mock_user_plugin = MagicMock(roles={'foo': {'name': 'Foo', 'description': 'Foo desc'}}, permissions={'bar': {'name': 'Bar', 'description': 'Bar desc'}})
                app.plugins = {'user': mock_user_plugin}
                form = forms.UserForm(mock_user, 'edit')
                form.populate_obj(mock_user)
                mock_email.begin_email_confirmation.assert_called_once_with(mock_user, 'test email 2')
                self.assertEqual(mock_user.username, 'test username 2')
                self.assertEqual(mock_user.email, 'test email 1')
                self.assertEqual(mock_user.new_email, None)
                self.assertEqual(mock_user.password, 'test password 2')
                self.assertEqual(mock_user.name, 'test name 2')
                self.assertEqual(mock_user.is_approved, False)
                self.assertEqual(mock_user.is_disabled, 'test disabled reason')
                self.assertEqual(mock_user.email_confirmation_code, None)
                self.assertEqual(mock_user.email_confirmation_expiration, None)
                self.assertEqual(mock_user.password_reset_code, None)
                self.assertEqual(mock_user.password_reset_expiration, None)
                self.assertEqual(mock_user.new_totp_secret, None)
                self.assertEqual(mock_user.new_totp_backup_codes, None)
                self.assertEqual(mock_user.totp_secret, None)
                self.assertEqual(mock_user.totp_backup_codes, None)
                self.assertEqual(mock_user.bio, 'test bio 2')
                self.assertEqual(mock_user.roles, ['test roles 2'])
                self.assertEqual(mock_user.permissions, ['test permissions 2'])
                self.assertEqual(mock_user.timezone, 'test timezone 2')
