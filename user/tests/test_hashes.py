from unittest import TestCase
from unittest.mock import patch
import json
import base64

from bc_fsf_user.hashes import PasswordHashDriver, SCryptHashDriver, Password


@patch('bc_fsf_user.hashes.Password')
class TestBaseHashDriver(TestCase):
    def test_init(self, mock_pw_cls):
        dr = PasswordHashDriver()
        self.assertEqual(dr.salt_len, 16)

    def test_init__salt_len(self, mock_pw_cls):
        dr = PasswordHashDriver(salt_len=32)
        self.assertEqual(dr.salt_len, 32)

    def test_get_params(self, mock_pw_cls):
        dr = PasswordHashDriver()
        self.assertEqual(dr.get_params(), {'salt_len': 16})

    def test_gen_salt(self, mock_pw_cls):
        dr = PasswordHashDriver()
        s = dr.gen_salt()
        self.assertIsInstance(s, bytes)
        self.assertEqual(len(s), 16)

    def test_really_hash(self, mock_pw_cls):
        dr = PasswordHashDriver()
        with self.assertRaises(NotImplementedError):
            dr.really_hash_password(b'', b'')

    def test_hash(self, mock_pw_cls):
        with patch('bc_fsf_user.hashes.PasswordHashDriver.gen_salt') as gs, \
        patch('bc_fsf_user.hashes.PasswordHashDriver.really_hash_password') as rh:
            dr = PasswordHashDriver()
            res = dr.hash_password(b'pw')
            gs.assert_called_once()
            rh.assert_called_once_with(gs(), b'pw')
            mock_pw_cls.assert_called_once_with('PasswordHashDriver', gs(), rh(), {'salt_len': 16})
            self.assertIsInstance(res, str)

    def test_hash__salt(self, mock_pw_cls):
        with patch('bc_fsf_user.hashes.PasswordHashDriver.really_hash_password') as rh:
            dr = PasswordHashDriver()
            res = dr.hash_password(b'pw', salt=b'sl')
            rh.assert_called_once_with(b'sl', b'pw')
            mock_pw_cls.assert_called_once_with('PasswordHashDriver', b'sl', rh(), {'salt_len': 16})
            self.assertIsInstance(res, str)

    def test_check(self, mock_pw_cls):
        dr = PasswordHashDriver()
        dr.check_password('foo', b'bar')
        mock_pw_cls.parse.assert_called_once_with('foo')
        mock_pw_cls.parse().check.assert_called_once_with(b'bar')


class TestSCryptHashDriver(TestCase):
    def test_init(self):
        dr = SCryptHashDriver()
        self.assertEqual(dr.salt_len, 16)
        self.assertEqual(dr.n, 16384)
        self.assertEqual(dr.r, 8)
        self.assertEqual(dr.p, 1)
        self.assertEqual(dr.maxmem, 0)
        self.assertEqual(dr.dklen, 64)

    def test_init_args(self):
        dr = SCryptHashDriver(salt_len=1, n=2, r=3, p=4, maxmem=5, dklen=6)
        self.assertEqual(dr.salt_len, 1)
        self.assertEqual(dr.n, 2)
        self.assertEqual(dr.r, 3)
        self.assertEqual(dr.p, 4)
        self.assertEqual(dr.maxmem, 5)
        self.assertEqual(dr.dklen, 6)

    def test_get_params(self):
        dr = SCryptHashDriver()
        self.assertEqual(dr.get_params(), {
            'salt_len': 16,
            'n': 16384,
            'r': 8,
            'p': 1,
            'maxmem': 0,
            'dklen': 64,
        })

    def test_really_hash(self):
        dr = SCryptHashDriver()
        pw = dr.really_hash_password(b'1q2w3e4r5t6y7u8i', b'password')
        self.assertEqual(pw, b'^\xc9\x13\x18U8\xe4\xc7"\xc8\x8d\x94.\xd8=O\xe7\xc1Pk\xaf\xb6\xdfJ\xfa\x07\xd0j\xfa0\x85?~QQA2\xd0\xec\x7f\xe9\xf5\xbef \x0c \x101\xed\xed\xe0\xef\xc0 \\\xfb:\xd4\xa4\x18\xf1\x80(')


