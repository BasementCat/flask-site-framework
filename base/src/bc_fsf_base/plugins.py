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


class BootstrapPlugin(Plugin):
    """\
    Install the Flask-Bootstrap plugin, and optionally include the FontAwesome
    stylesheet.
    """

    def __init__(self, *args, with_fontawesome: bool=False, **kwargs):
        """\
        Initialize the plugin, if with_fontawesome is True, add the fontawesome
        stylesheet to the page
        """

        super().__init__(*args, **kwargs)
        self.with_fontawesome = with_fontawesome

    def get_flask_plugins(self):
        return [Bootstrap()]

    def get_blueprints(self):
        return [(None, Blueprint('_base_bs', __name__, template_folder='templates'))]

    @staticmethod
    def get_fontawesome_stylesheet(event, value, *args, **kwargs):
        value.append('<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.6.0/css/all.min.css" integrity="sha512-Kc323vGBEqzTmouAECnVceyQqyqdsSiqLQISBL29aUW4U/M7pSPA/gEUZQqv1cwx4OnYxTxve5UMg5GT6L4JJg==" crossorigin="anonymous" referrerpolicy="no-referrer" />')
        return value

    def init_app(self, app):
        super().init_app(app)
        if self.with_fontawesome:
            subscribe('base.template.stylesheets', self.get_fontawesome_stylesheet)


@BootstrapPlugin.jinja_global()
def fa(icon, collection='fa', cls=''):
    """\
    Generate markup for a FontAwesome icon
    """

    return f'<span class="{collection} fa-{icon} {cls}"></span>'


class CachePlugin(Plugin):
    """\
    Enable caching on the application
    """

    def __init__(self, app: Optional[Flask]=None, driver: Optional[CacheDriver]=None):
        """\
        Initialize the cache plugin with an optional flask app.
        If no cache driver is provided, the memory cache driver is used.
        """

        self.driver = driver or MemoryCacheDriver()
        super().__init__(app=app)

    def get_config(self):
        return self.driver.require_config({
            'REDIS_URL': {
                'description': "URI to connect to Redis, like redis://:password@localhost:6379/0 or unix://:password@/path/to/socket.sock?db=0",
            },
        })

    def get_flask_plugins(self):
        return self.driver.get_flask_plugins()

    def init_app(self, app):
        super().init_app(app)
        app._cache_driver = self.driver


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


class EmailMessage(Message):
    """\
    Represents an email message to be sent.
    """

    def __init__(self, plugin, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin = plugin

    def render(self, template_name: str, *args, text_args: Optional[dict]=None, html_args: Optional[dict]=None, **kwargs):
        """\
        Search for templates based on the given name, and render them as text or
        html content and apply to the message.

        Templates are searched for in "email/<template_name>", and if no HTML
        templates are found, the text content (which is expected to be markdown)
        is then rendered to HTML.

        Text: email/<template>/markdown.j2, email/<template>.md.j2
        HTML: email/<template>/html.j2, email/<template>.html.j2
        """

        text_candidates = [
            f'email/{template_name}/markdown.j2',
            f'email/{template_name}.md.j2',
        ]
        html_candidates = [
            f'email/{template_name}/html.j2',
            f'email/{template_name}.html.j2',
        ]
        def render_candidate(candidates, extra_args=None):
            for tpl in candidates:
                try:
                    return render_template(tpl, *args, **(extra_args or {}), **kwargs)
                except TemplateNotFound:
                    pass
        text = render_candidate(text_candidates, text_args)
        html = render_candidate(html_candidates, html_args)
        if text and not html:
            html = markdown(text)
        if not (text or html):
            raise RuntimeError("No template candidates were found")
        self.body = text
        self.html = html
        return self

    def send_message(self):
        """\
        Send the message to its recipients
        """

        if not (self.body or self.html):
            raise ValueError("A body is required")

        if not self.recipients or self.cc or self.bcc:
            raise ValueError("Recipients are required")

        return self.plugin.send_email(self)


class EmailPlugin(Plugin):
    """\
    Provides email sending functionality
    """

    def get_config(self):
        return {
            'MAIL_SERVER': {
                'required': True,
                'description': "Server to use to send email",
            },
            'MAIL_PORT': {
                'parser': int,
                'default': 25,
                'description': "Port on which to send email (usually 25(default) for plaintext, 587 for TLS/SSL",
            },
            'MAIL_USE_TLS': {
                'parser': bool,
                'default': False,
                'description': "Use TLS for the connection to the mail server",
            },
            'MAIL_USE_SSL': {
                'parser': bool,
                'default': False,
                'description': "Use SSL for the connection to the mail server",
            },
            'MAIL_USERNAME': {
                'description': "Username for mail server, if authentication is required",
            },
            'MAIL_PASSWORD': {
                'description': "Password for mail server, if authentication is required",
            },
            'MAIL_DEFAULT_SENDER': {
                'required': True,
                'description': "Default sender address for mail",
            },
        }

    def get_flask_plugins(self):
        self.mail = Mail()
        return [self.mail]

    def get_commands(self):
        return [commands.cli_email]

    def create(self, subject: str, text_body: Optional[str]=None, html_body: Optional[str]=None, sender: Optional[str]=None, to: Optional[Iterable[str]]=None, reply_to: Optional[str]=None, cc: Optional[Iterable[str]]=None, bcc: Optional[Iterable[str]]=None) -> EmailMessage:
        """\
        Create a new EmailMessage with the given properties
        """

        return EmailMessage(
            self,
            subject=subject,
            recipients=to,
            body=text_body,
            html=html_body,
            sender=sender,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
        )

    def send_email(self, message: Message):
        """\
        Send an email message
        """

        return self.mail.send(message)


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
