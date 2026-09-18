from unittest import TestCase
from unittest.mock import patch, MagicMock

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from alembic.operations import ops

from flask_site_framework import database as db
from flask_site_framework.database import commands


class TestPluginsCreated(TestCase):
    def test_plugins_created(self):
        self.assertTrue(isinstance(db.db, SQLAlchemy))
        self.assertTrue(isinstance(db.migrate, Migrate))


class TestConfigureAlembic(TestCase):
    def test_file_template_not_set(self):
        config = MagicMock()
        config.get_main_option.return_value = None
        res = db.configure_alembic(config)
        config.get_main_option.assert_called_once_with('file_template')
        config.set_main_option.assert_called_once_with('file_template', '%%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s')
        self.assertEqual(res, config)

    def test_file_template_is_set(self):
        config = MagicMock()
        config.get_main_option.return_value = 'asdf'
        res = db.configure_alembic(config)
        config.get_main_option.assert_called_once_with('file_template')
        config.set_main_option.assert_not_called()
        self.assertEqual(res, config)


class TestConfigureAlembicRuntime(TestCase):
    def test_configure_alembic_runtime(self):
        rewrite_fns = []
        def capture_rewrite_fn(callback):
            rewrite_fns.append(callback)
        with patch('flask_site_framework.database.rewriter.Rewriter') as mock_rewriter:
            mock_rewriter.return_value.rewrites.return_value.side_effect = capture_rewrite_fn
            config = {}
            res = db.configure_alembic_runtime('test', config)
            mock_rewriter.assert_called_once_with()
            mock_rewriter.return_value.rewrites.assert_called_once_with(ops.MigrationScript)
            mock_rewriter.return_value.rewrites.return_value.assert_called_once()
            self.assertEqual(config, {
                'process_revision_directives': mock_rewriter.return_value,
                'user_module_prefix': 'custom_types.',
            })
            self.assertEqual(res, config)
            self.assertEqual(len(rewrite_fns), 1)
            mock_op = MagicMock()
            res = rewrite_fns[0]('ctx', 'rev', mock_op)
            mock_op.imports.add.assert_called_once_with('import flask_site_framework.database.db_types as custom_types')
            self.assertEqual(res, [mock_op])


class TestDatabasePlugin_GetConfig(TestCase):
    def test_get_config(self):
        p = db.DatabasePlugin()
        res = p.get_config()
        self.assertIn('SQLALCHEMY_DATABASE_URI', res)


class TestDatabasePlugin_GetFlaskPlugins(TestCase):
    def test_get_flask_plugins(self):
        p = db.DatabasePlugin()
        res = p.get_flask_plugins()
        self.assertEqual(res, [db.db, db.migrate])


class TestDatabasePlugin_GetCommands(TestCase):
    def test_get_commands(self):
        p = db.DatabasePlugin()
        res = p.get_commands()
        self.assertEqual(res, [commands.cli])

