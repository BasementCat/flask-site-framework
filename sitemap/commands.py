"""Commands to generate/clear the sitemap/robots.txt"""

from flask import current_app
from flask.cli import AppGroup


cli_sm = AppGroup('sitemap')
cli_rt = AppGroup('robots')


@cli_sm.command('generate')
def generate_sitemap():
    """\
    Generate the sitemap
    """
    current_app.plugins['sitemap'].generate_sitemap()


@cli_sm.command('clear')
def clear_sitemap():
    """\
    Remove cached sitemap files
    """
    current_app.plugins['sitemap'].clear_sitemap()


@cli_rt.command('generate')
def generate_robots():
    """\
    Generate the robots.txt file
    """
    current_app.plugins['robots'].generate_robots()


@cli_rt.command('clear')
def clear_robots():
    """\
    Remove cached robots.txt file
    """
    current_app.plugins['robots'].clear_robots()