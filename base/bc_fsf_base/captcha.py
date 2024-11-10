"""Captcha implementations"""

from typing import Iterable, Union

import json
import base64
from flask import current_app, url_for, request
from altcha import ChallengeOptions, create_challenge, verify_solution, extract_params
import arrow


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
        options = ChallengeOptions(**dict(filter(lambda i: i[1] is not None, {
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
                raise
                pass

        if payload:
            try:
                ok, err = verify_solution(payload, current_app.config['SECRET_KEY'], check_expires=True)
                if ok:
                    out = extract_params(payload)
                    return out or {}
            except:
                pass

        return False
