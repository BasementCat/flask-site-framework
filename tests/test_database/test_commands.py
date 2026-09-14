from unittest import TestCase
from unittest.mock import patch, MagicMock, call
import io
import os

from flask import Flask

from src.flask_site_framework.database import commands as cmd


@patch('src.flask_site_framework.database.commands.os.path.exists')
class TestMakeMigrationsEnvPath(TestCase):
    def test_no_path(self, mock_exists):
        app = Flask(__name__)
        app.root_path = '/test/app'
        with app.app_context(), app.test_request_context():
            res = cmd._make_migrations_env_path(None)
            self.assertEqual(res, ('/test/migrations/env.py', mock_exists.return_value))

    def test_empty_path(self, mock_exists):
        app = Flask(__name__)
        app.root_path = '/test/app'
        with app.app_context(), app.test_request_context():
            res = cmd._make_migrations_env_path('')
            self.assertEqual(res, ('/test/migrations/env.py', mock_exists.return_value))

    def test_relative_path(self, mock_exists):
        app = Flask(__name__)
        app.root_path = '/test/app'
        with app.app_context(), app.test_request_context():
            res = cmd._make_migrations_env_path('relpath')
            self.assertEqual(res, ('/test/relpath/env.py', mock_exists.return_value))

    def test_absolute_path(self, mock_exists):
        app = Flask(__name__)
        app.root_path = '/test/app'
        with app.app_context(), app.test_request_context():
            res = cmd._make_migrations_env_path('/abspath')
            self.assertEqual(res, ('/abspath/env.py', mock_exists.return_value))



@patch('src.flask_site_framework.database.commands._make_migrations_env_path')
@patch('src.flask_site_framework.database.commands.sys.stderr')
@patch('src.flask_site_framework.database.commands.open')
@patch('src.flask_site_framework.database.commands.print')
class TestDatabaseInit(TestCase):
    def test_path_does_not_exist(self, mock_print, mock_open, mock_stderr, mock_mk_path):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            mock_mk_path.return_value = ('foo', False)
            with self.assertRaises(SystemExit):
                cmd.database_init([])
            mock_mk_path.assert_called_once_with(None)
            mock_open.assert_not_called()

    def test_marker_is_present(self, mock_print, mock_open, mock_stderr, mock_mk_path):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            mock_mk_path.return_value = ('foo', True)
            mock_open.return_value = io.StringIO(cmd.MARKER)
            with self.assertRaises(SystemExit):
                cmd.database_init([])
            mock_mk_path.assert_called_once_with(None)
            mock_open.assert_called_once_with('foo', 'r')

    def test_file_written(self, mock_print, mock_open, mock_stderr, mock_mk_path):
        app = Flask(__name__)
        with app.app_context(), app.test_request_context():
            mock_mk_path.return_value = ('foo', True)
            mock_output_file = MagicMock()
            mock_open.side_effect = [
                # First call - read the existing file to determine if the marker is present
                io.StringIO('asdf'),
                # Second call - read the template file
                io.StringIO('test marker {{MARKER}}\ntest module {{MODULE}}\n'),
                # Third call - write the modified file
                mock_output_file,
            ]
            with self.assertRaises(SystemExit):
                cmd.database_init([])
            mock_mk_path.assert_called_once_with(None)
            tpl_path = os.path.abspath(os.path.normpath(os.path.join(
                os.path.dirname(__file__), '..', '..', 'src', 'flask_site_framework', 'database', 'env.py.template'
            )))
            mock_open.assert_has_calls([
                call('foo', 'r'),
                call(tpl_path, 'r'),
                call('foo', 'w'),
            ])
            mock_output_file.__enter__.return_value.write.assert_called_once_with(f'test marker {cmd.MARKER}\ntest module flask_site_framework\n')
