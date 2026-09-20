from unittest import TestCase
from unittest.mock import patch, MagicMock, call, ANY

from flask import session, g

from flask_site_framework.user import events
from flask_site_framework.user.permissions import (
    Permission,
    Role,
)
from flask_site_framework.user.process import exc as bc_fsf_user_proc_exc

from . import mock_app, MockUser


class TestInitPermsRoles(TestCase):
    def tearDown(self):
        Permission.all_permissions = {}
        Permission.default_permissions = []
        Role.all_roles = {}
        Role.anonymous_role = None
        Role.default_roles = []

    def test_init_perms_roles(self):
        self.assertEqual(Role.all_roles, {})
        self.assertEqual(Permission.all_permissions, {})
        self.assertIsNone(Role.anonymous_role)
        with mock_app({'USERS_ALLOW_SIGNUP': True}) as app:
            events.init_perms_roles('app.loaded', app)
        self.assertGreater(len(Role.all_roles), 0)
        self.assertGreater(len(Permission.all_permissions), 0)
        self.assertIsNotNone(Role.anonymous_role)
        self.assertGreater(len(Role.default_roles), 0)


class TestLoginLogout(TestCase):
    def test_login_user(self):
        with mock_app({'SECRET_KEY': 'foo'}) as app, app.test_request_context():
            self.assertFalse(session.permanent)
            self.assertIsNone(session.get('current_user'))
            self.assertIsNone(g.get('current_user'))
            u = MockUser(id=1)
            res = events.login_user('user.login', u)
            self.assertEqual(res, u)
            self.assertTrue(session.permanent)
            self.assertEqual(session['current_user'], 1)
            self.assertEqual(g.current_user, u)

    def test_logout_user(self):
        with mock_app({'SECRET_KEY': 'foo'}) as app, app.test_request_context():
            u = MockUser(id=1)
            res = events.login_user('user.login', u)
            self.assertEqual(res, u)
            self.assertTrue(session.permanent)
            self.assertEqual(session['current_user'], 1)
            self.assertEqual(g.current_user, u)
            session['totp_login'] = True
            events.logout_user('user.logout', None)
            self.assertFalse(session.permanent)
            self.assertIsNone(session.get('current_user'))
            self.assertIsNone(session.get('totp_login'))
            self.assertIsNone(g.get('current_user'))


