"""\
Base plugin code.

General usage in your app's __init__.py

    from flask import Flask
    from flask_site_framework import FlaskConfigPlugin, ErrorHandlerPlugin
    from flask_site_framework.jinja import JinjaPlugin

    def create_app():
        app = Flask(__name__)
        # Load config first
        FlaskConfigPlugin(app)
        ErrorHandlerPlugin(app)
        # Load jinja last
        JinjaPlugin(app)
        return app
"""

from typing import Callable, Optional, Dict, Any, Iterable, Tuple, Union

import re
import os
import functools
import tempfile
import logging

from flask import Flask, current_app, Blueprint, render_template
from flask.cli import AppGroup
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

from . import event


logger = logging.getLogger(__name__)


class Plugin:
    """\
    Custom plugin class providing convenience methods for providing Flask things
    (commands, blueprints, config, etc).
    """

    def __init__(self, app: Optional[Flask]=None, url_prefix: Optional[str]=None):
        """\
        Initialize the plugin, optionally with the given Flask app.  If a URL
        prefix is given, it is used in the case that a blueprint does not
        provide its own url prefix.
        """

        self.url_prefix = url_prefix
        if app is not None:
            self.init_app(app)

    def get_config(self) -> Dict[str, Dict[str, Any]]:
        """\
        Provides this plugin's configuration keys to be parsed and validated.
        The return value must be a dict mapping config keys to dicts containing
        any of the following: (all are optional)

        * parser: Callable to parse the config value
        * validator: Callable to validate the config value
        * default: Default value of this config key, if it is not present at all
        * required: If true, this config key is required and the application will not start without it
        * description: A helpful brief description of the config key
        """

        return {}

    def get_flask_plugins(self) -> Iterable[object]:
        """\
        Provide other Flask plugins to be initialized with the main Flask app
        """
        return []

    def get_blueprints(self) -> Iterable[Tuple[Optional[str], Blueprint]]:
        """\
        Provide blueprints to mount to the Flask app, with an optional URL
        prefix.  If no prefix is given, the global url prefix for this plugin
        is used (if present)
        """

        return []

    def get_commands(self) -> Iterable[AppGroup]:
        """\
        Provide app groups to be registered to the app as commands.
        """

        return []

    def init_app(self, app: Flask):
        """\
        Perform initialization of this plugin, and apply to the app.  If a
        subclass defines init_app, it must call the superclass method.
        """

        for fplugin in self.get_flask_plugins():
            fplugin.init_app(app)

        for bp_prefix, bp in self.get_blueprints():
            prefix = re.sub(r'/{2,}', '/', '/' + ((self.url_prefix or '') + '/' + (bp_prefix or '')).strip('/'))
            app.register_blueprint(bp, url_prefix=prefix)

        for group in self.get_commands():
            app.cli.add_command(group)

        self._load_config(app)

    def _load_config(self, app: Flask):
        defaults = {
            'parser': None,
            'validator': None,
            'default': None,
            'required': False,
            'description': '',
        }
        for config_key, config_opt in self.get_config().items():
            config_opt = dict(defaults, **config_opt)
            try:
                value = app.config[config_key]
            except KeyError:
                if config_opt['required']:
                    raise ValueError(f"Config key {config_key} is required")
                value = None

            if value is not None:
                if config_opt['parser']:
                    try:
                        value = config_opt['parser'](value)
                    except (TypeError, ValueError) as e:
                        raise ValueError(f"Failed to parse value {repr(value)} for config key {config_key}: {e}") from e

                if config_opt['validator']:
                    config_opt['validator'](value)

            app.config[config_key] = value


