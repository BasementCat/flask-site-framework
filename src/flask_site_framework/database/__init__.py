"""Database functionality

Initialization:

    from flask_site_framework.database import db, migrate

    def create_app():
        [...]
        db.init_app(app)
        migrate.init_app(app)
        [...]
        return app

For models:

    from flask_site_framework.database import db

    class MyModel(db.Model):
        [...]

Ensure all models are imported in your create_app function, and use the usual
commands to setup & generate migrations.

Setup:

* flask db init
* flask database init

Migrations:

* flask db migrate
* flask db upgrade
"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_migrate import Migrate
from alembic import context
from alembic.autogenerate import rewriter
from alembic.operations import ops

from .. import Plugin
from .. import event

from . import db_types


class BaseModel(DeclarativeBase):
    """Base model used for SQLAlchemy - do not use directly!  Use db.Model"""
    pass

db = SQLAlchemy(model_class=BaseModel)
"""Flask-SQLAlchemy flask plugin, providing the base model & fields"""
migrate = Migrate(None, db)
"""Instance of Alembic plugin"""


@migrate.configure
def configure_alembic(config):
    if config.get_main_option('file_template') is None:
        config.set_main_option('file_template', '%%(year)d_%%(month).2d_%%(day).2d_%%(hour).2d%%(minute).2d-%%(rev)s_%%(slug)s')
    return config


@event.subscribes_to('alembic.env.context_config')
def configure_alembic_runtime(event, config, *args, online=False, **kwargs):
    writer = rewriter.Rewriter()

    @writer.rewrites(ops.MigrationScript)
    def add_imports(context, revision, op):
        op.imports.add(f'import {db_types.__name__} as custom_types')
        return [op]

    config['process_revision_directives'] = writer
    config['user_module_prefix'] = 'custom_types.'
    return config


class DatabasePlugin(Plugin):
    """\
    Provides database & migration functionality to the application
    """

    def get_config(self):
        return {
            'SQLALCHEMY_DATABASE_URI': {
                'required': True,
                'description': "SQLAlchemy database URI",
            },
        }

    def get_flask_plugins(self):
        return [
            db,
            migrate,
        ]

    def get_commands(self):
        from . import commands
        return [commands.cli]
