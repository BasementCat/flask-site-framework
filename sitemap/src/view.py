"""Views for robots.txt/sitemap files"""

import logging

from flask import Blueprint, current_app, abort


bp_sm = Blueprint('sitemap', __name__)
bp_rt = Blueprint('robots', __name__)
logger = logging.getLogger(__name__)


def _plugin_sm():
    try:
        return current_app.plugins['sitemap']
    except KeyError:
        logger.error("Sitemap plugin not found!")
        abort(404)


def _plugin_rt():
    try:
        return current_app.plugins['robots']
    except KeyError:
        logger.error("Robots plugin not found!")
        abort(404)


@bp_sm.get('/sitemap.xml')
def get_sitemap():
    if current_app.config.get('SITEMAP_INDEX'):
        abort(404)
    res = _plugin_sm().get_sitemap()
    if res is False:
        logger.error("Sitemap index is not configured, single sitemap is not found")
        abort(404)
    return res, 200, {'Content-type': 'application/xml'}


@bp_sm.get('/sitemap_index.xml')
def get_sitemap_index():
    if not current_app.config.get('SITEMAP_INDEX'):
        abort(404)
    res = _plugin_sm().get_sitemap_index()
    if res is False:
        logger.error("Sitemap index is configured, sitemap index is not found")
        abort(404)
    return res, 200, {'Content-type': 'application/xml'}


@bp_sm.get('/sitemap_<int:idx>.xml')
def get_sitemap_n(idx):
    if not current_app.config.get('SITEMAP_INDEX'):
        abort(404)
    res = _plugin_sm().get_sitemap_by_number(idx)
    if res is False:
        logger.error("Sitemap index is configured, sitemap #%d is not found", idx)
        abort(404)
    return res, 200, {'Content-type': 'application/xml'}


@bp_rt.get('/robots.txt')
def get_robots():
    res = _plugin_rt().get_robots()
    if res is False:
        logger.error("Robots.txt is not found")
        abort(404)
    return res, 200, {'Content-type': 'text/plain'}