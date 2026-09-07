"""Jinja helper functions and base globals/filters"""

from typing import Optional, Any

import math

from flask import Flask, request, current_app
import arrow

from . import event
from . import Plugin


jinja_data = {
    'filters': {},
    'globals': {},
}
"""All registered Jinja filters and globals"""


class JinjaPlugin(Plugin):
    def init_app(self, app: Flask):
        super().init_app(app)
        app.jinja_env.filters.update(jinja_data['filters'])
        app.jinja_env.globals.update(jinja_data['globals'])
        # hax
        app.jinja_env.auto_reload = bool(app.config.get('TEMPLATES_AUTO_RELOAD'))


def jinja_filter(name: Optional[str]=None):
    """\
    Decorator to define a Jinja filter.  If no name is given,
    the callback name is used.
    """

    def jinja_filter_impl(callback):
        jinja_data['filters'][name or callback.__name__] = callback
        return callback
    return jinja_filter_impl


def jinja_global(name: Optional[str]=None):
    """\
    Decorator to define a Jinja global.  If no name is given,
    the callback name is used.
    """

    def jinja_global_impl(callback):
        jinja_data['globals'][name or callback.__name__] = callback
        return callback
    return jinja_global_impl


jinja_global('publish_event')(event.publish)

@jinja_global()
def route_matches(endpoint: str, **params) -> bool:
    """\
    Determine if the current request's route matches the given endpoint and
    parameters.
    """

    if request.endpoint == endpoint:
        for k, v in params.items():
            if request.view_args.get(k) != v:
                return False
        return True
    return False


@jinja_global()
def now() -> arrow.arrow.Arrow:
    """\
    Return the current UTC timestamp as an Arrow object
    """

    return arrow.utcnow()


@jinja_filter()
def dt(dt: arrow.arrow.Arrow, part: str='all', fmt='full') -> str:
    """\
    Format an Arrow datetime using either the site timezone or one defined by
    an event
    """
    formats = {
        'full': ('MMMM Do, YYYY', 'h:mm A'),
    }
    tz = event.publish('jinja.dt.timezone', current_app.config['SITE_TIMEZONE'])
    if fmt in formats:
        df, tf = formats[fmt]
        if part == 'date':
            fmt = df
        elif part == 'time':
            fmt = tf
        else:
            fmt = f'{df} {tf}'
    return dt.to(tz).format(fmt)


jinja_filter('ceil')(math.ceil)
jinja_filter('floor')(math.floor)