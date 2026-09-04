# from typing import Iterable, Optional

# from random import SystemRandom
import uuid

from flask import current_app, url_for
import arrow

from bc_fsf_database import db
from ..models import User
from . import exc


def begin_password_reset(user: User):
    """\
    Begin the password reset process for a user.
    """

    user.password_reset_code = str(uuid.uuid4())
    user.password_reset_expiration = arrow.utcnow().shift(seconds=current_app.config['USERS_VERIFY_EXPIRATION'])
    db.session.commit()
    try:
        subject = f"{current_app.config.get('SITE_NAME')} password reset"
        current_app.plugins['email'] \
            .create(
                subject,
                to=[user.email]
            ) \
            .render(
                'user/password_reset',
                subject=subject,
                user=user,
                code=user.password_reset_code,
                expires=user.password_reset_expiration,
                confirm_url=url_for('user.reset_password', code=user.password_reset_code, action='confirm', _external=True),
                deny_url=url_for('user.reset_password', code=user.password_reset_code, action='deny', _external=True),
            ) \
            .send_message()
    except:
        raise exc.FailedToSendEmail("Failed to send password reset email, please try again later")


def check_complete_password_reset(code: str, confirm: bool=True) -> bool:
    """\
    Check whether the password reset process can continue
    """

    user = User.query.filter(User.password_reset_code == code).first()
    if user:
        if not user.password_reset_expiration or user.password_reset_expiration < arrow.utcnow():
            raise exc.InvalidCode("Password reset code has expired")
        if confirm:
            # Password reset may continue
            return user, True
        else:
            # Password reset may not continue
            user.password_reset_code = user.password_reset_expiration = None
            db.session.commit()
            return user, False
    else:
        raise exc.InvalidCode("Password reset code is invalid")


def complete_password_reset(user: User, new_password: str):
    """\
    Complete the password reset process for a user, setting their password to
    the given password.
    """

    user.password_reset_code = user.password_reset_expiration = None
    user.password = new_password
    db.session.commit()
