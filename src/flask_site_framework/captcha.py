"""Captcha implementations"""

from typing import Iterable, Union, Optional

import json
import base64
import functools

from flask import Flask, Blueprint, current_app, request, g, abort, flash, redirect, url_for, jsonify
from altcha import ChallengeOptionsV1, create_challenge, verify_solution, extract_params_v1
import arrow
from markupsafe import Markup

from . import Plugin
from .event import subscribe
from .jinja import jinja_global


bp_captcha = Blueprint('captcha', __name__)


class CaptchaDriver:
    """\
    Implementation of a captcha for protecting form submission/anything else
    that bots should not access
    """

    def get_stylesheets(self) -> Iterable[str]:
        """\
        Provide any necessary stylesheets for this captcha driver, applied only
        if the captcha is used on a page.  May be a URL, or full link tag.
        """

        return []

    def get_scripts(self) -> Iterable[str]:
        """\
        Provide any necessary javascript for this captcha driver, applied only
        if the captcha is used on a page.  May be a URL, or full script tag.
        """

        return []

    def challenge(self, **params) -> dict:
        """\
        Generate a challenge for the given parameters.  The resulting dict must
        be json-serializable.
        """

        raise NotImplementedError()

    def render(self, **params) -> str:
        """\
        Render markup for the captcha
        """

        raise NotImplementedError()

    def verify(self) -> Union[dict, bool]:
        """\
        Use request data to verify the captcha challenge.  May return parameters
        extracted from the challenge, but must return False if the challenge is
        not present or cannot be verified.
        """

        raise NotImplementedError()


class AltchaCaptchaDriver:
    """\
    Captcha driver for Altcha - see above for details on functions
    """

    def get_scripts(self) -> Iterable[str]:
        return ['<script async defer src="https://cdn.jsdelivr.net/npm/altcha/dist/altcha.min.js" type="module"></script>']

    def challenge(self, **params) -> dict:
        options = ChallengeOptionsV1(**dict(filter(lambda i: i[1] is not None, {
            'algorithm': current_app.config.get('CAPTCHA_ALTCHA_ALGO'),  # Hashing algorithm to use ('SHA-1', 'SHA-256', 'SHA-512', default: 'SHA-256').
            'max_number': current_app.config.get('CAPTCHA_MAX_NUMBER'),  # Maximum number for the random number generator (default: 1,000,000).
            'salt_length': current_app.config.get('CAPTCHA_SALT_LEN'),  # Length of the random salt in bytes (default: 12).
            'hmac_key': current_app.config['SECRET_KEY'],
            'expires': arrow.utcnow().shift(seconds=current_app.config.get('CAPTCHA_EXPIRE', 300)),  # Duration after which the captcha expires
            'params': params or None,
        }.items())))
        challenge = create_challenge(options)

        out = {
            'algorithm': challenge.algorithm,
            'challenge': challenge.challenge,
            'salt': challenge.salt,
            'signature': challenge.signature,
        }
        if not current_app.config.get('CAPTCHA_HIDE_MAX_NUMBER') and current_app.config.get('CAPTCHA_MAX_NUMBER'):
            out['maxnumber'] = current_app.config.get('CAPTCHA_MAX_NUMBER')
        return out

    def render(self, **params) -> str:
        options = {
            'auto': current_app.config.get('CAPTCHA_ALTCHA_AUTO'),  # Automatically verify without user interaction (possible values: off, onfocus, onload, onsubmit).
            'delay': current_app.config.get('CAPTCHA_DELAY'),  # Artificial delay in milliseconds before verification (defaults to 0).
            'expire': int(current_app.config.get('CAPTCHA_EXPIRE', 300) * 1000),  # Challenge expiration duration in milliseconds.
            'hidefooter': 'true',
            'hidelogo': 'true',
            'name': current_app.config.get('CAPTCHA_FIELD_NAME'),  # Name of the hidden field containing the payload (defaults to “altcha”).
            'refetchonexpire': current_app.config.get('CAPTCHA_REFETCHONEXPIRE'),  # Automatically re-fetch and re-validate when the challenge expires (defaults to true).
        }

        if not current_app.config.get('CAPTCHA_HIDE_MAX_NUMBER'):
            options['maxnumber'] = current_app.config.get('CAPTCHA_MAX_NUMBER')  # Max number to iterate to (defaults to 1,000,000).

        if current_app.config.get('CAPTCHA_CHALLENGE_INLINE'):
            options['challengejson'] = json.dumps(self.challenge(**params))
        else:
            options['challengeurl'] = url_for('captcha.challenge', **params)

        options = dict(filter(lambda i: i[1] is not None, options.items()))
        options_str = ' '.join((f'{k}="{v}"' for k, v in options.items()))

        return f'<altcha-widget {options_str}></altcha-widget>'

    def verify(self, payload=None) -> Union[dict, bool]:
        if payload is None:
            try:
                payload = json.loads(base64.b64decode(request.form.get(current_app.config.get('CAPTCHA_FIELD_NAME') or 'altcha')))
            except:
                pass

        if payload:
            try:
                ok, err = verify_solution(payload, current_app.config['SECRET_KEY'], check_expires=True)
                if ok:
                    out = extract_params_v1(payload)
                    return out or {}
            except:
                pass

        return False


