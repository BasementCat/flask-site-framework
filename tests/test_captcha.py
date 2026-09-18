from unittest import TestCase
from unittest.mock import patch, MagicMock, call, ANY
import json, base64

from flask import Flask, g
import arrow

from flask_site_framework.captcha import bp_captcha, CaptchaDriver, AltchaCaptchaDriver, challenge, CaptchaPlugin, validate_captcha, captcha


class TestAltchaCaptchaDriver_GetScripts(TestCase):
    def test_get_scripts(self):
        d = AltchaCaptchaDriver()
        self.assertEqual(d.get_scripts(), ['<script async defer src="https://cdn.jsdelivr.net/npm/altcha/dist/altcha.min.js" type="module"></script>'])


@patch('flask_site_framework.captcha.arrow.utcnow', return_value=arrow.get('2026-09-10 08:00:00'))
@patch('flask_site_framework.captcha.ChallengeOptionsV1')
@patch('flask_site_framework.captcha.create_challenge', return_value=MagicMock(algorithm='algo', challenge='chal', salt='salt', signature='sig'))
class TestAltchaCaptchaDriver_Challenge(TestCase):
    def test_default(self, mock_create_challenge, mock_challenge_options, mock_utcnow):
        app = Flask(__name__)
        app.config.update({
            'SECRET_KEY': 'asdf',
        })
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            res = d.challenge()
            mock_challenge_options.assert_called_once_with(
                hmac_key='asdf',
                expires=arrow.get('2026-09-10 08:05:00'),
            )
            mock_create_challenge.assert_called_once_with(mock_challenge_options.return_value)
            self.assertEqual(res, {
                'algorithm': 'algo',
                'challenge': 'chal',
                'salt': 'salt',
                'signature': 'sig',
            })

    def test_alt_config_and_params(self, mock_create_challenge, mock_challenge_options, mock_utcnow):
        app = Flask(__name__)
        app.config.update({
            'SECRET_KEY': 'asdf',
            'CAPTCHA_ALTCHA_ALGO': 'testalgo',
            'CAPTCHA_MAX_NUMBER': 3,
            'CAPTCHA_SALT_LEN': 5,
            'CAPTCHA_EXPIRE': 120,
            'CAPTCHA_HIDE_MAX_NUMBER': False,
        })
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            res = d.challenge(foo='bar')
            mock_challenge_options.assert_called_once_with(
                hmac_key='asdf',
                expires=arrow.get('2026-09-10 08:02:00'),
                algorithm='testalgo',
                max_number=3,
                salt_length=5,
                params={'foo': 'bar'},
            )
            mock_create_challenge.assert_called_once_with(mock_challenge_options.return_value)
            self.assertEqual(res, {
                'algorithm': 'algo',
                'challenge': 'chal',
                'salt': 'salt',
                'signature': 'sig',
                'maxnumber': 3,
            })


@patch('flask_site_framework.captcha.AltchaCaptchaDriver.challenge', return_value={'foo': 'bar'})
@patch('flask_site_framework.captcha.url_for', return_value='testurl')
class TestAltchaCaptchaDriver_Render(TestCase):
    maxDiff = None

    def test_default(self, mock_url_for, mock_challenge):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            res = d.render()
            mock_challenge.assert_not_called()
            mock_url_for.assert_called_once_with('captcha.challenge')
            self.assertEqual(res, '<altcha-widget expire="300000" hidefooter="true" hidelogo="true" challengeurl="testurl"></altcha-widget>')

    def test_default_with_params(self, mock_url_for, mock_challenge):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            res = d.render(foo='bar')
            mock_challenge.assert_not_called()
            mock_url_for.assert_called_once_with('captcha.challenge', foo='bar')
            self.assertEqual(res, '<altcha-widget expire="300000" hidefooter="true" hidelogo="true" challengeurl="testurl"></altcha-widget>')

    def test_alt_config_and_params(self, mock_url_for, mock_challenge):
        app = Flask(__name__)
        app.config.update({
            'CAPTCHA_ALTCHA_AUTO': 'true',
            'CAPTCHA_DELAY': 60000,
            'CAPTCHA_EXPIRE': 120,
            'CAPTCHA_FIELD_NAME': 'testfield',
            'CAPTCHA_REFETCHONEXPIRE': 'true',
            'CAPTCHA_HIDE_MAX_NUMBER': False,
            'CAPTCHA_MAX_NUMBER': 3,
            'CAPTCHA_CHALLENGE_INLINE': True
        })
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            res = d.render(foo='bar')
            mock_challenge.assert_called_once_with(foo='bar')
            mock_url_for.assert_not_called()
            self.assertEqual(res, '<altcha-widget auto="true" delay="60000" expire="120000" hidefooter="true" hidelogo="true" name="testfield" refetchonexpire="true" maxnumber="3" challengejson="{\"foo\": \"bar\"}"></altcha-widget>')


