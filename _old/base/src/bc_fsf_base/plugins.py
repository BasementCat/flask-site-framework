"""Core plugins"""

from typing import Optional, Iterable

import logging

from flask import Flask, Blueprint, current_app, request, render_template, g, abort, flash, redirect
from markupsafe import Markup
from jinja2.exceptions import TemplateNotFound
from flask_bootstrap import Bootstrap
from flask_mail import Mail, Message
from markdown import markdown

from . import Plugin, commands
from .cache import CacheDriver, MemoryCacheDriver
from .captcha import CaptchaDriver, AltchaCaptchaDriver
from .event import subscribe, publish
from .lib import meta
from . import views


logger = logging.getLogger(__name__)







class MetaPlugin(Plugin):
    """\
    Add meta tags for content to the page
    """

    def init_app(self, app):
        super().init_app(app)
        subscribe('base.template.meta_tags', self.get_meta_tags)

    @staticmethod
    def get_meta_tags(event, value, *args, **kwargs):
        content = publish('meta.content', {})
        try:
            value += list(meta.get_meta_for_content(content))
        except:
            logger.error("Failed to generate meta tags for content\n%s", content, exc_info=True)
        return value


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
        return [('/captcha', views.bp_captcha)]

    def get_decorators(self):
        # decorators are called with callback, dec_args/dec_kwargs, and call_args/call_kwargs
        # after performing necessary work, they should return callback with call_args/call_kwargs
        return {'validate': self.dec_validate}

    def init_app(self, app):
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

    def dec_validate(self, callback, dec_args, dec_kwargs, call_args, call_kwargs):
        res = {}
        if self.driver:
            res = self.driver.verify()
            if res is False:
                if dec_kwargs.get('error_page'):
                    abort(400, "Captcha validation failed")
                else:
                    flash("Captcha validation failed", 'danger')
                    return redirect(request.referrer or '/')
        return callback(*call_args, **call_kwargs, **res)

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


@CaptchaPlugin.jinja_global()
def captcha(**params):
    """\
    Get the captcha markup from the current driver in a template
    """

    plugin = current_app.plugins.get('captcha')
    if plugin:
        return plugin.get_captcha(**params)
    return ''
