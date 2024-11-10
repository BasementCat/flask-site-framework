"""Models for the mailing list"""

import uuid

from bc_fsf_database import db
from bc_fsf_database.mixins import TimestampMixin


class Email(TimestampMixin, db.Model):
    """Represents a subscribed email"""

    __tablename__ = 'mailing_list_email'
    __table_args__ = (
        db.UniqueConstraint('email', name='uq_ml_email_email'),
        db.Index('ix_ml_email_source', 'source'),
        db.Index('ix_ml_email_flags', 'subscribed', 'confirmed', 'bounced'),
    )
    # mixin - created/updated at
    id = db.Column(db.String(36), nullable=False, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.Unicode(512), nullable=False)
    name = db.Column(db.UnicodeText())
    source = db.Column(db.Unicode(64))
    subscribed = db.Column(db.Boolean(), nullable=False, default=True)
    confirmed = db.Column(db.Boolean(), nullable=False, default=False)
    bounced = db.Column(db.Boolean(), nullable=False, default=False)
