"""Bootstrap plugin"""

from typing import Literal, Union


from flask import Blueprint, current_app, url_for
from markupsafe import Markup
from flask_bootstrap import Bootstrap4, Bootstrap5

from . import Plugin
from .event import subscribe
from .jinja import jinja_global


class BootstrapPlugin(Plugin):
    """\
    Install the Bootstrap-Flask plugin, and optionally include the FontAwesome
    stylesheet.

    See https://bootstrap-flask.readthedocs.io/en/stable/migrate/ for docs on
    migration from flask-bootstrap
    """

    fontawesome_versions = {
        '7.3.1': '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/7.3.1/css/all.min.css" integrity="sha512-QeR2VH+lsBE5LSAe1Q5EnTBbe7XTBubt8dG93Y7gidSgdMCr8nVqKcfKAMyN96SV8KDbZVTDXChatu5G2KQGzg==" crossorigin="anonymous" referrerpolicy="no-referrer">',
    }
    default_fontawesome_version = '7.3.1'

    def __init__(self, *args, with_fontawesome: Union[bool, str]=False, bootstrap_version: Literal[4, 5]=5, **kwargs):
        """\
        Initialize the plugin, if with_fontawesome is True, add the fontawesome
        stylesheet to the page (can optionally specify a fontawesome version)
        """

        super().__init__(*args, **kwargs)
        self.with_fontawesome = with_fontawesome
        self.bootstrap_plugin = {4: Bootstrap4, 5: Bootstrap5}[bootstrap_version]

    def get_flask_plugins(self):
        return [self.bootstrap_plugin()]

    def get_blueprints(self):
        return [(None, Blueprint('_base_bs', __name__, url_prefix='/fsf/bs', static_folder='static', template_folder='templates'))]

    def get_fontawesome_stylesheet(self, event, value, *args, **kwargs):
        ver = self.with_fontawesome
        if ver is True:
            ver = self.default_fontawesome_version
        if ver:
            if current_app.config.get('BOOTSTRAP_SERVE_LOCAL'):
                url = url_for('_base_bs.static', filename=f'css/fontawesome/v{ver}-all.min.css')
                link = f'<link rel="stylesheet" href="{url}">'
                value.append(link)
            else:
                value.append(self.fontawesome_versions[ver])
        return value

    def init_app(self, app):
        super().init_app(app)
        if self.with_fontawesome:
            subscribe('base.template.stylesheets', self.get_fontawesome_stylesheet)


@jinja_global()
def fa(icon, collection='fa', cls=''):
    """\
    Generate markup for a FontAwesome icon
    """

    return Markup(f'<span class="{collection} fa-{icon} {cls}"></span>')


@jinja_global()
def fas(icon, collection='fas', cls=''):
    """\
    Generate markup for a FontAwesome icon, defaulting to the solid collection
    """

    return fa(icon, collection=collection, cls=cls)


@jinja_global()
def fab(icon, collection='fab', cls=''):
    """\
    Generate markup for a FontAwesome icon, defaulting to the brands collection
    """

    return fa(icon, collection=collection, cls=cls)