@bp_captcha.get('/challenge')
def challenge():
    """Get a challenge for the current captcha driver"""

    plugin = getattr(current_app, 'captcha', None)
    if plugin:
        driver = plugin.driver
        if driver:
            return jsonify(driver.challenge(**dict(request.args.items())))
    return jsonify({'error': "No captcha plugin or driver"}, status=404)


class CaptchaPlugin(Plugin):
    """\
    Provides captcha functionality for the application
    """

    def __init__(self, app: Optional[Flask]=None, driver: Optional[CaptchaDriver]=None):
        """\
        Initialize the plugin, if no driver is given, the Altcha driver is used
        """

        self.driver = driver or AltchaCaptchaDriver()
        super().__init__(app=app)

    def get_config(self):
        return {
            'CAPTCHA_ALTCHA_ALGO': {
                'description': "Altcha hashing algorithm to use ('SHA-1', 'SHA-256', 'SHA-512', default: 'SHA-256').",
            },
            'CAPTCHA_MAX_NUMBER': {
                'parser': int,
                'description': "Maximum number for the random number generator (Altcha default: 1,000,000).",
            },
            'CAPTCHA_SALT_LEN': {
                'parser': int,
                'description': "Length of the random salt in bytes (Altcha default: 12).",
            },
            'CAPTCHA_EXPIRE': {
                'parser': int,
                'default': 300,
                'description': "Duration after which the captcha expires, in seconds",
            },
            'CAPTCHA_ALTCHA_AUTO': {
                'description': "For Altcha, automatically verify without user interaction (possible values: off, onfocus, onload, onsubmit).",
            },
            'CAPTCHA_DELAY': {
                'parser': int,
                'description': "Artificial delay in milliseconds before verification (Altcha defaults to 0).",
            },
            'CAPTCHA_FIELD_NAME': {
                'description': "Name of the hidden field containing the payload (Altcha defaults to 'altcha').",
            },
            'CAPTCHA_REFETCHONEXPIRE': {
                'parser': bool,
                'description': "Automatically re-fetch and re-validate when the challenge expires (Altcha defaults to true).",
            },
            'CAPTCHA_HIDE_MAX_NUMBER': {
                'parser': bool,
                'default': True,
                'description': "Avoid sending the max number in the challenge (decreases client-side performance, may be desirable)",
            },
            'CAPTCHA_CHALLENGE_INLINE': {
                'parser': bool,
                'default': False,
                'description': "Send the challenge inline with the form rather than making an additional request",
            },
        }

    def get_blueprints(self):
        return [('/captcha', bp_captcha)]

    def init_app(self, app):
        app.captcha = self
        super().init_app(app)
        subscribe('base.template.stylesheets', self.get_stylesheets)
        subscribe('base.template.scripts', self.get_scripts)

    def get_stylesheets(self, event, value, *args, **kwargs):
        if self.driver and 'uses_captcha' in g and g.uses_captcha:
            value += (self.driver.get_stylesheets())
        return value

    def get_scripts(self, event, value, *args, **kwargs):
        if self.driver and 'uses_captcha' in g and g.uses_captcha:
            value += (self.driver.get_scripts())
        return value

    def get_captcha(self, **params):
        """\
        Get the captcha markup from the current driver
        """

        if self.driver:
            html = self.driver.render(**params)
            if html:
                g.uses_captcha = True
                return Markup(html)
        return ''


def validate_captcha(error_page: bool=False):
    """\
    Validate the captcha prior to rendering a route.  Set error_page to true to
    abort and render an error page; othewise flash a message and return to the
    referrer or /
    """
    def validate_captcha_impl(callback):
        @functools.wraps(callback)
        def validate_captcha_wrap(*args, **kwargs):
            plugin = getattr(current_app, 'captcha', None)
            if plugin and plugin.driver:
                res = plugin.driver.verify()
                if res is False:
                    if error_page:
                        abort(400, "Captcha validation failed")
                    else:
                        flash("Captcha validation failed", 'danger')
                        return redirect(request.referrer or '/')
            return callback(*args, **kwargs)
        return validate_captcha_wrap
    return validate_captcha_impl


@jinja_global()
def captcha(**params):
    """\
    Get the captcha markup from the current driver in a template
    """

    plugin = getattr(current_app, 'captcha', None)
    if plugin:
        return plugin.get_captcha(**params)
    return ''
