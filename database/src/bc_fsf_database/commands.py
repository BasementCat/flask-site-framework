"""Database commands"""

import os, sys, re

import click
from flask import Flask, current_app
from flask.cli import AppGroup


cli = AppGroup('database')
MARKER = '9ec5e472d35c'


@cli.command('init')
@click.option('-p', '--path', help="Path to Alembic migrations folder, relative to the application root path or an absolute path (default is 'migrations' relative to root path)")
def database_init(path: str):
    """\
    Custom database initialization, to be run after `flask db init`
    """
    path = path or 'migrations'
    if not path.startswith('/'):
        path = os.path.join(current_app.root_path, '..', path)
    path = os.path.abspath(os.path.normpath(os.path.expanduser(os.path.join(path, 'env.py'))))
    if not os.path.exists(path):
        sys.stderr.write(f"Cannot find env file at {path} - run `flask db init` first\n")
        sys.exit(1)

    with open(path, 'r') as fp:
        for line in fp:
            if MARKER in line:
                return

    with open(os.path.join(os.path.dirname(__file__), 'env.py.template'), 'r') as fp:
        template = fp.read()

    template = template.replace('{{MARKER}}', MARKER)
    template = template.replace('{{MODULE}}', current_app.base_plugin_module)

    with open(path, 'w') as fp:
        fp.write(template)

    print(f"Wrote new configuration to {path}")