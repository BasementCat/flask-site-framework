from unittest import TestCase
from unittest.mock import patch, MagicMock

from src.flask_site_framework import Plugin


@patch('src.flask_site_framework.Plugin.init_app')
class TestInit(TestCase):
    def test_init__no_args(self, mock_init_app):
        p = Plugin()
        self.assertIsNone(p.url_prefix)
        mock_init_app.assert_not_called()

    def test_init__with_args(self, mock_init_app):
        p = Plugin('foo', url_prefix='bar')
        self.assertEqual(p.url_prefix, 'bar')
        mock_init_app.assert_called_once_with('foo')


@patch('src.flask_site_framework.Plugin.get_flask_plugins', return_value=[])
@patch('src.flask_site_framework.Plugin.get_blueprints', return_value=[])
@patch('src.flask_site_framework.Plugin.get_commands', return_value=[])
@patch('src.flask_site_framework.Plugin._load_config')
class TestInitApp(TestCase):
    def test_nothing_to_do(self, mock_load_config, mock_get_commands, mock_get_blueprints, mock_get_plugins):
        mock_app = MagicMock()
        p = Plugin()
        p.init_app(mock_app)
        mock_get_plugins.assert_called_once_with()
        mock_get_blueprints.assert_called_once_with()
        mock_app.register_blueprint.assert_not_called()
        mock_get_commands.assert_called_once_with()
        mock_app.cli.add_command.assert_not_called()
        mock_load_config.assert_called_once_with(mock_app)

    def test_init_flask_plugins(self, mock_load_config, mock_get_commands, mock_get_blueprints, mock_get_plugins):
        mock_app = MagicMock()
        mock_plugin = MagicMock()
        mock_get_plugins.return_value = [mock_plugin]
        p = Plugin()
        p.init_app(mock_app)
        mock_plugin.init_app.assert_called_once_with(mock_app)

    def test_init_blueprints(self, mock_load_config, mock_get_commands, mock_get_blueprints, mock_get_plugins):
        mock_app = MagicMock()
        mock_get_blueprints.return_value = [('/foo/bar/', 'bp')]
        p = Plugin()
        p.init_app(mock_app)
        mock_app.register_blueprint.assert_called_once_with('bp', url_prefix='/foo/bar')

    def test_init_blueprints__with_url_prefix(self, mock_load_config, mock_get_commands, mock_get_blueprints, mock_get_plugins):
        mock_app = MagicMock()
        mock_get_blueprints.return_value = [('/foo/bar/', 'bp')]
        p = Plugin(url_prefix='/baz/quux/')
        p.init_app(mock_app)
        mock_app.register_blueprint.assert_called_once_with('bp', url_prefix='/baz/quux/foo/bar')

    def test_init_commands(self, mock_load_config, mock_get_commands, mock_get_blueprints, mock_get_plugins):
        mock_app = MagicMock()
        mock_get_commands.return_value = ['group']
        p = Plugin()
        p.init_app(mock_app)
        mock_app.cli.add_command.assert_called_once_with('group')


@patch('src.flask_site_framework.Plugin.get_config', return_value={})
class TestLoadConfig(TestCase):
    def test_no_config(self, mock_get_config):
        p = Plugin()
        mock_app = MagicMock(config={})
        p._load_config(mock_app)
        mock_get_config.assert_called_once_with()
        self.assertEqual(mock_app.config, {})

    def test_missing_required_config(self, mock_get_config):
        def test_v(v):
            pass
        mock_get_config.return_value = {
            'FOO': {},
            'BAR': {'required': True},
            'BAZ': {'parser': int},
            'QUUX': {'parser': float},
            'ASDF': {'validator': test_v},
        }
        p = Plugin()
        mock_app = MagicMock(config={
            'FOO': 'asdf',
            'BAZ': '3',
            'QUUX': '5.6',
            'ASDF': 'lksjdkfls',
        })
        with self.assertRaisesRegex(ValueError, 'is required'):
            p._load_config(mock_app)

    def test_parser_fails__type(self, mock_get_config):
        def test_v(v):
            pass
        mock_get_config.return_value = {
            'FOO': {},
            'BAR': {'required': True},
            'BAZ': {'parser': int},
            'QUUX': {'parser': float},
            'ASDF': {'validator': test_v},
        }
        p = Plugin()
        mock_app = MagicMock(config={
            'FOO': 'asdf',
            'BAR': 'qwerty',
            'BAZ': [],
            'QUUX': '5.6',
            'ASDF': 'lksjdkfls',
        })
        with self.assertRaisesRegex(ValueError, 'Failed to parse'):
            p._load_config(mock_app)

    def test_parser_fails__value(self, mock_get_config):
        def test_v(v):
            pass
        mock_get_config.return_value = {
            'FOO': {},
            'BAR': {'required': True},
            'BAZ': {'parser': int},
            'QUUX': {'parser': float},
            'ASDF': {'validator': test_v},
        }
        p = Plugin()
        mock_app = MagicMock(config={
            'FOO': 'asdf',
            'BAR': 'qwerty',
            'BAZ': 'lksdfkls',
            'QUUX': '5.6',
            'ASDF': 'lksjdkfls',
        })
        with self.assertRaisesRegex(ValueError, 'Failed to parse'):
            p._load_config(mock_app)

    def test_validator_fails(self, mock_get_config):
        def test_v(v):
            raise RuntimeError('fail')
        mock_get_config.return_value = {
            'FOO': {},
            'BAR': {'required': True},
            'BAZ': {'parser': int},
            'QUUX': {'parser': float},
            'ASDF': {'validator': test_v},
        }
        p = Plugin()
        mock_app = MagicMock(config={
            'FOO': 'asdf',
            'BAR': 'qwerty',
            'BAZ': '3',
            'QUUX': '5.6',
            'ASDF': 'lksjdkfls',
        })
        with self.assertRaisesRegex(RuntimeError, 'fail'):
            p._load_config(mock_app)

    def test_success(self, mock_get_config):
        def test_v(v):
            pass
        mock_get_config.return_value = {
            'FOO': {'description': 'asdf'},
            'BAR': {'required': True},
            'BAZ': {'parser': int},
            'QUUX': {'parser': float},
            'ASDF': {'validator': test_v},
        }
        p = Plugin()
        mock_app = MagicMock(config={
            'FOO': 'asdf',
            'BAR': 'qwerty',
            'BAZ': '3',
            'QUUX': '5.6',
            'ASDF': 'lksjdkfls',
        })
        mock_app._config = 'asdf'
        del mock_app._config
        p._load_config(mock_app)
        self.assertEqual(mock_app.config, {
            'FOO': 'asdf',
            'BAR': 'qwerty',
            'BAZ': 3,
            'QUUX': 5.6,
            'ASDF': 'lksjdkfls',
        })
        self.assertEqual(mock_app._config, {
            'FOO': {
                'parser': None,
                'validator': None,
                'default': None,
                'required': False,
                'description': 'asdf',
            },
            'BAR': {
                'parser': None,
                'validator': None,
                'default': None,
                'required': True,
                'description': '',
            },
            'BAZ': {
                'parser': int,
                'validator': None,
                'default': None,
                'required': False,
                'description': '',
            },
            'QUUX': {
                'parser': float,
                'validator': None,
                'default': None,
                'required': False,
                'description': '',
            },
            'ASDF': {
                'parser': None,
                'validator': test_v,
                'default': None,
                'required': False,
                'description': '',
            },
        })