class TestPassword(TestCase):
    maxDiff = None

    def test_create_password__invalid(self):
        with self.assertRaises(KeyError):
            Password('foo', b'', b'', {}).driver

    def test_create_password(self):
        pw = Password(
            'SCryptHashDriver',
            b'1q2w3e4r5t6y7u8i',
            b'^\xc9\x13\x18U8\xe4\xc7"\xc8\x8d\x94.\xd8=O\xe7\xc1Pk\xaf\xb6\xdfJ\xfa\x07\xd0j\xfa0\x85?~QQA2\xd0\xec\x7f\xe9\xf5\xbef \x0c \x101\xed\xed\xe0\xef\xc0 \\\xfb:\xd4\xa4\x18\xf1\x80(',
            {
                'salt_len': 16,
                'n': 16384,
                'r': 8,
                'p': 1,
                'maxmem': 0,
                'dklen': 64,
            },
        )
        dr = pw.driver
        self.assertIsInstance(dr, SCryptHashDriver)
        self.assertEqual(dr.salt_len, 16)
        self.assertEqual(dr.n, 16384)
        self.assertEqual(dr.r, 8)
        self.assertEqual(dr.p, 1)
        self.assertEqual(dr.maxmem, 0)
        self.assertEqual(dr.dklen, 64)

    def test_password_equal(self):
        p = {
            'salt_len': 16,
            'n': 16384,
            'r': 8,
            'p': 1,
            'maxmem': 0,
            'dklen': 64,
        }
        dr = SCryptHashDriver(**p)
        s = b'1q2w3e4r5t6y7u8i'
        hpw1 = dr.really_hash_password(s, b'password')
        hpw2 = dr.really_hash_password(s, b'password')
        hpw3 = dr.really_hash_password(s, b'password2')
        pw1 = Password('SCryptHashDriver', s, hpw1, p)
        pw2 = Password('SCryptHashDriver', s, hpw2, p)
        pw3 = Password('SCryptHashDriver', s, hpw3, p)
        self.assertEqual(pw1, pw1)
        self.assertEqual(pw1, pw2)
        self.assertNotEqual(pw1, pw3)

    def test_password_equal__str(self):
        p = {
            'salt_len': 16,
            'n': 16384,
            'r': 8,
            'p': 1,
            'maxmem': 0,
            'dklen': 64,
        }
        dr = SCryptHashDriver(**p)
        s = b'1q2w3e4r5t6y7u8i'
        hpw1 = dr.really_hash_password(s, b'password')
        pw1 = Password('SCryptHashDriver', s, hpw1, p)
        self.assertEqual(pw1, 'password')

    def test_stringify(self):
        p = {
            'salt_len': 16,
            'n': 16384,
            'r': 8,
            'p': 1,
            'maxmem': 0,
            'dklen': 64,
        }
        dr = SCryptHashDriver(**p)
        s = b'1q2w3e4r5t6y7u8i'
        hpw1 = dr.really_hash_password(s, b'password')
        pw1 = Password('SCryptHashDriver', s, hpw1, p)
        data = json.loads(str(pw1))
        self.assertEqual(data, {
            'driver_name': 'SCryptHashDriver',
            'salt': base64.b64encode(s).decode('ascii'),
            'hashed_password': base64.b64encode(hpw1).decode('ascii'),
            'params': p
        })

    def test_parse(self):
        p = {
            'salt_len': 16,
            'n': 16384,
            'r': 8,
            'p': 1,
            'maxmem': 0,
            'dklen': 64,
        }
        dr = SCryptHashDriver(**p)
        s = b'1q2w3e4r5t6y7u8i'
        hpw1 = dr.really_hash_password(s, b'password')
        pw1 = Password('SCryptHashDriver', s, hpw1, p)
        pw2 = Password.parse(str(pw1))
        self.assertEqual(pw1, pw2)

    def test_parse__invalid(self):
        p = {
            'salt_len': 16,
            'n': 16384,
            'r': 8,
            'p': 1,
            'maxmem': 0,
            'dklen': 64,
        }
        dr = SCryptHashDriver(**p)
        s = b'1q2w3e4r5t6y7u8i'
        hpw1 = dr.really_hash_password(s, b'password')
        pw1 = Password('SCryptHashDriver', s, hpw1, p)
        data = str(pw1).replace('SCryptHashDriver', 'invalid')
        with self.assertRaises(KeyError):
            Password.parse(data).driver
