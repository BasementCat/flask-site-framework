from unittest import TestCase
from unittest.mock import patch, MagicMock, call

from werkzeug.exceptions import HTTPException, NotFound

from flask_site_framework import ErrorHandlerPlugin


@patch('flask_site_framework.Plugin.__init__')
class TestInit(TestCase):
    def test_no_args(self, mock_super_init):
        p = ErrorHandlerPlugin()
        mock_super_init.assert_called_once_with(app=None, url_prefix=None)
        self.assertEqual(p.default_error_template, 'base/error.html.j2')

    def test_with_args(self, mock_super_init):
        p = ErrorHandlerPlugin('foo', url_prefix='bar', default_error_template='baz')
        mock_super_init.assert_called_once_with(app='foo', url_prefix='bar')
        self.assertEqual(p.default_error_template, 'baz')


class TestRegisterErrorHandler(TestCase):
    def test_register(self):
        eh = {'*': 'dfl'}
        with patch('flask_site_framework.ErrorHandlerPlugin.error_handlers', eh):
            ErrorHandlerPlugin.register_error_handler(TypeError, 'foo')
            ErrorHandlerPlugin.register_error_handler(ValueError, 'bar')
            ErrorHandlerPlugin.register_error_handler(ValueError, 'baz')
            ErrorHandlerPlugin.register_error_handler(404, 'quux')
            ErrorHandlerPlugin.register_error_handler('5xx', 'asdf')
            self.assertEqual(ErrorHandlerPlugin.error_handlers, {
                '*': 'dfl',
                'exc': [
                    (TypeError, 'foo'),
                    (ValueError, 'baz')
                ],
                404: 'quux',
                '5xx': 'asdf',
            })


@patch('flask_site_framework.logger')
@patch('flask_site_framework.render_template')
class TestTemplateErrorHandler(TestCase):
    def test_with_httpexc(self, mock_render_tpl, mock_logger):
        e = NotFound()
        res = ErrorHandlerPlugin._template_error_handler('foo', e)
        mock_logger.error.assert_called_once_with('%s', e)
        mock_render_tpl.assert_called_once_with(
            'foo',
            err=e,
            code=404,
            name='Not Found',
            description='The requested URL was not found on the server. If you entered the URL manually please check your spelling and try again.',
        )
        self.assertEqual(res, (mock_render_tpl.return_value, 404))

    def test_with_other_exc(self, mock_render_tpl, mock_logger):
        e = ValueError()
        res = ErrorHandlerPlugin._template_error_handler('foo', e)
        mock_logger.error.assert_called_once_with('%s', e)
        mock_render_tpl.assert_called_once_with(
            'foo',
            err=e,
            code=None,
            name=None,
            description=None,
        )
        self.assertEqual(res, (mock_render_tpl.return_value, 500))


@patch('flask_site_framework.ErrorHandlerPlugin._template_error_handler')
class TestMakeTemplateErrorHandler(TestCase):
    def test_make_tpl_handler(self, mock_tpl_handler):
        res = ErrorHandlerPlugin._make_template_error_handler('foo')
        e = ValueError()
        res(e)
        mock_tpl_handler.assert_called_once_with('foo', e)

class TestParseErrspec(TestCase):
    def test_int(self):
        res = ErrorHandlerPlugin._parse_errspec(404)
        self.assertEqual(list(res), [404])

    def test_all(self):
        res = ErrorHandlerPlugin._parse_errspec('*')
        self.assertEqual(list(res), [HTTPException])

    def test_nxx(self):
        res = ErrorHandlerPlugin._parse_errspec('4xx')
        self.assertEqual(list(res), list(range(400, 500)))

    def test_range(self):
        res = ErrorHandlerPlugin._parse_errspec('500-502')
        self.assertEqual(list(res), list(range(500, 503)))

    def test_list(self):
        res = ErrorHandlerPlugin._parse_errspec('401,501')
        self.assertEqual(list(res), [401, 501])


@patch('flask_site_framework.ErrorHandlerPlugin._make_template_error_handler')
@patch('flask_site_framework.ErrorHandlerPlugin._parse_errspec', side_effect=lambda v: [1,v])
class TestRegisterErrorHandlers(TestCase):
    def test_register(self, mock_parse_errspec, mock_mk_tpl_ehdr):
        mock_app = MagicMock()
        p = ErrorHandlerPlugin()
        mock_handler = lambda v: v
        handlers = {
            'exc': [
                (TypeError, None),
                (ValueError, mock_handler),
                (RuntimeError, 'foo'),
            ],
            400: None,
            401: mock_handler,
            402: 'invalid',
            403: 'asdf',
        }
        with patch('flask_site_framework.ErrorHandlerPlugin.error_handlers', handlers):
            p._register_error_handlers(mock_app)
            mock_mk_tpl_ehdr.assert_has_calls([
                call('base/error.html.j2'),
                call('foo'),
                call('base/error.html.j2'),
                call('invalid'),
                call('asdf'),
            ])
            mock_parse_errspec.assert_has_calls([
                call(400),
                call(401),
                call(402),
                call(403),
            ])
            mock_app.register_error_handler.assert_has_calls([
                call(TypeError, mock_mk_tpl_ehdr.return_value),
                call(ValueError, mock_handler),
                call(RuntimeError, mock_mk_tpl_ehdr.return_value),
                call(400, mock_mk_tpl_ehdr.return_value),
                call(401, mock_handler),
                call(403, mock_mk_tpl_ehdr.return_value),
            ])


@patch('flask_site_framework.Plugin.init_app')
@patch('flask_site_framework.ErrorHandlerPlugin._register_error_handlers')
class TestInitApp(TestCase):
    def test_init(self, mock_reg, mock_init):
        mock_app = MagicMock()
        p = ErrorHandlerPlugin()
        p.init_app(mock_app)
        mock_init.assert_called_once_with(mock_app)
        mock_reg.assert_called_once_with(mock_app)