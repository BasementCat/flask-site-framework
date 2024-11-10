"""Database mixins"""

from sqlalchemy.orm import declared_attr
from sqlalchemy_utils import ArrowType
import arrow

from . import db


class TimestampMixin:
    """\
    Add created_at/updated_at fields to the model, automatically setting them to
    appropriate UTC timestamps
    """

    @declared_attr
    def created_at(self):
        return db.Column(ArrowType(), nullable=False, index=True, default=arrow.utcnow)

    @declared_attr
    def updated_at(self):
        return db.Column(ArrowType(), nullable=False, index=True, default=arrow.utcnow, onupdate=arrow.utcnow)
