"""Jinja helper functions and base globals/filters"""

from typing import Optional, Any

from flask import Flask, request, current_app
import arrow

from . import event

jinja_data = {
    'filters': {},
    'globals': {},
}
"""All registered Jinja filters and globals"""


class PerPlugin:
    """\
    Mixin class allowing Jinja filters and globals to be defined on a per-plugin
    basis - this allows these items to be available only when the plugin is
    installed to the app.  This class is used by the base plugin class, so these
    methods are available on all plugins.
    """

    @classmethod
    def _set_jinja_data(cls, v):
        """\
        Set up Jinja data on the class and append the given item to it
        """

        if not hasattr(cls, '_jinja_data'):
            cls._jinja_data = []
        cls._jinja_data.append(v)

    @classmethod
    def jinja_filter(cls, name: Optional[str]=None):
        """\
        Decorator to define a plugin-level Jinja filter.  If no name is given,
        the callback name is used.
        """

        def jinja_filter_impl(callback):
            cls._set_jinja_data([jinja_filter, name, callback])
            return callback
        return jinja_filter_impl


    @classmethod
    def jinja_global(cls, name: Optional[str]=None):
        """\
        Decorator to define a plugin-level Jinja global.  If no name is given,
        the callback name is used.
        """

        def jinja_global_impl(callback):
            cls._set_jinja_data([jinja_global, name, callback])
            return callback
        return jinja_global_impl

    def init_app(self, app: Flask):
        """\
        Apply all of this plugin's filters/globals
        """

        for jf, n, cb in getattr(self.__class__, '_jinja_data', []):
            jf(n)(cb)


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


def apply(app: Flask):
    """\
    Apply Jinja filters and globals to the app's environment
    """

    app.jinja_env.filters.update(jinja_data['filters'])
    app.jinja_env.globals.update(jinja_data['globals'])


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


@jinja_global()
def maybe_call(fn: str, *args, **kwargs) -> Any:
    """\
    Call the given jinja global if it exists, returning the result or an empty
    string if it does not exist
    """

    if fn in current_app.jinja_env.globals:
        return current_app.jinja_env.globals[fn](*args, **kwargs)
    return ''


@jinja_filter()
def maybe_filter(fn: str, *args, **kwargs) -> Any:
    """\
    Call the given jinja filter if it exists, returning the result or an empty
    string if it does not exist
    """

    if fn in current_app.jinja_env.filters:
        return current_app.jinja_env.filters[fn](*args, **kwargs)
    return ''