@patch('flask_site_framework.captcha.verify_solution', return_value=(True, None))
@patch('flask_site_framework.captcha.extract_params_v1')
class TestAltchaCaptchaDriver_Verify(TestCase):
    def test_no_payload__no_data(self, mock_extract_params, mock_verify_solution):
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf'})
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            self.assertFalse(d.verify())
            mock_verify_solution.assert_not_called()
            mock_extract_params.assert_not_called()

    def test_no_payload__invalid_b64(self, mock_extract_params, mock_verify_solution):
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf'})
        data = '=az'
        with app.app_context(), app.test_request_context(data={'altcha': data}):
            d = AltchaCaptchaDriver()
            self.assertFalse(d.verify())
            mock_verify_solution.assert_not_called()
            mock_extract_params.assert_not_called()

    def test_no_payload__invalid_json(self, mock_extract_params, mock_verify_solution):
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf'})
        data = base64.b64encode(b'asdf')
        with app.app_context(), app.test_request_context(data={'altcha': data}):
            d = AltchaCaptchaDriver()
            self.assertFalse(d.verify())
            mock_verify_solution.assert_not_called()
            mock_extract_params.assert_not_called()

    def test_no_payload__load_from_form(self, mock_extract_params, mock_verify_solution):
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf'})
        data = base64.b64encode(json.dumps({'foo': 'bar'}).encode('utf-8'))
        with app.app_context(), app.test_request_context(data={'altcha': data}):
            d = AltchaCaptchaDriver()
            self.assertEqual(d.verify(), mock_extract_params.return_value)
            mock_verify_solution.assert_called_once_with({'foo': 'bar'}, 'asdf', check_expires=True)
            mock_extract_params.assert_called_once_with({'foo': 'bar'})

    def test_no_payload__load_from_form__custom_field(self, mock_extract_params, mock_verify_solution):
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf', 'CAPTCHA_FIELD_NAME': 'testfield'})
        data = base64.b64encode(json.dumps({'foo': 'bar'}).encode('utf-8'))
        with app.app_context(), app.test_request_context(data={'testfield': data}):
            d = AltchaCaptchaDriver()
            self.assertEqual(d.verify(), mock_extract_params.return_value)
            mock_verify_solution.assert_called_once_with({'foo': 'bar'}, 'asdf', check_expires=True)
            mock_extract_params.assert_called_once_with({'foo': 'bar'})

    def test_verify_failed(self, mock_extract_params, mock_verify_solution):
        mock_verify_solution.return_value = (False, 'testerror')
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf', 'CAPTCHA_FIELD_NAME': 'testfield'})
        payload = {'foo': 'bar'}
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            self.assertFalse(d.verify(payload))
            mock_verify_solution.assert_called_once_with({'foo': 'bar'}, 'asdf', check_expires=True)
            mock_extract_params.assert_not_called()

    def test_verify_succeeded(self, mock_extract_params, mock_verify_solution):
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf', 'CAPTCHA_FIELD_NAME': 'testfield'})
        payload = {'foo': 'bar'}
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            self.assertEqual(d.verify(payload), mock_extract_params.return_value)
            mock_verify_solution.assert_called_once_with({'foo': 'bar'}, 'asdf', check_expires=True)
            mock_extract_params.assert_called_once_with({'foo': 'bar'})

    def test_verify_succeeded__returns_none(self, mock_extract_params, mock_verify_solution):
        mock_extract_params.return_value = None
        app = Flask(__name__)
        app.config.update({'SECRET_KEY': 'asdf', 'CAPTCHA_FIELD_NAME': 'testfield'})
        payload = {'foo': 'bar'}
        with app.app_context(), app.test_request_context():
            d = AltchaCaptchaDriver()
            self.assertEqual(d.verify(payload), {})
            mock_verify_solution.assert_called_once_with({'foo': 'bar'}, 'asdf', check_expires=True)
            mock_extract_params.assert_called_once_with({'foo': 'bar'})


@patch('flask_site_framework.captcha.jsonify')
class TestChallengeRoute(TestCase):
    def test_no_plugin(self, mock_jsonify):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            res = challenge()
            mock_jsonify.assert_called_once_with({'error': "No captcha plugin or driver"}, status=404)
            self.assertEqual(res, mock_jsonify.return_value)

    def test_no_driver(self, mock_jsonify):
        app = Flask(__name__)
        app.captcha = MagicMock(driver=None)
        with app.app_context(), app.test_request_context():
            res = challenge()
            mock_jsonify.assert_called_once_with({'error': "No captcha plugin or driver"}, status=404)
            self.assertEqual(res, mock_jsonify.return_value)

    def test_get_challenge(self, mock_jsonify):
        app = Flask(__name__)
        app.captcha = MagicMock()
        with app.app_context(), app.test_request_context(query_string={'foo': 'bar'}):
            res = challenge()
            app.captcha.driver.challenge.assert_called_once_with(foo='bar')
            mock_jsonify.assert_called_once_with(app.captcha.driver.challenge.return_value)
            self.assertEqual(res, mock_jsonify.return_value)


