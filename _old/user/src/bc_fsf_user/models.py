"""Models for users"""

from typing import Optional, Iterable, Tuple, Dict, Any

import hmac
from random import SystemRandom

from flask import current_app, url_for
import sqlalchemy_utils as sau
import arrow
import pyotp
import qrcode

from bc_fsf_base import event
from bc_fsf_database import db
from bc_fsf_database.mixins import TimestampMixin
from .mixins import CompareProperty
from .hashes import Password


class User(TimestampMixin, db.Model):
    """Represents a user account"""

    __tablename__ = 'user'
    __table_args__ = (
        db.UniqueConstraint('username', name='uq_user_username'),
        db.UniqueConstraint('email', name='uq_user_email'),
        db.Index('ix_user_ecc', 'email_confirmation_code'),
        db.Index('ix_user_prc', 'password_reset_code'),
    )
    id = db.Column(db.BigInteger().with_variant(db.Integer, "sqlite"), nullable=False, primary_key=True, autoincrement=True)
    username = db.Column(db.Unicode(512), nullable=False)
    email = db.Column(db.Unicode(512), nullable=False)
    hashed_password = db.Column(db.Text(), nullable=False)
    name = db.Column(db.UnicodeText())
    is_approved = db.Column(db.Boolean(), nullable=False, default=False, server_default='0')
    is_disabled = db.Column(db.UnicodeText())
    new_email = db.Column(db.Unicode(512))
    email_confirmation_code = db.Column(db.String(36))
    email_confirmation_expiration = db.Column(sau.ArrowType())
    password_reset_code = db.Column(db.String(36))
    password_reset_expiration = db.Column(sau.ArrowType())
    new_totp_secret = db.Column(db.String(64))
    new_totp_backup_codes = db.Column(sau.JSONType())
    totp_secret = db.Column(db.String(64))
    totp_backup_codes = db.Column(sau.JSONType())
    bio = db.Column(db.UnicodeText())
    roles = db.Column(sau.JSONType(), nullable=False, default=list, server_default='[]')
    permissions = db.Column(sau.JSONType(), nullable=False, default=list, server_default='[]')
    timezone = db.Column(db.String(64), nullable=False, default='UTC', server_default='UTC')

    @property
    def rolegroup(self):
        from .permissions import RoleGroup
        if not hasattr(self, '_rolegroup'):
            self._rolegroup = RoleGroup.for_user(self)
        return self._rolegroup

    @property
    def password(self):
        return Password.parse(self.hashed_password)

    @password.setter
    def password(self, new_password: str):
        """\
        Set the user's password to the given password.
        """

        new_password = new_password.encode('utf-8')
        hasher = current_app.plugins['user'].hash_driver
        self.hashed_password = hasher.hash_password(new_password)

    def can(self, *permissions, obj=None):
        """\
        Check if the user has at least one of the given permissions against the
        given object
        """
        return event.publish('user.can', False, *permissions, user=self, obj=obj)

    @property
    def is_logged_in(self):
        current_user = event.publish('user.current')
        return current_user and current_user.id == self.id
