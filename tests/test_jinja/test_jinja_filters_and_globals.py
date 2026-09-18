from unittest import TestCase
from unittest.mock import patch, MagicMock
import math

from flask import Flask, request
import arrow

from flask_site_framework import jinja
from flask_site_framework.event import publish


class TestDefaults(TestCase):
    def test_fns_in_defaults(self):
        self.assertEqual(jinja.jinja_data['globals']['publish_event'], publish)
        self.assertEqual(jinja.jinja_data['filters']['ceil'], math.ceil)
        self.assertEqual(jinja.jinja_data['filters']['floor'], math.floor)


class TestRouteMatches(TestCase):
    def test_only_route_matches(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            request.url_rule = MagicMock(endpoint='test.endpoint')
            request.view_args = {'foo': 'bar', 'baz': 'quux'}
            self.assertTrue(jinja.route_matches('test.endpoint'))

        # path – URL path being requested.
        # base_url – Base URL where the app is being served, which path is relative to. If not given, built from PREFERRED_URL_SCHEME, subdomain, SERVER_NAME, and APPLICATION_ROOT.
        # subdomain – Subdomain name to append to SERVER_NAME.
        # url_scheme – Scheme to use instead of PREFERRED_URL_SCHEME.
        # data – The request body, either as a string or a dict of form keys and values.
        # json – If given, this is serialized as JSON and passed as data. Also defaults content_type to application/json.
        # args (Any) – other positional arguments passed to EnvironBuilder.
        # kwargs (Any) – other keyword arguments passed to EnvironBuilder.
        # query_string (t.Mapping[str, str] | str | None) – an optional string or dict with URL parameters.


    def test_only_route_does_not_match(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            request.url_rule = MagicMock(endpoint='test.otherendpoint')
            request.view_args = {'foo': 'bar', 'baz': 'quux'}
            self.assertFalse(jinja.route_matches('test.endpoint'))

    def test_route_and_args_matches(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            request.url_rule = MagicMock(endpoint='test.endpoint')
            request.view_args = {'foo': 'bar', 'baz': 'quux'}
            self.assertTrue(jinja.route_matches('test.endpoint', foo='bar'))

    def test_route_and_args_does_not_match(self):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            request.url_rule = MagicMock(endpoint='test.endpoint')
            request.view_args = {'foo': 'bar', 'baz': 'quux'}
            self.assertFalse(jinja.route_matches('test.endpoint', foo='bar', baz='asdf'))


@patch('flask_site_framework.jinja.arrow.utcnow')
class TestNow(TestCase):
    def test_now(self, mock_utcnow):
        res = jinja.now()
        self.assertEqual(res, mock_utcnow.return_value)


@patch('flask_site_framework.jinja.event.publish', side_effect=lambda e, v: v)
class TestDT(TestCase):
    def test_full_fmt__all(self, mock_publish):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            app.config['SITE_TIMEZONE'] = 'America/Denver'
            dt = arrow.get('2026-09-07 10:03:00', tzinfo='UTC')
            res = jinja.dt(dt)
            mock_publish.assert_called_once_with('jinja.dt.timezone', 'America/Denver')
            self.assertEqual(res, 'September 7th, 2026 4:03 AM')

    def test_full_fmt__date(self, mock_publish):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            app.config['SITE_TIMEZONE'] = 'America/Denver'
            dt = arrow.get('2026-09-07 10:03:00', tzinfo='UTC')
            res = jinja.dt(dt, part='date')
            mock_publish.assert_called_once_with('jinja.dt.timezone', 'America/Denver')
            self.assertEqual(res, 'September 7th, 2026')

    def test_full_fmt__time(self, mock_publish):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            app.config['SITE_TIMEZONE'] = 'America/Denver'
            dt = arrow.get('2026-09-07 10:03:00', tzinfo='UTC')
            res = jinja.dt(dt, part='time')
            mock_publish.assert_called_once_with('jinja.dt.timezone', 'America/Denver')
            self.assertEqual(res, '4:03 AM')

    def test_alt_tz(self, mock_publish):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            app.config['SITE_TIMEZONE'] = 'America/Denver'
            mock_publish.side_effect = None
            mock_publish.return_value = 'America/Chicago'
            dt = arrow.get('2026-09-07 10:03:00', tzinfo='UTC')
            res = jinja.dt(dt)
            mock_publish.assert_called_once_with('jinja.dt.timezone', 'America/Denver')
            self.assertEqual(res, 'September 7th, 2026 5:03 AM')