class TestCurrentUser(TestCase):
    @patch('flask_site_framework.user.events.User')
    def test_get_current_user__no_uid(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'foo'}) as app, app.test_request_context():
            mock_user_cls.query.get.return_value = None
            res = events.get_current_user()
            self.assertIsNone(res)
            mock_user_cls.query.get.assert_not_called()

    @patch('flask_site_framework.user.events.User')
    def test_get_current_user__bad_uid(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'foo'}) as app, app.test_request_context():
            session['current_user'] = 1
            mock_user_cls.query.get.return_value = None
            res = events.get_current_user()
            self.assertIsNone(res)
            mock_user_cls.query.get.assert_called_once_with(1)

    @patch('flask_site_framework.user.events.User')
    def test_get_current_user(self, mock_user_cls):
        with mock_app({'SECRET_KEY': 'foo'}) as app, app.test_request_context():
            session['current_user'] = 1
            user = MockUser()
            mock_user_cls.query.get.return_value = user
            res = events.get_current_user()
            self.assertEqual(res, user)
            res = events.get_current_user()
            self.assertEqual(res, user)
            mock_user_cls.query.get.assert_called_once_with(1)

    @patch('flask_site_framework.user.events.get_current_user')
    def test_get_current_tz__no_user(self, mock_get_user):
        user = None
        mock_get_user.return_value = user
        tz = events.get_current_user_timezone('jinja.dt.timezone', None)
        mock_get_user.assert_called_once()
        self.assertIsNone(tz)

    @patch('flask_site_framework.user.events.get_current_user')
    def test_get_current_tz__no_tz(self, mock_get_user):
        user = MockUser(timezone=None)
        mock_get_user.return_value = user
        tz = events.get_current_user_timezone('jinja.dt.timezone', None)
        mock_get_user.assert_called_once()
        self.assertIsNone(tz)

    @patch('flask_site_framework.user.events.get_current_user')
    def test_get_current_tz(self, mock_get_user):
        user = MockUser(timezone='America/Chicago')
        mock_get_user.return_value = user
        tz = events.get_current_user_timezone('jinja.dt.timezone', None)
        mock_get_user.assert_called_once()
        self.assertEqual(tz, 'America/Chicago')

    @patch('flask_site_framework.user.events.get_current_user')
    @patch('flask_site_framework.user.events.RoleGroup')
    def test_user_can__no_user(self, mock_rolegroup, mock_get_user):
        mock_rolegroup.for_user().check_permissions.return_value = False
        mock_get_user.return_value = None
        res = events.check_user_permission('user.can', None, 'foo')
        self.assertFalse(res)
        mock_get_user.assert_called_once()
        mock_rolegroup.for_user.assert_called_with(None)
        mock_rolegroup.for_user().check_permissions.assert_called_once_with('foo', obj=None)

    @patch('flask_site_framework.user.events.get_current_user')
    @patch('flask_site_framework.user.events.RoleGroup')
    def test_user_can__explicit_user(self, mock_rolegroup, mock_get_user):
        mock_rolegroup.for_user().check_permissions.return_value = False
        curruser = MockUser()
        euser = MockUser()
        mock_get_user.return_value = curruser
        res = events.check_user_permission('user.can', None, 'foo', user=euser)
        self.assertFalse(res)
        mock_get_user.assert_not_called()
        mock_rolegroup.for_user.assert_called_with(euser)
        mock_rolegroup.for_user().check_permissions.assert_called_once_with('foo', obj=None)

    @patch('flask_site_framework.user.events.get_current_user')
    @patch('flask_site_framework.user.events.RoleGroup')
    def test_user_can__current_user(self, mock_rolegroup, mock_get_user):
        mock_rolegroup.for_user().check_permissions.return_value = False
        curruser = MockUser()
        mock_get_user.return_value = curruser
        res = events.check_user_permission('user.can', None, 'foo')
        self.assertFalse(res)
        mock_get_user.assert_called_once()
        mock_rolegroup.for_user.assert_called_with(curruser)
        mock_rolegroup.for_user().check_permissions.assert_called_once_with('foo', obj=None)

    @patch('flask_site_framework.user.events.get_current_user')
    @patch('flask_site_framework.user.events.RoleGroup')
    def test_user_can__current_user__obj(self, mock_rolegroup, mock_get_user):
        mock_rolegroup.for_user().check_permissions.return_value = False
        curruser = MockUser()
        mock_get_user.return_value = curruser
        res = events.check_user_permission('user.can', None, 'foo', obj='bar')
        self.assertFalse(res)
        mock_get_user.assert_called_once()
        mock_rolegroup.for_user.assert_called_with(curruser)
        mock_rolegroup.for_user().check_permissions.assert_called_once_with('foo', obj='bar')