@patch('flask_site_framework.captcha.AltchaCaptchaDriver')
class TestCaptchaPlugin_Init(TestCase):
    def test_no_driver(self, mock_altcha_driver):
        p = CaptchaPlugin()
        self.assertEqual(p.driver, mock_altcha_driver.return_value)

    def test_with_custom_driver(self, mock_altcha_driver):
        driver = MagicMock()
        p = CaptchaPlugin(driver=driver)
        self.assertEqual(p.driver, driver)


class TestCaptchaPlugin_GetConfig(TestCase):
    def test_get_config(self):
        p = CaptchaPlugin()
        res = p.get_config()
        self.assertGreater(len(res), 0)


class TestCaptchaPlugin_GetBlueprints(TestCase):
    def test_get_blueprints(self):
        p = CaptchaPlugin()
        self.assertEqual(p.get_blueprints(), [('/captcha', bp_captcha)])


@patch('flask_site_framework.Plugin.init_app')
@patch('flask_site_framework.captcha.subscribe')
class TestCaptchaPlugin_InitApp(TestCase):
    def test_init_app(self, mock_subscribe, mock_super_init_app):
        p = CaptchaPlugin()
        app = MagicMock()
        p.init_app(app)
        mock_super_init_app.assert_called_once_with(app)
        mock_subscribe.assert_has_calls([
            call('base.template.stylesheets', p.get_stylesheets),
            call('base.template.scripts', p.get_scripts),
        ])


class TestCaptchaPlugin_GetStylesheets(TestCase):
    def test_no_driver(self):
        p = CaptchaPlugin()
        p.driver = None
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            res = p.get_stylesheets('testevent', ['foo'])
            self.assertEqual(res, ['foo'])

    def test_does_not_use_captcha__key_missing(self):
        driver = MagicMock()
        driver.get_stylesheets.return_value = ['bar']
        p = CaptchaPlugin(driver=driver)
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            res = p.get_stylesheets('testevent', ['foo'])
            self.assertEqual(res, ['foo'])

    def test_does_not_use_captcha__key_false(self):
        driver = MagicMock()
        driver.get_stylesheets.return_value = ['bar']
        p = CaptchaPlugin(driver=driver)
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            g.uses_captcha = False
            res = p.get_stylesheets('testevent', ['foo'])
            self.assertEqual(res, ['foo'])

    def test_get_stylesheets(self):
        driver = MagicMock()
        driver.get_stylesheets.return_value = ['bar']
        p = CaptchaPlugin(driver=driver)
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            g.uses_captcha = True
            res = p.get_stylesheets('testevent', ['foo'])
            self.assertEqual(res, ['foo', 'bar'])


class TestCaptchaPlugin_GetScripts(TestCase):
    def test_no_driver(self):
        p = CaptchaPlugin()
        p.driver = None
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            res = p.get_scripts('testevent', ['foo'])
            self.assertEqual(res, ['foo'])

    def test_does_not_use_captcha__key_missing(self):
        driver = MagicMock()
        driver.get_scripts.return_value = ['bar']
        p = CaptchaPlugin(driver=driver)
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            res = p.get_scripts('testevent', ['foo'])
            self.assertEqual(res, ['foo'])

    def test_does_not_use_captcha__key_false(self):
        driver = MagicMock()
        driver.get_scripts.return_value = ['bar']
        p = CaptchaPlugin(driver=driver)
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            g.uses_captcha = False
            res = p.get_scripts('testevent', ['foo'])
            self.assertEqual(res, ['foo'])

    def test_get_scripts(self):
        driver = MagicMock()
        driver.get_scripts.return_value = ['bar']
        p = CaptchaPlugin(driver=driver)
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            g.uses_captcha = True
            res = p.get_scripts('testevent', ['foo'])
            self.assertEqual(res, ['foo', 'bar'])


