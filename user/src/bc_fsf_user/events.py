"""\
Events to interact with users

Do not import at the module level, as this subscribes to events outside of the
user plugin!
"""

from typing import Iterable

from random import SystemRandom
import uuid
import logging

from flask import current_app, redirect, url_for, flash, session, g, request
import pyotp
import arrow
from sqlalchemy.exc import IntegrityError

from bc_fsf_base import event
from bc_fsf_database import db
from .models import User
from .permissions import Permission, Role, RoleGroup, load as load_perms_roles
from .process import totp, email, exc


logger = logging.getLogger(__name__)


@event.subscribes_to('app.loaded')
def init_perms_roles(event_name, app, *args, **kwargs):
    load_perms_roles(app)
    return app


@event.subscribes_to('user.login')
def login_user(event_name, user: User, *args, **kwargs):
    if user:
        session['current_user'] = user.id
        session.permanent = True
        g.current_user = user
    return user


@event.subscribes_to('user.logout')
def logout_user(event_name, user=None, *args, **kwargs):
    if 'current_user' in session:
        del session['current_user']
    if 'totp_login' in session:
        del session['totp_login']
    session.permanent = False
    g.current_user = None

    return user


@event.subscribes_to('user.current')
def get_current_user(event_name='user.current', user=None, *args, **kwargs):
    if 'current_user' not in g:
        g.current_user = None
        current_user_id = session.get('current_user')
        if current_user_id:
            user = User.query.get(current_user_id)
            if user:
                g.current_user = user

    return g.current_user

@event.subscribes_to('jinja.dt.timezone')
def get_current_user_timezone(event_name, timezone, *args, **kwargs):
    user = get_current_user()
    if user and user.timezone:
        return user.timezone
    return timezone


@event.subscribes_to('user.can')
def check_user_permission(event_name, has_permission, *permissions, obj=None, user=None, **kwargs):
    user = user or get_current_user()
    return RoleGroup.for_user(user).check_permissions(*permissions, obj=obj)


@event.subscribes_to('user.after_permission_check')
def check_email_conf_required(event_name, dest, user, *args, skip_totp_setup=False, **kwargs):
    if not dest:
        if user and current_app.config['USERS_VERIFY_EMAIL']:
            if user.email_confirmation_code:
                # Indicates email verification is in progress
                if not user.new_email:
                    # If confirmation is for new email that's fine; only original email matters here
                    flash("You must confirm your email before you can log in", 'danger')
                    event.publish('user.logout')
                    # TODO: way to send confirmation email
                    return redirect(url_for('user.login'))
    return dest


@event.subscribes_to('user.after_permission_check')
def check_admin_approve_required(event_name, dest, user, *args, skip_totp_setup=False, **kwargs):
    if not dest:
        if user:
            if user.is_disabled:
                # if a logged-in user is disabled, log them out and bail
                flash("Your account is disabled", 'danger')
                event.publish('user.logout')
                return redirect('/')
            if current_app.config['USERS_ADMIN_APPROVAL'] and not user.is_approved:
                flash("Your account must be approved before you can log in", 'danger')
                event.publish('user.logout')
                return redirect(url_for('user.login'))
    return dest


def is_totp_required_for(user: User) -> bool:
    level = current_app.config.get('USERS_REQUIRE_TOTP')
    if level is not None:
        try:
            level = int(level)
            if user.rolegroup.maxlevel >= level:
                return True
        except:
            return user.rolegroup.contains_role(level)
    return False


@event.subscribes_to('user.after_permission_check')
def check_totp_setup_required(event_name, dest, user, *args, skip_totp_setup=False, **kwargs):
    if not dest:
        if not skip_totp_setup and user and current_app.config['USERS_ALLOW_TOTP']:
            need_totp = False
            if user.new_totp_secret:
                need_totp = True
                msg = "You must complete or cancel TOTP setup before continuing"
            else:
                need_totp = is_totp_required_for(user)
                msg = "You are required to set up two factor auth for your account"

            if need_totp:
                session['url_after_login'] = session.get('url_after_login') or request.url
                flash(msg, 'warning')
                return redirect(url_for('user.totp_setup', user_id=user.id))
    return dest


@event.subscribes_to('user.after_permission_check')
def check_totp_login_required(event_name, dest, user, *args, skip_totp_setup=False, **kwargs):
    if not dest:
        if user and current_app.config['USERS_ALLOW_TOTP']:
            if user.totp_secret and not session.get('totp_login'):
                session['url_after_login'] = session.get('url_after_login') or request.url
                return redirect(url_for('user.totp_login'))
    return dest


@event.subscribes_to('user.create', priority=50)
def create_user_data__defaults(event_name, data, *args, **kwargs):
    user, properties, warnings, errors, meta = data
    warnings = warnings or []
    errors = errors or []
    meta = meta or {}

    properties.update({
        'roles': list(properties.get('roles') or [r.key for r in Role.default_roles]),
        'permissions': list(properties.get('permissions') or [p.key for p in Permission.default_permissions]),
        'timezone': properties.get('timezone') or current_app.config['SITE_TIMEZONE'],
        'name': properties.get('name') or None,
        'is_disabled': properties.get('is_disabled') or None,
        'bio': properties.get('bio') or None,
    })
    if 'is_approved' in properties:
        properties['is_approved'] = bool(properties['is_approved'])
    else:
        properties['is_approved'] = not current_app.config['USERS_ADMIN_APPROVAL']

    return user, properties, warnings, errors, meta


@event.subscribes_to('user.create', priority=75)
def create_user(event_name, data, *args, **kwargs):
    user, properties, warnings, errors, meta = data
    warnings = warnings or []
    errors = errors or []
    meta = meta or {}

    required_props = ('username', 'email', 'password', 'timezone')
    for k in required_props:
        if not properties.get(k):
            errors.append(f"Field {k} is required to create a user")

    if not errors:
        user = User(**properties)
        user.password = properties['password']
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError as e:
            errors.append("Username or email is already in use")
            user = None

    return user, properties, warnings, errors, meta


@event.subscribes_to('user.create', priority=125)
def create_user__setup(event_name, data, *args, do_totp_setup=None, skip_email_confirmation=False, **kwargs):
    user, properties, warnings, errors, meta = data
    warnings = warnings or []
    errors = errors or []
    meta = meta or {}
    meta.update({
        'did_totp_setup': None,
        'did_email_confirmation': None,
    })

    if user:
        if do_totp_setup is None:
            do_totp_setup = is_totp_required_for(user)

        if do_totp_setup:
            try:
                totp.begin_totp_setup(user, skip_confirm=kwargs.get('skip_totp_confirm'))
                meta['did_totp_setup'] = True
            except exc.ProcessComplete as e:
                warnings.append(str(e))
                meta['did_totp_setup'] = True
            except exc.ProcessInProgress as e:
                errors.append(str(e))
                # already started totp setup but not completed, user will be redirected later
                meta['did_totp_setup'] = True

        if not skip_email_confirmation:
            try:
                email.begin_email_confirmation(user)
                meta['did_email_confirmation'] = True
            except exc.ProcessDisabled as e:
                pass
            except exc.ProcessInProgress as e:
                warnings.append(str(e))
                meta['did_email_confirmation'] = True
            except exc.FailedToSendEmail as e:
                errors.append(str(e))
                meta['did_email_confirmation'] = False

    return user, properties, warnings, errors, meta