class FlaskConfigPlugin(Plugin):
    """\
    Load configuration from the environment.  This plugin should always be used,
    and should be loaded before any other plugins (or they may fail to load
    their own configs)
    """

    def __init__(self, app: Optional[Flask]=None, url_prefix: Optional[str]=None, env_prefix: str = 'FLASK'):
        super().__init__(app=app, url_prefix=url_prefix)
        self.env_prefix = env_prefix

    def get_config(self) -> Dict[str, Dict[str, Any]]:
        return {
            'SITE_NAME': {
                'parser': str,
                'required': True,
                'description': "Name of the site used for page titles and in other places",
            },
            'SITE_TIMEZONE': {
                'parser': str,
                'default': 'UTC',
                'description': "Default timezone of the site",
            },
            'DEBUG': {
                'parser': bool,
                'default': False,
                'description': "Whether debug mode is enabled.",
            },
            'TESTING': {
                'parser': bool,
                'default': False,
                'description': "Enable testing mode.",
            },
            'PROPAGATE_EXCEPTIONS': {
                'parser': bool,
                'description': "Exceptions are re-raised rather than being handled by the app’s error handlers.",
            },
            'TRAP_HTTP_EXCEPTIONS': {
                'parser': bool,
                'default': False,
                'description': "If there is no handler for an HTTPException-type exception, re-raise it to be handled by the interactive debugger instead of returning it as a simple error response.",
            },
            'TRAP_BAD_REQUEST_ERRORS': {
                'parser': bool,
                'description': "Trying to access a key that doesn’t exist from request dicts like args and form will return a 400 Bad Request error page. Enable this to treat the error as an unhandled exception instead so that you get the interactive debugger. This is a more specific version of TRAP_HTTP_EXCEPTIONS. If unset, it is enabled in debug mode.",
            },
            'SECRET_KEY': {
                'parser': str,
                'required': True,
                'description': "A secret key that will be used for securely signing the session cookie and can be used for any other security related needs by extensions or your application.",
            },
            'SESSION_COOKIE_NAME': {
                'parser': str,
                'default': 'session',
                'description': "The name of the session cookie.",
            },
            'SESSION_COOKIE_DOMAIN': {
                'parser': str,
                'description': "The value of the Domain parameter on the session cookie.",
            },
            'SESSION_COOKIE_PATH': {
                'parser': str,
                'description': "The path that the session cookie will be valid for.",
            },
            'SESSION_COOKIE_HTTPONLY': {
                'parser': bool,
                'default': True,
                'description': "Browsers will not allow JavaScript access to cookies marked as “HTTP only” for security.",
            },
            'SESSION_COOKIE_SECURE': {
                'parser': bool,
                'default': False,
                'description': "Browsers will only send cookies with requests over HTTPS if the cookie is marked “secure”.",
            },
            'SESSION_COOKIE_SAMESITE': {
                'parser': str,
                'description': "Restrict how cookies are sent with requests from external sites. Can be set to 'Lax' (recommended) or 'Strict'. See Set-Cookie options.",
            },
            'PERMANENT_SESSION_LIFETIME': {
                'parser': int,
                'default': 2678400,
                'description': "If session.permanent is true, the cookie’s expiration will be set this number of seconds in the future.",
            },
            'SESSION_REFRESH_EACH_REQUEST': {
                'parser': bool,
                'default': True,
                'description': "Control whether the cookie is sent with every response when session.permanent is true.",
            },
            'USE_X_SENDFILE': {
                'parser': bool,
                'default': False,
                'description': "When serving files, set the X-Sendfile header instead of serving the data with Flask.",
            },
            'SEND_FILE_MAX_AGE_DEFAULT': {
                'parser': int,
                'description': "When serving files, set the cache control max age to this number of seconds.",
            },
            'SERVER_NAME': {
                'parser': str,
                'description': "Inform the application what host and port it is bound to.",
            },
            'APPLICATION_ROOT': {
                'parser': str,
                'default': '/',
                'description': "Inform the application what path it is mounted under by the application / web server.",
            },
            'PREFERRED_URL_SCHEME': {
                'parser': str,
                'default': 'http',
                'description': "Use this scheme for generating external URLs when not in a request context.",
            },
            'MAX_CONTENT_LENGTH': {
                'parser': int,
                'description': "Don’t read more than this many bytes from the incoming request data.",
            },
            'TEMPLATES_AUTO_RELOAD': {
                'parser': bool,
                'description': "Reload templates when they are changed.",
            },
            'EXPLAIN_TEMPLATE_LOADING': {
                'parser': bool,
                'default': False,
                'description': "Log debugging information tracing how a template file was loaded.",
            },
            'MAX_COOKIE_SIZE': {
                'parser': int,
                'default': 4093,
                'description': "Warn if cookie headers are larger than this many bytes.",
            },
        }

    def init_app(self, app: Flask):
        load_dotenv()
        app.config.from_prefixed_env(self.env_prefix)
        super().init_app(app)


