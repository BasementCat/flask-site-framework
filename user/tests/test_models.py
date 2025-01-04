from unittest import TestCase
from unittest.mock import patch, MagicMock

from bc_fsf_user.models import User

from . import mock_app


class TestUserModel(TestCase):
    def test_prop__rolegroup(self):
        with mock_app({}) as app, app.test_request_context():
            u = User()
            rg1 = u.rolegroup
            rg2 = u.rolegroup
            self.assertTrue(rg1 is rg2)

    @patch('bc_fsf_user.models.Password')
    def test_prop__password(self, mock_password_cls):
        with mock_app({}) as app, app.test_request_context():
            mock_hasher = MagicMock()
            app.plugins = {'user': MagicMock(hash_driver=mock_hasher)}
            u = User()

            u.password = 'foo'
            mock_hasher.hash_password.assert_called_once_with(b'foo')
            self.assertEqual(u.hashed_password, mock_hasher.hash_password())

            pw = u.password
            mock_password_cls.parse.assert_called_once_with(u.hashed_password)
            self.assertEqual(pw, mock_password_cls.parse())

    @patch('bc_fsf_user.models.event')
    def test_method__can(self, mock_event):
        u = User()
        res = u.can('foo', 'bar', obj='baz')
        mock_event.publish.assert_called_once_with('user.can', False, 'foo', 'bar', user=u, obj='baz')
        self.assertEqual(res, mock_event.publish())

    @patch('bc_fsf_user.models.event')
    def test_prop__is_logged_in__no_user(self, mock_event):
        u_test = User(id=1)
        u_curr = None
        mock_event.publish.return_value = u_curr
        res = u_test.is_logged_in
        self.assertFalse(res)

    @patch('bc_fsf_user.models.event')
    def test_prop__is_logged_in__not_current_user(self, mock_event):
        u_test = User(id=1)
        u_curr = User(id=2)
        mock_event.publish.return_value = u_curr
        res = u_test.is_logged_in
        self.assertFalse(res)

    @patch('bc_fsf_user.models.event')
    def test_prop__is_logged_in(self, mock_event):
        u_test = User(id=1)
        u_curr = User(id=1)
        mock_event.publish.return_value = u_curr
        res = u_test.is_logged_in
        self.assertTrue(res)
