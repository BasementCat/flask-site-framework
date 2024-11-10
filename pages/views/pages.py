"""Views for pages"""

from flask import Blueprint, render_template, abort, g, current_app
from jinja2.exceptions import TemplateNotFound


bp = Blueprint('pages', __name__)


@bp.get('/')
@bp.get('/<page>')
def view(page='index'):
    try:
        g.pages_current_slug = page
        meta = (current_app.plugins['pages'].list_pages(slug=g.pages_current_slug) or [{}])[0]
        res = render_template(f'pages/{page}.html.j2', meta=meta)
        return res
    except TemplateNotFound:
        abort(404)
