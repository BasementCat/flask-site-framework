"""Users functionality"""

from typing import Optional

import logging

from flask import Flask, g, session, request, url_for, redirect, current_app, abort, flash
from markupsafe import Markup
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from bc_fsf_base import Plugin, event

from .hashes import PasswordHashDriver, SCryptHashDriver
from .models import User
# from .permissions import RoleGroup, load as load_perms_roles


logger = logging.getLogger(__name__)


class UserPlugin(Plugin):
    """\
    Implements users and login
    """

    def __init__(self, app: Optional[Flask]=None, hash_driver: Optional[PasswordHashDriver]=None):
        """\
        Initialize the users plugin with an optional flask app.
        If no hash driver is provided, the scrypt driver with default args is used.
        """

        self.hash_driver = hash_driver or SCryptHashDriver()
        super().__init__(app=app)

    def get_config(self):
        return {
            'USERS_USE_CAPTCHA': {
                'parser': bool,
                'default': True,
                'description': "Use a captcha on the signup & login forms, if available",
            },
            'USERS_ALLOW_SIGNUP': {
                'parser': bool,
                'default': True,
                'description': "Allow users to sign up for the site",
            },
            'USERS_VERIFY_EMAIL': {
                'parser': bool,
                'default': True,
                'description': "Require email verification for new signups",
            },
            'USERS_ADMIN_APPROVAL': {
                'parser': bool,
                'default': True,
                'description': "Require admin approval for new signups",
            },
            'USERS_ALLOW_TOTP': {
                'parser': bool,
                'default': True,
                'description': "Allow TOTP for users",
            },
            'USERS_REQUIRE_TOTP': {
                'parser': str,
                'description': "Require TOTP for roles >= this role, or having a level >= this level",
            },
            'USERS_VERIFY_EXPIRATION': {
                'parser': int,
                'default': 86400 * 3,
                'description': "Email verification and password reset codes expire after this many seconds",
            },
        }

    def get_blueprints(self):
        from . import view
        return [('/user', view.bp)]

    def get_commands(self):
        from . import commands
        return [commands.cli]

    def get_decorators(self):
        return {
            'load': self.dec_user_load,
            'can': self.dec_user_can,
        }

    def init_app(self, app):
        super().init_app(app)
        from . import events

    def dec_user_load(self, callback, dec_args, dec_kwargs, call_args, call_kwargs):
        user = None
        if dec_kwargs.get('current'):
            user = event.publish('user.current')
        else:
            user_id = call_kwargs.get(dec_kwargs.get('user_id_key', 'user_id'))
            username = call_kwargs.get(dec_kwargs.get('user_name_key', 'username'))
            if user_id:
                user = User.query.get(user_id)
            elif username:
                try:
                    user = User.query.filter(User.username.like(username) | User.email.like(username)).one()
                except NoResultFound:
                    pass
                except MultipleResultsFound:
                    logger.error("Multiple users matching %s", username)

        if not user and dec_kwargs.get('abort_on_missing', True):
            abort(404, "No matching user was found")

        call_kwargs = dict(call_kwargs, **{dec_kwargs.get('user_key', 'user'): user})
        return callback(*call_args, **call_kwargs)

    def dec_user_can(self, callback, dec_args, dec_kwargs, call_args, call_kwargs):
        # dec args - permissions to check
        # dec kwargs - obj_key=key of object in call_kwargs

        check_permissions = dec_args
        obj_key = dec_kwargs.get('obj_key', 'obj')
        obj = call_kwargs.get(obj_key)

        user = event.publish('user.current')

        if (not dec_kwargs.get('require_user') or user) and event.publish('user.can', False, *check_permissions, obj=obj):
            res = event.publish('user.after_permission_check', None, user, skip_totp_setup=dec_kwargs.get('skip_totp_setup'))
            if res:
                return res
            return callback(*call_args, **call_kwargs)
        else:
            if user:
                # user is logged in - logging in again (probably) won't help, so just abort
                abort(401, "You do not have permission to view this page")
            else:
                if dec_kwargs.get('always_abort'):
                    # Mostly for login - do not redirect to login page if you can't view the login page...
                    abort(403, "You do not have permission to view this page")
                session['url_after_login'] = request.url
                flash("You do not have permission; please log in first", 'danger')
                return redirect(url_for('user.login'))