class ErrorHandlerPlugin(Plugin):
    """\
    Register a base error handler for all common HTTP errors, easily register
    custom error handlers
    """

    error_handlers = {'*': None}
    valid_err = (400,401,403,404,405,406,408,409,410,411,412,413,414,415,417,418,421,422,423,424,428,429,431,451,500,501,502,503,504,505)

    def __init__(self, app: Optional[Flask]=None, url_prefix: Optional[str]=None, default_error_template: str = 'base/error.html.j2'):
        """\
        Create the error handler plugijn
        """

        super().__init__(app=app, url_prefix=url_prefix)
        self.default_error_template = default_error_template

    @classmethod
    def register_error_handler(cls, errspec: Union[str, Exception], handler_or_template: Optional[Union[str, Callable]]):
        """\
        Register an error handler or template for a given code or exception.

        `errspec` must be one of the following:
        * A specific HTTP error code, to handle only that error
        * A string like "4xx" or "5xx" to handle 400-499 or 500-599 respectively
        * A specific range, like "401-403"
        * A comma separated list, like "401,403"
        * An asterisk, "*", to handle all otherwise unhandled HTTPException subclasses
        * A special case, "exc" - in which case the value is 2-tuples of an exception class & either a template name or function

        `handler_or_template` may be an error handler function, or template name to render.  If None, the default error template is used.

        Error handler functions must accept the exception being handled, and return a valid response.  Templates are rendered with:
        * err=exception to be handled
        * code=exception "code" attribute (may be None in the case of non-http errors)
        * name=exception "name" attribute (may be None in the case of non-http errors)
        * description=exception "description" attribute (may be None in the case of non-http errors)

        By default, "*" is sent through "base/error.html.j2"

        Must be called before init_app - create the plugin outside of app creation, then register error handlers before calling init_app
        """
        if isinstance(errspec, type) and issubclass(errspec, Exception):
            cls.error_handlers.setdefault('exc', [])
            cls.error_handlers['exc'] = [(e, h) for e, h in cls.error_handlers['exc'] if e != errspec]
            cls.error_handlers['exc'].append((errspec, handler_or_template))
        else:
            cls.error_handlers[errspec] = handler_or_template

    @staticmethod
    def _template_error_handler(template: str, e: Exception) -> Tuple[str, int]:
        """\
        Error handler function to render an error template for a given exception.
        """

        logger.error('%s', e)
        return (
            render_template(
                template,
                err=e,
                code=getattr(e, 'code', None),
                name=getattr(e, 'name', None),
                description=getattr(e, 'description', None)
            ),
            getattr(e, 'code', 500)
        )

    @classmethod
    def _make_template_error_handler(cls, template: str) -> Callable[[Exception], Callable[[str, Exception], Tuple[str, int]]]:
        """\
        Given a template, generate the error handler to render the template.
        """

        return lambda e: cls._template_error_handler(template, e)

    @staticmethod
    def _parse_errspec(es):
        if isinstance(es, int):
            yield es
        else:
            es = str(es)
            if es == '*':
                yield HTTPException
            elif 'x' in es:
                start = int(es[0] + '00')
                yield from range(start, start + 100)
            elif '-' in es:
                start, end = map(int, es.split('-'))
                yield from range(start, end + 1)
            elif ',' in es:
                yield from map(int, es.split(','))

    def _register_error_handlers(self, app: Flask):
        """\
        Register error handlers previously defined
        """

        for errspec, errhandler in self.error_handlers.items():
            if errspec == 'exc':
                for ecls, ehdr in errhandler:
                    if ehdr is None:
                        ehdr = self.default_error_template
                    handler = ehdr if callable(ehdr) else self._make_template_error_handler(ehdr)
                    app.register_error_handler(ecls, handler)
            else:
                if errhandler is None:
                    errhandler = self.default_error_template
                handler = errhandler if callable(errhandler) else self._make_template_error_handler(errhandler)
                for code in self._parse_errspec(errspec):
                    if isinstance(code, int) and code not in self.valid_err:
                        continue
                    app.register_error_handler(code, handler)

    def init_app(self, app: Flask):
        super().init_app(app)
        self._register_error_handlers(app)
