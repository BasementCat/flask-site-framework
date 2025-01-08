"""Views for users"""

import os
import logging

from flask import Blueprint, abort, flash, url_for, redirect, request, current_app, render_template, session
from sqlalchemy.exc import NoResultFound, MultipleResultsFound

from bc_fsf_base import require, event
from bc_fsf_database import db
from .models import User
from .forms import LoginForm, PasswordResetInitForm, PasswordResetForm, TOTPValidationForm, UserForm
from .process import exc, email, password, totp


bp = Blueprint('user', __name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
logger = logging.getLogger(__name__)


def redir_after_login():
    dest = session.get('url_after_login')
    if dest:
        del session['url_after_login']
    return redirect(dest or '/')


@bp.route('/signup', methods=['GET', 'POST'])
@require('user.can', 'signup')
def signup():
    form = UserForm(None, 'signup')
    if form.validate_on_submit():
        data = {
            'username': form.username.data,
            'email': form.email.data,
            'password': form.update_password.data,
            'timezone': form.timezone.data,
            'name': form.name.data,
            'bio': form.bio.data,
        }
        user, props, warnings, errors, meta = event.publish('user.create', (data, None, None))
        for e in errors:
            flash(e, 'danger')
        for w in warnings:
            flash(w, 'warn')
        if user:
            if current_app.config['USERS_ADMIN_APPROVAL']:
                flash("You will not be able to log in until an administrator approves your account", 'info')

            if meta.get('did_email_confirmation') is True:
                flash("You have been sent an email to confirm your email address - please follow the instructions in the email before you can log in", 'info')
            elif meta.get('did_email_confirmation') is False:
                flash("There was an error sending your confirmation email", 'danger')

            if meta.get('did_email_confirmation') is None and not current_app.config['USERS_ADMIN_APPROVAL']:
                flash("Your account is created and you may now log in", 'success')

            return redirect(url_for('.login'))

    return render_template('user/signup.html.j2', form=form)


@bp.route('/login', methods=['GET', 'POST'])
@require('user.can', 'login', always_abort=True)
def login():
    form = LoginForm()
    user = form.validate_on_submit()
    if user:
        event.publish('user.login', user)
        # TOTP redirection done by user.can - not on this url but next
        return redir_after_login()
    elif user is None:
        flash("Invalid username or password", 'danger')

    return render_template('user/login.html.j2', form=form)


@bp.route('/login/totp', methods=['GET', 'POST'])
@require('user.load', current=True)
@require('user.can', 'login', always_abort=True, obj_key='user', skip_totp_setup=True)
def totp_login(user, *args, **kwargs):
    if not (current_app.config['USERS_ALLOW_TOTP'] and user.totp_secret):
        return redir_after_login()
    form = TOTPValidationForm(user)
    if form.validate_on_submit():
        session['totp_login'] = True
        return redir_after_login()

    return render_template('user/totp_login.html.j2', form=form)


@bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@require('user.load')
@require('user.can', 'edit_user', 'edit_other_user', 'edit_user_admin', 'edit_other_user_admin', obj_key='user')
def edit(user, *args, **kwargs):
    # User form assumes current user has at least edit_user (and user is current), or edit_other_user    
    form = UserForm(user, 'edit')
    if form.validate_on_submit():
        try:
            form.populate_obj(user)
        except (exc.ProcessInProgress, exc.FailedToSendEmail) as e:
            # catch & flash here as we still want to commit
            flash(str(e), 'danger')
        db.session.commit()
        flash("Your changes have been saved", 'success')

    return render_template('user/edit.html.j2', form=form, user=user)


@bp.get('/confirm-email/<any(confirm,deny):action>/<code>')
def confirm_email(action, code):
    try:
        res = email.complete_email_confirmation(code, confirm=(action == 'confirm'))
        if res:
            flash("Your email address is confirmed and you may now log in.", 'success')
        else:
            flash("Your email address change has been cancelled", 'info')
        return redirect(url_for('.login'))
    except (exc.InvalidCode, exc.ProcessInProgress) as e:
        abort(400, str(e))


@bp.route('/reset-password', methods=['GET', 'POST'])
@bp.route('/reset-password/<any(confirm,deny):action>/<code>', methods=['GET', 'POST'])
def reset_password(action=None, code=None):
    if action:
        try:
            user, status = password.check_complete_password_reset(code, confirm=(action == 'confirm'))
            if status:
                form = PasswordResetForm()
                if form.validate_on_submit():
                    password.complete_password_reset(user, form.password.data)
                    flash("Your password has been reset and you may now log in.", 'success')
                    return redirect(url_for('.login'))
            else:
                flash("Your password reset has been cancelled", 'info')
                return redirect(url_for('.login'))
        except exc.InvalidCode as e:
            abort(400, str(e))
    else:
        form = PasswordResetInitForm()
        if form.validate_on_submit():
            user = None
            try:
                user = User.query.filter(User.username.like(form.username_or_email.data) | User.email.like(form.username_or_email.data)).one()
            except NoResultFound:
                pass
            except MultipleResultsFound:
                logger.error("Multiple users found for %s", form.username_or_email.data)

            if user:
                try:
                    password.begin_password_reset(user)
                    return redirect(url_for('.login'))
                except exc.FailedToSendEmail as e:
                    abort(400, str(e))

            flash("No matching user was found", 'danger')

    return render_template('user/reset_password.html.j2', action=action or 'init', form=form)


@bp.route('/edit/<int:user_id>/totp', methods=['GET', 'POST'])
@require('user.load')
@require('user.can', 'edit_user', 'edit_other_user', 'edit_user_admin', 'edit_other_user_admin', obj_key='user', skip_totp_setup=True)
def totp_setup(user, *args, **kwargs):
    if not current_app.config['USERS_ALLOW_TOTP']:
        abort(404)

    form = TOTPValidationForm(user, setup=True)
    if form.validate_on_submit():
        # form performs TOTP validation
        if user.is_logged_in:
            session['totp_login'] = True
        flash("TOTP setup is complete", 'success')
        return redir_after_login()

    try:
        totp.begin_totp_setup(user)
    except exc.ProcessComplete:
        # setup is done
        return redir_after_login()
    except exc.ProcessInProgress:
        # setup already in progress; use the existing data
        pass

    return render_template('user/totp_setup.html.j2', form=form, user=user)
