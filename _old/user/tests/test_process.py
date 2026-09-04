from unittest import TestCase
from unittest.mock import patch, ANY, call

import arrow
import qrcode

from . import mock_app, MockUser
from bc_fsf_user.process import exc, email, password, totp


class ProcessEmailBeginTest(TestCase):
    def test_begin_email_confirmation__disabled(self):
        with mock_app({'USERS_VERIFY_EMAIL': False}):
            user = MockUser()
            with self.assertRaises(exc.ProcessDisabled):
                email.begin_email_confirmation(user)

    @patch('bc_fsf_user.process.email.url_for')
    @patch('bc_fsf_user.process.email.db')
    def test_begin_email_confirmation__disabled__new(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EMAIL': False, 'USERS_VERIFY_EXPIRATION': 3600}):
            user = MockUser()
            email.begin_email_confirmation(user, new_email='foo@bar.baz')
            self.assertIsNotNone(user.email_confirmation_code)
            self.assertIsNotNone(user.email_confirmation_expiration)

    @patch('bc_fsf_user.process.email.url_for')
    @patch('bc_fsf_user.process.email.db')
    def test_begin_email_confirmation(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EMAIL': True, 'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            email.begin_email_confirmation(user)
            self.assertIsNotNone(user.email_confirmation_code)
            self.assertIsNotNone(user.email_confirmation_expiration)
            self.assertIsNone(user.new_email)
            mock_db.session.commit.assert_called_once()
            subject = 'Test Site email address confirmation'
            app.plugins['email'].create.assert_called_once_with(subject, to=['test@test.test'])
            app.plugins['email'].create().render.assert_called_once_with(
                'user/email_confirmation',
                subject=subject,
                user=user,
                old_email='test@test.test',
                new_email=None,
                code=user.email_confirmation_code,
                expires=user.email_confirmation_expiration,
                confirm_url=ANY,
                deny_url=ANY,
            )
            app.plugins['email'].create().render().send_message.assert_called_once()
            mock_url_for.assert_has_calls([
                call('user.confirm_email', code=user.email_confirmation_code, action='confirm', _external=True),
                call('user.confirm_email', code=user.email_confirmation_code, action='deny', _external=True),
            ])

    @patch('bc_fsf_user.process.email.url_for')
    @patch('bc_fsf_user.process.email.db')
    def test_begin_email_confirmation__new__change_in_progress(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EMAIL': True, 'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            user.email_confirmation_code = 'foo'
            user.new_email = 'foo@bar.baz'
            with self.assertRaisesRegex(exc.ProcessInProgress, r'in progress'):
                email.begin_email_confirmation(user, new_email='a@b.c')

    @patch('bc_fsf_user.process.email.url_for')
    @patch('bc_fsf_user.process.email.db')
    def test_begin_email_confirmation__new__original_unconfirmed(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EMAIL': True, 'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            user.email_confirmation_code = 'foo'
            with self.assertRaisesRegex(exc.ProcessInProgress, r'not confirmed'):
                email.begin_email_confirmation(user, new_email='a@b.c')

    @patch('bc_fsf_user.process.email.url_for')
    @patch('bc_fsf_user.process.email.db')
    def test_begin_email_confirmation__new(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EMAIL': True, 'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            email.begin_email_confirmation(user, new_email='foo@bar.baz')
            self.assertIsNotNone(user.email_confirmation_code)
            self.assertIsNotNone(user.email_confirmation_expiration)
            self.assertEqual(user.new_email, 'foo@bar.baz')
            mock_db.session.commit.assert_called_once()
            subject = 'Test Site email address confirmation'
            app.plugins['email'].create.assert_called_once_with(subject, to=['test@test.test'])
            app.plugins['email'].create().render.assert_called_once_with(
                'user/email_confirmation',
                subject=subject,
                user=user,
                old_email='test@test.test',
                new_email='foo@bar.baz',
                code=user.email_confirmation_code,
                expires=user.email_confirmation_expiration,
                confirm_url=ANY,
                deny_url=ANY,
            )
            app.plugins['email'].create().render().send_message.assert_called_once()
            mock_url_for.assert_has_calls([
                call('user.confirm_email', code=user.email_confirmation_code, action='confirm', _external=True),
                call('user.confirm_email', code=user.email_confirmation_code, action='deny', _external=True),
            ])

    @patch('bc_fsf_user.process.email.url_for')
    @patch('bc_fsf_user.process.email.db')
    def test_begin_email_confirmation__new__same_email(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EMAIL': True, 'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            email.begin_email_confirmation(user, new_email='foo@bar.baz')
            code_1 = user.email_confirmation_code
            expires_1 = user.email_confirmation_expiration
            email.begin_email_confirmation(user, new_email='foo@bar.baz')
            self.assertIsNotNone(user.email_confirmation_code)
            self.assertIsNotNone(user.email_confirmation_expiration)
            self.assertEqual(user.new_email, 'foo@bar.baz')
            self.assertEqual(mock_db.session.commit.call_count, 2)
            self.assertEqual(app.plugins['email'].create.call_count, 2)
            self.assertEqual(app.plugins['email'].create().render.call_count, 2)
            self.assertEqual(app.plugins['email'].create().render().send_message.call_count, 2)

    @patch('bc_fsf_user.process.email.url_for')
    @patch('bc_fsf_user.process.email.db')
    def test_begin_email_confirmation__failed_to_send(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EMAIL': True, 'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            app.plugins['email'].create().render().send_message.side_effect = Exception("send fail")
            with self.assertRaises(exc.FailedToSendEmail):
                email.begin_email_confirmation(user)


class ProcessEmailCompleteTest(TestCase):
    @patch('bc_fsf_user.process.email.db')
    @patch('bc_fsf_user.process.email.User')
    def test_complete_email_confirmation__no_user(self, mock_user_cls, mock_db):
        with mock_app({}):
            user = MockUser(email_confirmation_code='foo', email_confirmation_expiration=arrow.utcnow().shift(seconds=300))
            mock_user_cls.query.filter().first.return_value = None
            with self.assertRaisesRegex(exc.InvalidCode, 'is invalid'):
                email.complete_email_confirmation('foo', confirm=True)
            mock_user_cls.query.filter.assert_called()
            mock_user_cls.query.filter().first.assert_called_once()

    @patch('bc_fsf_user.process.email.db')
    @patch('bc_fsf_user.process.email.User')
    def test_complete_email_confirmation__no_exp(self, mock_user_cls, mock_db):
        with mock_app({}):
            user = MockUser(email_confirmation_code='foo', email_confirmation_expiration=None)
            mock_user_cls.query.filter().first.return_value = user
            with self.assertRaisesRegex(exc.InvalidCode, 'has expired'):
                email.complete_email_confirmation('foo', confirm=True)

    @patch('bc_fsf_user.process.email.db')
    @patch('bc_fsf_user.process.email.User')
    def test_complete_email_confirmation__expired_code(self, mock_user_cls, mock_db):
        with mock_app({}):
            user = MockUser(email_confirmation_code='foo', email_confirmation_expiration=arrow.utcnow().shift(seconds=-300))
            mock_user_cls.query.filter().first.return_value = user
            with self.assertRaisesRegex(exc.InvalidCode, 'has expired'):
                email.complete_email_confirmation('foo', confirm=True)

    @patch('bc_fsf_user.process.email.db')
    @patch('bc_fsf_user.process.email.User')
    def test_complete_email_confirmation__deny_orig_fail(self, mock_user_cls, mock_db):
        with mock_app({}):
            user = MockUser(email_confirmation_code='foo', email_confirmation_expiration=arrow.utcnow().shift(seconds=300))
            mock_user_cls.query.filter().first.return_value = user
            with self.assertRaisesRegex(exc.ProcessInProgress, 'cannot be denied'):
                email.complete_email_confirmation('foo', confirm=False)

    @patch('bc_fsf_user.process.email.db')
    @patch('bc_fsf_user.process.email.User')
    def test_complete_email_confirmation__confirm_orig(self, mock_user_cls, mock_db):
        with mock_app({}):
            user = MockUser(email_confirmation_code='foo', email_confirmation_expiration=arrow.utcnow().shift(seconds=300))
            mock_user_cls.query.filter().first.return_value = user
            res = email.complete_email_confirmation('foo', confirm=True)
            self.assertTrue(res)
            self.assertIsNone(user.email_confirmation_code)
            self.assertIsNone(user.email_confirmation_expiration)
            self.assertIsNone(user.new_email)
            mock_db.session.commit.assert_called_once()

    @patch('bc_fsf_user.process.email.db')
    @patch('bc_fsf_user.process.email.User')
    def test_complete_email_confirmation__deny_new(self, mock_user_cls, mock_db):
        with mock_app({}):
            user = MockUser(email_confirmation_code='foo', email_confirmation_expiration=arrow.utcnow().shift(seconds=300), new_email='foo@bar.baz')
            mock_user_cls.query.filter().first.return_value = user
            res = email.complete_email_confirmation('foo', confirm=False)
            self.assertFalse(res)
            self.assertIsNone(user.email_confirmation_code)
            self.assertIsNone(user.email_confirmation_expiration)
            self.assertIsNone(user.new_email)
            mock_db.session.commit.assert_called_once()
            self.assertEqual(user.email, 'test@test.test')

    @patch('bc_fsf_user.process.email.db')
    @patch('bc_fsf_user.process.email.User')
    def test_complete_email_confirmation__confirm_new(self, mock_user_cls, mock_db):
        with mock_app({}):
            user = MockUser(email_confirmation_code='foo', email_confirmation_expiration=arrow.utcnow().shift(seconds=300), new_email='foo@bar.baz')
            mock_user_cls.query.filter().first.return_value = user
            res = email.complete_email_confirmation('foo', confirm=True)
            self.assertTrue(res)
            self.assertIsNone(user.email_confirmation_code)
            self.assertIsNone(user.email_confirmation_expiration)
            self.assertIsNone(user.new_email)
            mock_db.session.commit.assert_called_once()
            self.assertEqual(user.email, 'foo@bar.baz')


class ProcessPasswordBeginTest(TestCase):
    @patch('bc_fsf_user.process.password.url_for')
    @patch('bc_fsf_user.process.password.db')
    def test_begin_password_reset(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            password.begin_password_reset(user)
            self.assertIsNotNone(user.password_reset_code)
            self.assertIsNotNone(user.password_reset_expiration)
            mock_db.session.commit.assert_called_once()
            subject = 'Test Site password reset'
            app.plugins['email'].create.assert_called_once_with(subject, to=['test@test.test'])
            app.plugins['email'].create().render.assert_called_once_with(
                'user/password_reset',
                subject=subject,
                user=user,
                code=user.password_reset_code,
                expires=user.password_reset_expiration,
                confirm_url=ANY,
                deny_url=ANY,
            )
            app.plugins['email'].create().render().send_message.assert_called_once()
            mock_url_for.assert_has_calls([
                call('user.reset_password', code=user.password_reset_code, action='confirm', _external=True),
                call('user.reset_password', code=user.password_reset_code, action='deny', _external=True),
            ])

    @patch('bc_fsf_user.process.password.url_for')
    @patch('bc_fsf_user.process.password.db')
    def test_begin_password_reset__failed_to_send(self, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            app.plugins['email'].create().render().send_message.side_effect = Exception("send fail")
            with self.assertRaises(exc.FailedToSendEmail):
                password.begin_password_reset(user)


class ProcessPasswordCheckTest(TestCase):
    @patch('bc_fsf_user.process.password.url_for')
    @patch('bc_fsf_user.process.password.db')
    @patch('bc_fsf_user.process.password.User')
    def test_check_password_reset__invalid(self, mock_user_cls, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            mock_user_cls.query.filter().first.return_value = None
            with self.assertRaisesRegex(exc.InvalidCode, 'is invalid'):
                password.check_complete_password_reset('foo', confirm=True)

    @patch('bc_fsf_user.process.password.url_for')
    @patch('bc_fsf_user.process.password.db')
    @patch('bc_fsf_user.process.password.User')
    def test_check_password_reset__expired(self, mock_user_cls, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(password_reset_code='foo', password_reset_expiration=arrow.utcnow().shift(seconds=-300))
            mock_user_cls.query.filter().first.return_value = user
            with self.assertRaisesRegex(exc.InvalidCode, 'has expired'):
                password.check_complete_password_reset('foo', confirm=True)

    @patch('bc_fsf_user.process.password.url_for')
    @patch('bc_fsf_user.process.password.db')
    @patch('bc_fsf_user.process.password.User')
    def test_check_password_reset__confirm(self, mock_user_cls, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(password_reset_code='foo', password_reset_expiration=arrow.utcnow().shift(seconds=300))
            mock_user_cls.query.filter().first.return_value = user
            ruser, rres = password.check_complete_password_reset('foo', confirm=True)
            self.assertEqual(ruser, user)
            self.assertEqual(rres, True)
            self.assertTrue(bool(user.password_reset_code))
            self.assertTrue(bool(user.password_reset_expiration))

    @patch('bc_fsf_user.process.password.url_for')
    @patch('bc_fsf_user.process.password.db')
    @patch('bc_fsf_user.process.password.User')
    def test_check_password_reset__confirm(self, mock_user_cls, mock_db, mock_url_for):
        with mock_app({'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(password_reset_code='foo', password_reset_expiration=arrow.utcnow().shift(seconds=300))
            mock_user_cls.query.filter().first.return_value = user
            ruser, rres = password.check_complete_password_reset('foo', confirm=False)
            self.assertEqual(ruser, user)
            self.assertEqual(rres, False)
            self.assertIsNone(user.password_reset_code)
            self.assertIsNone(user.password_reset_expiration)


class ProcessPasswordCompleteTest(TestCase):
    @patch('bc_fsf_user.process.password.db')
    def test_check_password_reset__confirm(self, mock_db):
        with mock_app({'USERS_VERIFY_EXPIRATION': 3600, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(password_reset_code='foo', password_reset_expiration=arrow.utcnow().shift(seconds=300))
            password.complete_password_reset(user, 'newpass')
            self.assertIsNone(user.password_reset_code)
            self.assertIsNone(user.password_reset_expiration)
            self.assertEqual(user.password, 'newpass')
            mock_db.session.commit.assert_called_once()


class ProcessTOTPGenerateBackupCodesTest(TestCase):
    def test_generate_backup_codes__default(self):
        codes = list(totp.generate_otp_backup_codes())
        self.assertEqual(len(codes), 12)
        self.assertEqual(set((len(c) for c in codes)), {11})

    def test_generate_backup_codes__args(self):
        codes = list(totp.generate_otp_backup_codes(count=20, digits=12))
        self.assertEqual(len(codes), 20)
        self.assertEqual(set((len(c) for c in codes)), {15})

    def test_generate_backup_codes__invalid_count(self):
        with self.assertRaises(AssertionError):
            codes = list(totp.generate_otp_backup_codes(count=0))

    def test_generate_backup_codes__invalid_digit_count_low(self):
        with self.assertRaises(AssertionError):
            codes = list(totp.generate_otp_backup_codes(digits=3))

    def test_generate_backup_codes__invalid_digit_count_div(self):
        with self.assertRaises(AssertionError):
            codes = list(totp.generate_otp_backup_codes(digits=10))


class ProcessTOTPBeginSetupTest(TestCase):
    @patch('bc_fsf_user.process.totp.db')
    def test_begin_totp_setup__not_allowed(self, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': False}) as app:
            user = MockUser()
            totp.begin_totp_setup(user)
            self.assertIsNone(user.new_totp_secret)
            self.assertIsNone(user.totp_secret)
            self.assertIsNone(user.totp_backup_codes)
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    def test_begin_totp_setup__setup_in_progress(self, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser(new_totp_secret='foo')
            with self.assertRaises(exc.ProcessInProgress):
                totp.begin_totp_setup(user)
            self.assertEqual(user.new_totp_secret, 'foo')
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    def test_begin_totp_setup__setup_in_progress__force(self, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser(new_totp_secret='foo')
            totp.begin_totp_setup(user, force=True)
            self.assertNotEqual(user.new_totp_secret, 'foo')
            self.assertIsNotNone(user.new_totp_secret)
            self.assertIsNone(user.totp_secret)
            self.assertIsNotNone(user.new_totp_backup_codes)
            mock_db.session.commit.assert_called_once()

    @patch('bc_fsf_user.process.totp.db')
    def test_begin_totp_setup__skip__already_set_up(self, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser(totp_secret='foo')
            with self.assertRaises(exc.ProcessComplete):
                totp.begin_totp_setup(user, skip_confirm=True)
            self.assertIsNone(user.new_totp_secret)
            self.assertEqual(user.totp_secret, 'foo')
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    def test_begin_totp_setup__skip__new(self, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser()
            totp.begin_totp_setup(user, skip_confirm=True)
            self.assertIsNone(user.new_totp_secret)
            self.assertIsNone(user.new_totp_backup_codes)
            self.assertIsNotNone(user.totp_secret)
            self.assertIsNotNone(user.totp_backup_codes)
            mock_db.session.commit.assert_called_once()

    @patch('bc_fsf_user.process.totp.db')
    def test_begin_totp_setup__normal(self, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser()
            totp.begin_totp_setup(user)
            self.assertIsNone(user.totp_secret)
            self.assertIsNone(user.totp_backup_codes)
            self.assertIsNotNone(user.new_totp_secret)
            self.assertIsNotNone(user.new_totp_backup_codes)
            mock_db.session.commit.assert_called_once()


class ProcessTOTPCompleteSetupTest(TestCase):
    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.validate_totp')
    def test_complete_totp_setup__no_new_secret(self, mock_validate_totp, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser()
            with self.assertRaises(exc.ProcessNotInProgress):
                totp.complete_totp_setup(user, '123456')
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.validate_totp')
    def test_complete_totp_setup__invalid_code(self, mock_validate_totp, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser(new_totp_secret='foo')
            mock_validate_totp.return_value = False
            with self.assertRaises(exc.InvalidCode):
                totp.complete_totp_setup(user, '123456')
            mock_validate_totp.assert_called_once_with(user, '123456', secret='foo', backup=False)
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.validate_totp')
    def test_complete_totp_setup__normal(self, mock_validate_totp, mock_db):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser(new_totp_secret='foo', new_totp_backup_codes='bar')
            mock_validate_totp.return_value = True
            totp.complete_totp_setup(user, '123456')
            mock_validate_totp.assert_called_once_with(user, '123456', secret='foo', backup=False)
            mock_db.session.commit.assert_called_once()
            self.assertIsNone(user.new_totp_secret)
            self.assertIsNone(user.new_totp_backup_codes)
            self.assertEqual(user.totp_secret, 'foo')
            self.assertEqual(user.totp_backup_codes, 'bar')


class ProcessTOTPGetTOTPTest(TestCase):
    @patch('pyotp.TOTP')
    def test_get_totp__no_secret(self, mock_totp):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser()
            res = totp.get_totp(user)
            self.assertIsNone(res)
            mock_totp.assert_not_called()

    @patch('pyotp.TOTP')
    def test_get_totp__user_secret(self, mock_totp):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser(totp_secret='foo')
            res = totp.get_totp(user)
            self.assertIsNotNone(res)
            mock_totp.assert_called_once_with('foo')

    @patch('pyotp.TOTP')
    def test_get_totp__provided_secret(self, mock_totp):
        with mock_app({'USERS_ALLOW_TOTP': True}) as app:
            user = MockUser(totp_secret='foo')
            res = totp.get_totp(user, secret='bar')
            self.assertIsNotNone(res)
            mock_totp.assert_called_once_with('bar')


class ProcessTOTPGetTOTPURITest(TestCase):
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_get_totp_uri__no_secret(self, mock_get_totp):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            mock_get_totp.return_value = None
            res = totp.get_totp_uri(user)
            self.assertIsNone(res)
            mock_get_totp.assert_called_once_with(user, secret=None)
            mock_get_totp.provisioning_uri.assert_not_called()

    @patch('bc_fsf_user.process.totp.get_totp')
    def test_get_totp_uri__no_valid_secret(self, mock_get_totp):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(totp_secret='foo')
            mock_get_totp.return_value = None
            res = totp.get_totp_uri(user)
            self.assertIsNone(res)
            mock_get_totp.assert_called_once_with(user, secret=None)
            mock_get_totp.provisioning_uri.assert_not_called()

    @patch('bc_fsf_user.process.totp.get_totp')
    def test_get_totp_uri__user_secret(self, mock_get_totp):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar')
            res = totp.get_totp_uri(user)
            self.assertIsNotNone(res)
            mock_get_totp.assert_called_once_with(user, secret='bar')
            mock_get_totp().provisioning_uri.assert_called_once_with(name='test.user (test@test.test)', issuer_name='Test Site')

    @patch('bc_fsf_user.process.totp.get_totp')
    def test_get_totp_uri__provided_secret(self, mock_get_totp):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar')
            res = totp.get_totp_uri(user, secret='baz')
            self.assertIsNotNone(res)
            mock_get_totp.assert_called_once_with(user, secret='baz')
            mock_get_totp().provisioning_uri.assert_called_once_with(name='test.user (test@test.test)', issuer_name='Test Site')


class ProcessTOTPGetTOTPQRTest(TestCase):
    @patch('bc_fsf_user.process.totp.get_totp_uri')
    @patch('qrcode.QRCode')
    def test_get_totp_qr__no_secret(self, mock_qrcode_cls, mock_get_totp_uri):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser()
            mock_get_totp_uri.return_value = None
            res = totp.get_totp_qr(user)
            self.assertIsNone(res)
            mock_get_totp_uri.assert_called_once_with(user, secret=None)
            mock_qrcode_cls.assert_not_called()


    @patch('bc_fsf_user.process.totp.get_totp_uri')
    @patch('qrcode.QRCode')
    def test_get_totp_qr__no_valid_secret(self, mock_qrcode_cls, mock_get_totp_uri):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(totp_secret='foo')
            mock_get_totp_uri.return_value = None
            res = totp.get_totp_qr(user)
            self.assertIsNone(res)
            mock_get_totp_uri.assert_called_once_with(user, secret=None)
            mock_qrcode_cls.assert_not_called()

    @patch('bc_fsf_user.process.totp.get_totp_uri')
    @patch('qrcode.QRCode')
    def test_get_totp_qr__user_secret(self, mock_qrcode_cls, mock_get_totp_uri):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar')
            mock_get_totp_uri.return_value = 'testuri'
            res = totp.get_totp_qr(user)
            self.assertIsNotNone(res)
            mock_get_totp_uri.assert_called_once_with(user, secret='bar')
            mock_qrcode_cls.assert_called_once_with(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
            mock_qrcode_cls().add_data.assert_called_once_with('testuri')
            mock_qrcode_cls().make.assert_called_once_with(fit=True)
            mock_qrcode_cls().make_image.assert_called_once_with(image_factory=qrcode.image.svg.SvgPathFillImage, attrib={'class': 'totp-setup-qr'})
            mock_qrcode_cls().make_image().to_string.assert_called_once_with(encoding='unicode')

    @patch('bc_fsf_user.process.totp.get_totp_uri')
    @patch('qrcode.QRCode')
    def test_get_totp_qr__provided_secret(self, mock_qrcode_cls, mock_get_totp_uri):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar')
            mock_get_totp_uri.return_value = 'testuri'
            res = totp.get_totp_qr(user, secret='baz')
            self.assertIsNotNone(res)
            mock_get_totp_uri.assert_called_once_with(user, secret='baz')
            mock_qrcode_cls.assert_called_once_with(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
            mock_qrcode_cls().add_data.assert_called_once_with('testuri')
            mock_qrcode_cls().make.assert_called_once_with(fit=True)
            mock_qrcode_cls().make_image.assert_called_once_with(image_factory=qrcode.image.svg.SvgPathFillImage, attrib={'class': 'totp-setup-qr'})
            mock_qrcode_cls().make_image().to_string.assert_called_once_with(encoding='unicode')

    @patch('bc_fsf_user.process.totp.get_totp_uri')
    @patch('qrcode.QRCode')
    def test_get_totp_qr__alt_cls(self, mock_qrcode_cls, mock_get_totp_uri):
        with mock_app({'USERS_ALLOW_TOTP': True, 'SITE_NAME': 'Test Site'}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar')
            mock_get_totp_uri.return_value = 'testuri'
            res = totp.get_totp_qr(user, cssclass='testcls')
            self.assertIsNotNone(res)
            mock_get_totp_uri.assert_called_once_with(user, secret='bar')
            mock_qrcode_cls.assert_called_once_with(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
            mock_qrcode_cls().add_data.assert_called_once_with('testuri')
            mock_qrcode_cls().make.assert_called_once_with(fit=True)
            mock_qrcode_cls().make_image.assert_called_once_with(image_factory=qrcode.image.svg.SvgPathFillImage, attrib={'class': 'testcls'})
            mock_qrcode_cls().make_image().to_string.assert_called_once_with(encoding='unicode')


class ProcessTOTPValidateTOTPTest(TestCase):
    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_validate_totp__no_secret(self, mock_get_totp, mock_db):
        with mock_app({}) as app:
            user = MockUser()
            res = totp.validate_totp(user, '123456')
            self.assertFalse(res)
            mock_get_totp.assert_not_called()
            mock_get_totp().verify.assert_not_called()
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_validate_totp__user_secret(self, mock_get_totp, mock_db):
        with mock_app({}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar')
            mock_get_totp().verify.return_value = True
            res = totp.validate_totp(user, '123456')
            self.assertTrue(res)
            mock_get_totp.assert_called_with(user, secret='foo')
            mock_get_totp().verify.assert_called_with('123456')
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_validate_totp__provided_secret(self, mock_get_totp, mock_db):
        with mock_app({}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar')
            mock_get_totp().verify.return_value = True
            res = totp.validate_totp(user, '123456', secret='baz')
            self.assertTrue(res)
            mock_get_totp.assert_called_with(user, secret='baz')
            mock_get_totp().verify.assert_called_with('123456')
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_validate_totp__no_backup__with_backup(self, mock_get_totp, mock_db):
        with mock_app({}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar', totp_backup_codes=['123-456-789', '111-222-333'])
            mock_get_totp().verify.return_value = False
            res = totp.validate_totp(user, '123-456-789', backup=False)
            self.assertFalse(res)
            mock_get_totp.assert_called_with(user, secret='foo')
            mock_get_totp().verify.assert_called_with('123456789')
            mock_db.session.commit.assert_not_called()

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_validate_totp__with_backup__backup(self, mock_get_totp, mock_db):
        with mock_app({}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar', totp_backup_codes=['123-456-789', '111-222-333'])
            mock_get_totp().verify.return_value = False
            res = totp.validate_totp(user, '123-456-789')
            self.assertTrue(res)
            mock_get_totp.assert_called_with(user, secret='foo')
            mock_get_totp().verify.assert_called_with('123456789')
            mock_db.session.commit.assert_called_once()
            self.assertEqual(user.totp_backup_codes, ['111-222-333'])

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_validate_totp__with_backup__valid(self, mock_get_totp, mock_db):
        with mock_app({}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar', totp_backup_codes=['123-456-789', '111-222-333'])
            mock_get_totp().verify.return_value = True
            res = totp.validate_totp(user, '123456')
            self.assertTrue(res)
            mock_get_totp.assert_called_with(user, secret='foo')
            mock_get_totp().verify.assert_called_with('123456')
            mock_db.session.commit.assert_not_called()
            self.assertEqual(user.totp_backup_codes, ['123-456-789', '111-222-333'])

    @patch('bc_fsf_user.process.totp.db')
    @patch('bc_fsf_user.process.totp.get_totp')
    def test_validate_totp__invalid(self, mock_get_totp, mock_db):
        with mock_app({}) as app:
            user = MockUser(totp_secret='foo', new_totp_secret='bar', totp_backup_codes=['123-456-789', '111-222-333'])
            mock_get_totp().verify.return_value = False
            res = totp.validate_totp(user, '1234567')
            self.assertFalse(res)
            mock_get_totp.assert_called_with(user, secret='foo')
            mock_get_totp().verify.assert_called_with('1234567')
            mock_db.session.commit.assert_not_called()
            self.assertEqual(user.totp_backup_codes, ['123-456-789', '111-222-333'])