class TestAfterPermCheck__EmailConf(TestCase):
    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_email_conf_required__dest(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_VERIFY_EMAIL': True}) as app, app.test_request_context():
            user = MockUser(email_confirmation_code='foo', new_email='test@test.test')
            res = events.check_email_conf_required('user.after_permission_check', 'bar', user)
            self.assertEqual(res, 'bar')
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_email_conf_required__no_user(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_VERIFY_EMAIL': True}) as app, app.test_request_context():
            user = MockUser(email_confirmation_code='foo', new_email='test@test.test')
            res = events.check_email_conf_required('user.after_permission_check', None, user)
            self.assertIsNone(res)
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_email_conf_required__no_verify(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_VERIFY_EMAIL': False}) as app, app.test_request_context():
            user = MockUser(email_confirmation_code='foo', new_email='test@test.test')
            res = events.check_email_conf_required('user.after_permission_check', None, user)
            self.assertIsNone(res)
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_email_conf_required__no_code(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_VERIFY_EMAIL': True}) as app, app.test_request_context():
            user = MockUser(email_confirmation_code=None, new_email='test@test.test')
            res = events.check_email_conf_required('user.after_permission_check', None, user)
            self.assertIsNone(res)
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_email_conf_required__new_email(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_VERIFY_EMAIL': True}) as app, app.test_request_context():
            user = MockUser(email_confirmation_code='foo', new_email='test@test.test')
            res = events.check_email_conf_required('user.after_permission_check', None, user)
            self.assertIsNone(res)
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_email_conf_required(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_VERIFY_EMAIL': True}) as app, app.test_request_context():
            user = MockUser(email_confirmation_code='foo', new_email=None)
            res = events.check_email_conf_required('user.after_permission_check', None, user)
            mock_flash.assert_called_once_with("You must confirm your email before you can log in", 'danger')
            mock_event.publish.assert_called_once_with('user.logout')
            mock_url_for.assert_called_once_with('user.login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())


class TestAfterPermCheck__AdminApprove(TestCase):
    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_admin_approve_req__dest(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_ADMIN_APPROVAL': True}) as app, app.test_request_context():
            user = MockUser(is_disabled=False, is_approved=False)
            res = events.check_admin_approve_required('user.after_permission_check', 'bar', user)
            self.assertEqual(res, 'bar')
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_admin_approve_req__no_user(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_ADMIN_APPROVAL': True}) as app, app.test_request_context():
            user = MockUser(is_disabled=False, is_approved=False)
            res = events.check_admin_approve_required('user.after_permission_check', None, None)
            self.assertIsNone(res)
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_admin_approve_req__user_disabled(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_ADMIN_APPROVAL': True}) as app, app.test_request_context():
            user = MockUser(is_disabled=True, is_approved=False)
            res = events.check_admin_approve_required('user.after_permission_check', None, user)
            mock_flash.assert_called_once_with("Your account is disabled", 'danger')
            mock_event.publish.assert_called_once_with('user.logout')
            mock_url_for.assert_not_called()
            mock_redirect.assert_called_once_with('/')
            self.assertEqual(res, mock_redirect())

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_admin_approve_req__no_approval(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_ADMIN_APPROVAL': False}) as app, app.test_request_context():
            user = MockUser(is_disabled=False, is_approved=False)
            res = events.check_admin_approve_required('user.after_permission_check', None, user)
            self.assertIsNone(res)
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_admin_approve_req__not_approved(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_ADMIN_APPROVAL': True}) as app, app.test_request_context():
            user = MockUser(is_disabled=False, is_approved=False)
            res = events.check_admin_approve_required('user.after_permission_check', None, user)
            mock_flash.assert_called_once_with("Your account must be approved before you can log in", 'danger')
            mock_event.publish.assert_called_once_with('user.logout')
            mock_url_for.assert_called_once_with('user.login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_admin_approve_req(self, mock_url_for, mock_redirect, mock_event, mock_flash):
        with mock_app({'USERS_ADMIN_APPROVAL': True}) as app, app.test_request_context():
            user = MockUser(is_disabled=False, is_approved=True)
            res = events.check_admin_approve_required('user.after_permission_check', None, user)
            self.assertIsNone(res)
            mock_flash.assert_not_called()
            mock_event.publish.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()


class TestAfterPermCheck__TOTPSetup(TestCase):
    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__dest(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': None}) as app, app.test_request_context():
            user = MockUser(new_totp_secret=None)
            res = events.check_totp_setup_required('user.after_permission_check', 'foo', user)
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()
            self.assertEqual(res, 'foo')

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__skip_setup(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': None}) as app, app.test_request_context():
            user = MockUser(new_totp_secret=None)
            res = events.check_totp_setup_required('user.after_permission_check', None, user, skip_totp_setup=True)
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__no_user(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': None}) as app, app.test_request_context():
            user = MockUser(new_totp_secret=None)
            res = events.check_totp_setup_required('user.after_permission_check', None, None)
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__totp_disabled(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'USERS_ALLOW_TOTP': False, 'USERS_REQUIRE_TOTP': None}) as app, app.test_request_context():
            user = MockUser(new_totp_secret=None)
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__totp_setup_inprogress(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': None}) as app, app.test_request_context():
            user = MockUser(id=1, new_totp_secret='foo')
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            mock_flash.assert_called_once_with('You must complete or cancel TOTP setup before continuing', 'warning')
            mock_url_for.assert_called_once_with('user.totp_setup', user_id=1)
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__req_level_gt_user(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': 50}) as app, app.test_request_context():
            mrg = MagicMock(maxlevel=40)
            user = MockUser(id=1, new_totp_secret=None, rolegroup=mrg)
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__req_level_lte_user(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': 50}) as app, app.test_request_context():
            mrg = MagicMock(maxlevel=60)
            user = MockUser(id=1, new_totp_secret=None, rolegroup=mrg)
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            mock_flash.assert_called_once_with("You are required to set up two factor auth for your account", 'warning')
            mock_url_for.assert_called_once_with('user.totp_setup', user_id=1)
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__req_level_role_notinuser(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': 'group'}) as app, app.test_request_context():
            mrg = MagicMock()
            mrg.contains_role.return_value = False
            user = MockUser(id=1, new_totp_secret=None, rolegroup=mrg)
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            mock_url_for.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__req_level_role_inuser(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': 'group'}) as app, app.test_request_context():
            mrg = MagicMock()
            mrg.contains_role.return_value = True
            user = MockUser(id=1, new_totp_secret=None, rolegroup=mrg)
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            mock_flash.assert_called_once_with("You are required to set up two factor auth for your account", 'warning')
            mock_url_for.assert_called_once_with('user.totp_setup', user_id=1)
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__url__dfl(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': 'group'}) as app, app.test_request_context():
            mrg = MagicMock()
            mrg.contains_role.return_value = True
            user = MockUser(id=1, new_totp_secret=None, rolegroup=mrg)
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            self.assertEqual(session['url_after_login'], 'http://localhost/')

    @patch('flask_site_framework.user.events.flash')
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_check_totp_setup_req__url__set(self, mock_url_for, mock_redirect, mock_flash):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True, 'USERS_REQUIRE_TOTP': 'group'}) as app, app.test_request_context():
            mrg = MagicMock()
            mrg.contains_role.return_value = True
            user = MockUser(id=1, new_totp_secret=None, rolegroup=mrg)
            session['url_after_login'] = '/foo'
            res = events.check_totp_setup_required('user.after_permission_check', None, user)
            self.assertEqual(session['url_after_login'], '/foo')


class TestAfterPermCheck__TOTPLogin(TestCase):
    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_totp_login_required__dest(self, mock_url_for, mock_redirect):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True}) as app, app.test_request_context():
            user = MockUser(id=1, totp_secret='foo')
            res = events.check_totp_login_required('user.after_permission_check', 'foo', user)
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()
            self.assertEqual(res, 'foo')

    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_totp_login_required__no_user(self, mock_url_for, mock_redirect):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True}) as app, app.test_request_context():
            user = None
            res = events.check_totp_login_required('user.after_permission_check', None, user)
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_totp_login_required__disabled(self, mock_url_for, mock_redirect):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': False}) as app, app.test_request_context():
            user = MockUser(id=1, totp_secret='foo')
            res = events.check_totp_login_required('user.after_permission_check', None, user)
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_totp_login_required__no_secret(self, mock_url_for, mock_redirect):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True}) as app, app.test_request_context():
            user = MockUser(id=1, totp_secret=None)
            res = events.check_totp_login_required('user.after_permission_check', None, user)
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_totp_login_required__already_login(self, mock_url_for, mock_redirect):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True}) as app, app.test_request_context():
            user = MockUser(id=1, totp_secret='foo')
            session['totp_login'] = True
            res = events.check_totp_login_required('user.after_permission_check', None, user)
            mock_url_for.assert_not_called()
            mock_redirect.assert_not_called()
            self.assertIsNone(res)

    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_totp_login_required__dfl_url(self, mock_url_for, mock_redirect):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True}) as app, app.test_request_context():
            user = MockUser(id=1, totp_secret='foo')
            res = events.check_totp_login_required('user.after_permission_check', None, user)
            mock_url_for.assert_called_once_with('user.totp_login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())
            self.assertEqual(session['url_after_login'], 'http://localhost/')

    @patch('flask_site_framework.user.events.redirect')
    @patch('flask_site_framework.user.events.url_for')
    def test_totp_login_required__set_url(self, mock_url_for, mock_redirect):
        with mock_app({'SECRET_KEY': 'asdlfkj', 'USERS_ALLOW_TOTP': True}) as app, app.test_request_context():
            user = MockUser(id=1, totp_secret='foo')
            session['url_after_login'] = 'bar'
            res = events.check_totp_login_required('user.after_permission_check', None, user)
            mock_url_for.assert_called_once_with('user.totp_login')
            mock_redirect.assert_called_once_with(mock_url_for())
            self.assertEqual(res, mock_redirect())
            self.assertEqual(session['url_after_login'], 'bar')


class TestCreateUser__Data(TestCase):
    def tearDown(self):
        Permission.all_permissions = {}
        Permission.default_permissions = []
        Role.all_roles = {}
        Role.anonymous_role = None
        Role.default_roles = []

    def test_dfl__empty__noapprove(self):
        with mock_app({'SITE_TIMEZONE': 'foo', 'USERS_ALLOW_SIGNUP': True, 'USERS_ADMIN_APPROVAL': False}) as app, app.test_request_context():
            events.init_perms_roles('app.loaded', app)
            user, props, warnings, errors, meta = events.create_user_data__defaults('user.create', (None, {}, None, None, None))
            self.assertIsNone(user)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertFalse(bool(meta))
            self.assertEqual(props, {
                # NOTE: dependent upon actual default config
                'roles': ['user'],
                'permissions': [],
                'timezone': 'foo',
                'name': None,
                'is_approved': True,
                'is_disabled': None,
                'bio': None,
            })

    def test_dfl__empty__approve(self):
        with mock_app({'SITE_TIMEZONE': 'foo', 'USERS_ALLOW_SIGNUP': True, 'USERS_ADMIN_APPROVAL': True}) as app, app.test_request_context():
            events.init_perms_roles('app.loaded', app)
            user, props, warnings, errors, meta = events.create_user_data__defaults('user.create', (None, {}, None, None, None))
            self.assertIsNone(user)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertFalse(bool(meta))
            self.assertEqual(props, {
                # NOTE: dependent upon actual default config
                'roles': ['user'],
                'permissions': [],
                'timezone': 'foo',
                'name': None,
                'is_approved': False,
                'is_disabled': None,
                'bio': None,
            })

    def test_dfl__populated(self):
        with mock_app({'SITE_TIMEZONE': 'foo', 'USERS_ALLOW_SIGNUP': True}) as app, app.test_request_context():
            events.init_perms_roles('app.loaded', app)
            data = {
                'roles': ['a'],
                'permissions': ['b'],
                'timezone': 'bar',
                'name': 'testname',
                'is_approved': True,
                'is_disabled': 'reason',
                'bio': 'asdf',
            }
            user, props, warnings, errors, meta = events.create_user_data__defaults('user.create', (None, data, None, None, None))
            self.assertIsNone(user)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertFalse(bool(meta))
            self.assertEqual(props, {
                'roles': ['a'],
                'permissions': ['b'],
                'timezone': 'bar',
                'name': 'testname',
                'is_approved': True,
                'is_disabled': 'reason',
                'bio': 'asdf',
            })


class TestCreateUser__Create(TestCase):
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.User')
    @patch('flask_site_framework.user.events.db')
    def test_create__missing(self, mock_db, mock_user_cls, mock_event):
        data = {
            'username': 'testuser',
            'email': 'test@test.test',
            'password': 'testpw',
            'timezone': 'foo',
            'a': 'b',
        }
        for k in ('username', 'email', 'password', 'timezone'):
            tempdata = dict(data)
            del tempdata[k]
            user, props, warnings, errors, meta = events.create_user('user.create', (None, tempdata, None, None, None))
            self.assertIsNone(user)
            self.assertIn(f'Field {k} is required to create a user', errors)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(meta))
        mock_db.session.add.assert_not_called()
        mock_db.session.commit.assert_not_called()
        mock_user_cls.assert_not_called()

    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.User')
    @patch('flask_site_framework.user.events.db')
    def test_create(self, mock_db, mock_user_cls, mock_event):
        data = {
            'username': 'testuser',
            'email': 'test@test.test',
            'password': 'testpw',
            'timezone': 'foo',
            'a': 'b',
        }
        user, props, warnings, errors, meta = events.create_user('user.create', (None, data, None, None, None))
        mock_db.session.add.assert_called_once_with(user)
        mock_db.session.commit.assert_called_once()
        mock_user_cls.assert_called_once_with(**data)
        self.assertFalse(bool(warnings))
        self.assertFalse(bool(errors))
        self.assertFalse(bool(meta))

    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.User')
    @patch('flask_site_framework.user.events.db')
    def test_create__integrityerr(self, mock_db, mock_user_cls, mock_event):
        data = {
            'username': 'testuser',
            'email': 'test@test.test',
            'password': 'testpw',
            'timezone': 'foo',
            'a': 'b',
        }
        class MockIntErr(Exception):pass
        with patch('flask_site_framework.user.events.IntegrityError', new=MockIntErr):
            mock_db.session.commit.side_effect = MockIntErr
            user, props, warnings, errors, meta = events.create_user('user.create', (None, data, None, None, None))
            mock_db.session.add.assert_called_once_with(mock_user_cls())
            mock_db.session.commit.assert_called_once()
            mock_user_cls.assert_any_call(**data)
            self.assertIsNone(user)
            self.assertFalse(bool(warnings))
            self.assertIn('Username or email is already in use', errors)
            self.assertFalse(bool(meta))


class TestCreateUser__Setup(TestCase):
    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__no_user(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            testuser = None
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None), do_totp_setup=True)
            mock_email.begin_email_confirmation.assert_not_called()
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertIsNone(user)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': None,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__no_totp(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            testuser = MockUser()
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None), do_totp_setup=False)
            mock_email.begin_email_confirmation.assert_called_once_with(testuser)
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertEqual(user, testuser)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__totp_default(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            testuser = MockUser()
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None))
            mock_email.begin_email_confirmation.assert_called_once_with(testuser)
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertEqual(user, testuser)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__totp_default__required(self, mock_email, mock_event, mock_totp):
        with mock_app({'USERS_REQUIRE_TOTP': 5}) as app:
            testuser = MockUser(rolegroup=MagicMock(maxlevel=5))
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None))
            mock_email.begin_email_confirmation.assert_called_once_with(testuser)
            mock_totp.begin_totp_setup.assert_called_once_with(testuser, skip_confirm=None)
            self.assertEqual(user, testuser)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': True,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__totp_default__not_required(self, mock_email, mock_event, mock_totp):
        with mock_app({'USERS_REQUIRE_TOTP': 5}) as app:
            testuser = MockUser(rolegroup=MagicMock(maxlevel=4))
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None))
            mock_email.begin_email_confirmation.assert_called_once_with(testuser)
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertEqual(user, testuser)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__totp__skip_confirm(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            testuser = MockUser()
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None), do_totp_setup=True, skip_totp_confirm=True)
            mock_email.begin_email_confirmation.assert_called_once_with(testuser)
            mock_totp.begin_totp_setup.assert_called_once_with(testuser, skip_confirm=True)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': True,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__totp(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            testuser = MockUser()
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None), do_totp_setup=True)
            mock_email.begin_email_confirmation.assert_called_once_with(testuser)
            mock_totp.begin_totp_setup.assert_called_once_with(testuser, skip_confirm=None)
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': True,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__totp__ecomplete(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            testuser = MockUser()
            mock_totp.begin_totp_setup.side_effect = bc_fsf_user_proc_exc.ProcessComplete('foo')
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (testuser, {}, None, None, None), do_totp_setup=True)
            mock_email.begin_email_confirmation.assert_called_once_with(testuser)
            mock_totp.begin_totp_setup.assert_called_once_with(testuser, skip_confirm=None)
            self.assertIn('foo', warnings)
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': True,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__totp__einprogress(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            user = MockUser()
            mock_totp.begin_totp_setup.side_effect = bc_fsf_user_proc_exc.ProcessInProgress('foo')
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (user, {}, None, None, None), do_totp_setup=True)
            mock_email.begin_email_confirmation.assert_called_once_with(user)
            mock_totp.begin_totp_setup.assert_called_once_with(user, skip_confirm=None)
            self.assertFalse(bool(warnings))
            self.assertIn('foo', errors)
            self.assertEqual(meta, {
                'did_totp_setup': True,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__no_email(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            user = MockUser()
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (user, {}, None, None, None), skip_email_confirmation=True)
            mock_email.begin_email_confirmation.assert_not_called()
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': None,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__email__edisabled(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            user = MockUser()
            mock_email.begin_email_confirmation.side_effect = bc_fsf_user_proc_exc.ProcessDisabled('foo')
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (user, {}, None, None, None))
            mock_email.begin_email_confirmation.assert_called_once_with(user)
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertFalse(bool(warnings))
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': None,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__email__einprogress(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            user = MockUser()
            mock_email.begin_email_confirmation.side_effect = bc_fsf_user_proc_exc.ProcessInProgress('foo')
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (user, {}, None, None, None))
            mock_email.begin_email_confirmation.assert_called_once_with(user)
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertIn('foo', warnings)
            self.assertFalse(bool(errors))
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': True,
            })

    @patch('flask_site_framework.user.events.totp')
    @patch('flask_site_framework.user.events.event')
    @patch('flask_site_framework.user.events.email')
    def test_create__email__efailedtosend(self, mock_email, mock_event, mock_totp):
        with mock_app({}) as app:
            user = MockUser()
            mock_email.begin_email_confirmation.side_effect = bc_fsf_user_proc_exc.FailedToSendEmail('foo')
            user, props, warnings, errors, meta = events.create_user__setup('user.create', (user, {}, None, None, None))
            mock_email.begin_email_confirmation.assert_called_once_with(user)
            mock_totp.begin_totp_setup.assert_not_called()
            self.assertFalse(bool(warnings))
            self.assertIn('foo', errors)
            self.assertEqual(meta, {
                'did_totp_setup': None,
                'did_email_confirmation': False,
            })