class TestCaptchaPlugin_GetCaptcha(TestCase):
    def test_no_driver(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            p = CaptchaPlugin()
            p.driver = None
            res = p.get_captcha()
            self.assertEqual(str(res), '')
            self.assertNotIn('uses_captcha', g)

    def test_driver_returns_no_html(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = MagicMock()
            driver.render.return_value = None
            p = CaptchaPlugin(driver=driver)
            res = p.get_captcha()
            driver.render.assert_called_once_with()
            self.assertEqual(str(res), '')
            self.assertNotIn('uses_captcha', g)

    def test_get_markup(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = MagicMock()
            driver.render.return_value = 'foo'
            p = CaptchaPlugin(driver=driver)
            res = p.get_captcha()
            driver.render.assert_called_once_with()
            self.assertEqual(str(res), 'foo')
            self.assertEqual(g.uses_captcha, True)

    def test_get_markup_with_params(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            driver = MagicMock()
            driver.render.return_value = 'foo'
            p = CaptchaPlugin(driver=driver)
            res = p.get_captcha(foo='bar')
            driver.render.assert_called_once_with(foo='bar')
            self.assertEqual(str(res), 'foo')
            self.assertEqual(g.uses_captcha, True)


@patch('flask_site_framework.captcha.abort', side_effect=RuntimeError('testerror'))
@patch('flask_site_framework.captcha.flash')
@patch('flask_site_framework.captcha.redirect')
class TestValidateCaptchaDecorator(TestCase):
    def test_no_plugin(self, mock_redirect, mock_flash, mock_abort):
        app = Flask(__name__)
        testfn = MagicMock()
        testfn_wrapped = validate_captcha()(testfn)
        with app.app_context(), app.test_request_context():
            res = testfn_wrapped('foo', bar='baz')
            mock_abort.assert_not_called()
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            testfn.assert_called_once_with('foo', bar='baz')
            self.assertEqual(res, testfn.return_value)

    def test_no_driver(self, mock_redirect, mock_flash, mock_abort):
        app = Flask(__name__)
        p = CaptchaPlugin(app)
        p.driver = None
        testfn = MagicMock()
        testfn_wrapped = validate_captcha()(testfn)
        with app.app_context(), app.test_request_context():
            res = testfn_wrapped('foo', bar='baz')
            mock_abort.assert_not_called()
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            testfn.assert_called_once_with('foo', bar='baz')
            self.assertEqual(res, testfn.return_value)

    def test_verification_fails__no_error_page(self, mock_redirect, mock_flash, mock_abort):
        app = Flask(__name__)
        driver = MagicMock()
        driver.verify.return_value = False
        p = CaptchaPlugin(app, driver)
        testfn = MagicMock()
        testfn_wrapped = validate_captcha()(testfn)
        with app.app_context(), app.test_request_context():
            res = testfn_wrapped('foo', bar='baz')
            driver.verify.assert_called_once_with()
            mock_abort.assert_not_called()
            mock_flash.assert_called_once_with("Captcha validation failed", 'danger')
            mock_redirect.assert_called_once_with('/')
            testfn.assert_not_called()
            self.assertEqual(res, mock_redirect.return_value)

    def test_verification_fails__error_page(self, mock_redirect, mock_flash, mock_abort):
        app = Flask(__name__)
        driver = MagicMock()
        driver.verify.return_value = False
        p = CaptchaPlugin(app, driver)
        testfn = MagicMock()
        testfn_wrapped = validate_captcha(error_page=True)(testfn)
        with app.app_context(), app.test_request_context():
            with self.assertRaisesRegex(RuntimeError, 'testerror'):
                res = testfn_wrapped('foo', bar='baz')
            driver.verify.assert_called_once_with()
            mock_abort.assert_called_once_with(400, "Captcha validation failed")
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            testfn.assert_not_called()

    def test_verification_succeeds(self, mock_redirect, mock_flash, mock_abort):
        app = Flask(__name__)
        driver = MagicMock()
        driver.verify.return_value = True
        p = CaptchaPlugin(app, driver)
        testfn = MagicMock()
        testfn_wrapped = validate_captcha()(testfn)
        with app.app_context(), app.test_request_context():
            res = testfn_wrapped('foo', bar='baz')
            driver.verify.assert_called_once_with()
            mock_abort.assert_not_called()
            mock_flash.assert_not_called()
            mock_redirect.assert_not_called()
            testfn.assert_called_once_with('foo', bar='baz')
            self.assertEqual(res, testfn.return_value)


@patch('flask_site_framework.captcha.CaptchaPlugin.get_captcha')
class TestCaptchaJinjaGlobal(TestCase):
    def test_no_plugin(self, mock_get_captcha):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            res = captcha(foo='bar')
            self.assertEqual(res, '')
            mock_get_captcha.assert_not_called()

    def test_with_plugin(self, mock_get_captcha):
        app = Flask(__name__)
        p = CaptchaPlugin(app)
        assert app.captcha is p
        with app.app_context(), app.test_request_context():
            res = captcha(foo='bar')
            self.assertEqual(res, mock_get_captcha.return_value)
            mock_get_captcha.assert_called_once_with(foo='bar')
