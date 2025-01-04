from typing import Optional

import uuid

from flask import current_app, url_for
import arrow

from bc_fsf_database import db
from ..models import User
from . import exc


def begin_email_confirmation(user: User, new_email: Optional[str]=None):
    """\
    Begin the email confirmation process, optionally with a new email address.

    If a new email is provided, and email confirmation is in progress for a different
    email, an exception is raised.

    Otherwise, the new email is set as appropriate, and a confirmation email is
    sent to the user.  If the site is not configured for email verification, no
    changes are made.
    """

    if not (new_email or current_app.config['USERS_VERIFY_EMAIL']):
        user.new_email = user.email_confirmation_code = user.email_confirmation_expiration = None
        db.session.commit()
        raise exc.ProcessDisabled("No new email was given, and base email verification is disabled")
    else:
        if new_email:
            if user.email_confirmation_code:
                if user.new_email:
                    if user.new_email != new_email:
                        raise exc.ProcessInProgress("An email change is already in progress")
                else:
                    raise exc.ProcessInProgress("The original email address is not confirmed")
            user.new_email = new_email
        user.email_confirmation_code = str(uuid.uuid4())
        user.email_confirmation_expiration = arrow.utcnow().shift(seconds=current_app.config['USERS_VERIFY_EXPIRATION'])
        db.session.commit()
        try:
            subject = f"{current_app.config.get('SITE_NAME')} email address confirmation"
            current_app.plugins['email'] \
                .create(
                    subject,
                    to=[user.email]
                ) \
                .render(
                    'user/email_confirmation',
                    subject=subject,
                    user=user,
                    old_email=user.email,
                    new_email=user.new_email,
                    code=user.email_confirmation_code,
                    expires=user.email_confirmation_expiration,
                    confirm_url=url_for('user.confirm_email', code=user.email_confirmation_code, action='confirm'),
                    deny_url=url_for('user.confirm_email', code=user.email_confirmation_code, action='deny'),
                ) \
                .send_message()
        except:
            raise exc.FailedToSendEmail("Failed to send the confirmation email")


def complete_email_confirmation(code: str, confirm: bool=True) -> bool:
    """\
    Complete the email verification process, checking the given code against
    the stored one, raising an exception if the process cannot be completed.
    """

    user = User.query.filter(User.email_confirmation_code == code).first()
    if user:
        if not user.email_confirmation_expiration or user.email_confirmation_expiration < arrow.utcnow():
            raise exc.InvalidCode("Email confirmation code has expired")
        if user.new_email:
            if confirm:
                user.email = user.new_email
        elif not confirm:
            raise exc.ProcessInProgress("Email confirmation for original email cannot be denied")
        user.new_email = user.email_confirmation_code = user.email_confirmation_expiration = None
        db.session.commit()

        return confirm
    else:
        raise exc.InvalidCode("Email confirmation code is invalid")