from unittest import TestCase
from unittest.mock import patch, MagicMock

from flask import Flask
from flask_bootstrap import Bootstrap4, Bootstrap5

from src.flask_site_framework import bootstrap as bs


@patch('src.flask_site_framework.Plugin.__init__')
class TestBootstrapPlugin_Init(TestCase):
    def test_defaults(self, mock_super_init):
        p = bs.BootstrapPlugin()
        mock_super_init.assert_called_once_with()
        self.assertFalse(p.with_fontawesome)
        self.assertEqual(p.bootstrap_plugin, Bootstrap5)

    def test_super_called(self, mock_super_init):
        p = bs.BootstrapPlugin('foo', bar='baz')
        mock_super_init.assert_called_once_with('foo', bar='baz')

    def test_with_fa(self, mock_super_init):
        p = bs.BootstrapPlugin(with_fontawesome='foo')
        mock_super_init.assert_called_once_with()
        self.assertEqual(p.with_fontawesome, 'foo')
        self.assertEqual(p.bootstrap_plugin, Bootstrap5)

    def test_alt_bs_version(self, mock_super_init):
        p = bs.BootstrapPlugin(bootstrap_version=4)
        mock_super_init.assert_called_once_with()
        self.assertFalse(p.with_fontawesome)
        self.assertEqual(p.bootstrap_plugin, Bootstrap4)

    def test_invalid_bs_version(self, mock_super_init):
        with self.assertRaises(KeyError):
            p = bs.BootstrapPlugin(bootstrap_version=3)
        mock_super_init.assert_called_once_with()


class TestBootstrapPlugin_GetFlaskPlugins(TestCase):
    def test_get_flask_plugins(self):
        p = bs.BootstrapPlugin()
        res = p.get_flask_plugins()
        self.assertEqual(len(res), 1)
        self.assertTrue(isinstance(res[0], Bootstrap5))


class TestBootstrapPlugin_GetBlueprints(TestCase):
    def test_get_blueprints(self):
        p = bs.BootstrapPlugin()
        res = p.get_blueprints()
        self.assertEqual(len(res), 1)
        self.assertIsNone(res[0][0])
        self.assertEqual(res[0][1].name, '_base_bs')
        self.assertEqual(res[0][1].import_name, 'src.flask_site_framework.bootstrap')
        self.assertEqual(res[0][1].url_prefix, '/fsf/bs')
        self.assertTrue(res[0][1].static_folder.endswith('/flask_site_framework/static'))
        self.assertEqual(res[0][1].template_folder, 'templates')


@patch('src.flask_site_framework.bootstrap.url_for', return_value='foo')
class TestBootstrapPlugin_GetFontawesomeStylesheet(TestCase):
    def test_no_with_fa(self, mock_url_for):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            p = bs.BootstrapPlugin()
            res = p.get_fontawesome_stylesheet('test', [])
            mock_url_for.assert_not_called()
            self.assertEqual(res, [])

    def test_with_fa_is_true(self, mock_url_for):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            p = bs.BootstrapPlugin(with_fontawesome=True)
            res = p.get_fontawesome_stylesheet('test', [])
            mock_url_for.assert_not_called()
            self.assertEqual(res, ['<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/7.3.1/css/all.min.css" integrity="sha512-QeR2VH+lsBE5LSAe1Q5EnTBbe7XTBubt8dG93Y7gidSgdMCr8nVqKcfKAMyN96SV8KDbZVTDXChatu5G2KQGzg==" crossorigin="anonymous" referrerpolicy="no-referrer">'])

    def test_with_fa_is_version(self, mock_url_for):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            p = bs.BootstrapPlugin(with_fontawesome='7.3.1')
            res = p.get_fontawesome_stylesheet('test', [])
            mock_url_for.assert_not_called()
            self.assertEqual(res, ['<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/7.3.1/css/all.min.css" integrity="sha512-QeR2VH+lsBE5LSAe1Q5EnTBbe7XTBubt8dG93Y7gidSgdMCr8nVqKcfKAMyN96SV8KDbZVTDXChatu5G2KQGzg==" crossorigin="anonymous" referrerpolicy="no-referrer">'])

    def test_invalid_fa_version(self, mock_url_for):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            with self.assertRaises(KeyError):
                p = bs.BootstrapPlugin(with_fontawesome='1.2.3')
                res = p.get_fontawesome_stylesheet('test', [])
            mock_url_for.assert_not_called()

    def test_serve_local(self, mock_url_for):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            app.config['BOOTSTRAP_SERVE_LOCAL'] = True
            p = bs.BootstrapPlugin(with_fontawesome=True)
            res = p.get_fontawesome_stylesheet('test', [])
            mock_url_for.assert_called_once_with('_base_bs.static', filename='css/fontawesome/v7.3.1-all.min.css')
            self.assertEqual(res, ['<link rel="stylesheet" href="foo">'])


@patch('src.flask_site_framework.Plugin.init_app')
@patch('src.flask_site_framework.bootstrap.subscribe')
class TestBootstrapPlugin_InitApp(TestCase):
    def test_default(self, mock_sub, mock_init_app):
        mock_app = MagicMock()
        p = bs.BootstrapPlugin()
        p.init_app(mock_app)
        mock_init_app.assert_called_once_with(mock_app)
        mock_sub.assert_not_called()

    def test_with_fa(self, mock_sub, mock_init_app):
        mock_app = MagicMock()
        p = bs.BootstrapPlugin(with_fontawesome=True)
        p.init_app(mock_app)
        mock_init_app.assert_called_once_with(mock_app)
        mock_sub.assert_called_once_with('base.template.stylesheets', p.get_fontawesome_stylesheet)


class TestFontawesomeHelpers_Base(TestCase):
    def test_fa_defaults(self):
        res = str(bs.fa('foo'))
        self.assertEqual(res, '<span class="fa fa-foo "></span>')

    def test_fa_with_args(self):
        res = str(bs.fa('foo', collection='far', cls='bar'))
        self.assertEqual(res, '<span class="far fa-foo bar"></span>')


@patch('src.flask_site_framework.bootstrap.fa')
class TestFontawesomeHelpers_Other(TestCase):
    def test_fas_defaults(self, mock_fa):
        res = bs.fas('foo')
        mock_fa.assert_called_once_with('foo', collection='fas', cls='')
        self.assertEqual(res, mock_fa.return_value)

    def test_fas_with_args(self, mock_fa):
        res = bs.fas('foo', collection='far', cls='bar')
        mock_fa.assert_called_once_with('foo', collection='far', cls='bar')
        self.assertEqual(res, mock_fa.return_value)

    def test_fab_defaults(self, mock_fa):
        res = bs.fab('foo')
        mock_fa.assert_called_once_with('foo', collection='fab', cls='')
        self.assertEqual(res, mock_fa.return_value)

    def test_fab_with_args(self, mock_fa):
        res = bs.fab('foo', collection='far', cls='bar')
        mock_fa.assert_called_once_with('foo', collection='far', cls='bar')
        self.assertEqual(res, mock_fa.return_value)

