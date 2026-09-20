import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
import functools

from flask import Flask


@contextmanager
def mock_app(config):
    app = Flask(__name__)
    app.config.update(config)
    app.email = MagicMock()
    with app.app_context():
        yield app


@contextmanager
def mock_real_app(config):
    from flask_site_framework.bootstrap import BootstrapPlugin
    from flask_site_framework.jinja import JinjaPlugin
    app = Flask(__name__)
    app.config.update(config)
    BootstrapPlugin(app, with_fontawesome=True)
    JinjaPlugin(app)
    app.email = MagicMock()
    with app.app_context():
        yield app


@contextmanager
def mock_blueprint(app, bp, prefix=''):
    app.register_blueprint(bp, url_prefix=prefix)
    client = app.test_client()
    yield client


class MockUser:
    def __init__(self, **kwargs):
        self.username = 'test.user'
        self.email = 'test@test.test'
        self.new_email = None
        self.email_confirmation_code = None
        self.email_confirmation_expiration = None
        self.password_reset_code = None
        self.password_reset_expiration = None
        self.new_totp_secret = None
        self.totp_secret = None
        self.totp_backup_codes = None
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockPublish:
    def __init__(self, target, return_values=None, callback=None):
        self.target = target
        self.return_values = return_values or {}
        self.callback = callback

    def __enter__(self):
        self.p = patch(self.target, new=self)
        self.p.__enter__()
        return self

    def __exit__(self, *args):
        self.p.__exit__(*args)

    def __call__(self, event, init_arg=None, *args, **kwargs):
        if event in self.return_values:
            return self.return_values[event]
        if self.callback:
            return self.callback(event, init_arg, *args, **kwargs)
        return init_arg
