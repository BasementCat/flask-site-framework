"""Views for the mailing list"""

import os
import logging

from flask import Blueprint, request, current_app, abort, flash, redirect, url_for, render_template
from sqlalchemy.exc import IntegrityError
import purl

from app.plugins.base import decorator
from app.plugins.database import db
from .models import Email


bp = Blueprint('mailing_list', __name__, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))
logger = logging.getLogger(__name__)


@bp.post('/subscribe')
@decorator('captcha.validate')
def subscribe(*args, **kwargs):
    try:
        db.session.add(Email(
            email=(request.form.get('email') or '').strip() or None,
            name=(request.form.get('name') or '').strip() or None,
            source=(request.form.get('source') or '').strip() or None,
            subscribed=True,
            confirmed=False
        ))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

    e = Email.query.filter(Email.email.like(request.form.get('email'))).first()
    if e and not e.confirmed:
        try:
            subject = f"{current_app.config.get('SITE_NAME')} mailing list subscription confirmation"
            current_app.plugins['email'] \
                .create(
                    subject,
                    to=[e.email]
                ) \
                .render(
                    'mailing_list/confirmation',
                    subject=subject,
                    sub_url=url_for('mailing_list.update', id=e.id, default_action='subscribe', _external=True),
                    unsub_url=url_for('mailing_list.update', id=e.id, default_action='unsubscribe', _external=True),
                    edit_url=url_for('mailing_list.update', id=e.id, _external=True),
                ) \
                .send_message()
        except:
            logger.error("Failed to send email", exc_info=True)
            pass

        # Always show the message even if the email wasn't sent
        # TODO: cron or something to find emails where confirmed=false & resend emails
        flash("Thank you for subscribing!  You will get an email shortly to confirm your address and subscription.", 'info')

    next_url = purl.URL(request.form.get('next_url') or request.referrer or '/').path()
    return redirect(next_url)


@bp.route('/update/<id>', methods=['GET', 'POST'])
def update(id):
    e = Email.query.get(id)
    if not e:
        abort(404)

    if request.method == 'POST':
        if request.form.get('action') == 'subscribe':
            e.subscribed = True
            flash("Thank you for subscribing!", 'success')
        else:
            e.subscribed = False
            flash("You are now unsubscribed.", 'info')
        db.session.commit()

    if not e.confirmed:
        e.confirmed = True
        db.session.commit()

    return render_template('mailing_list/update.html.j2', email=e, default_action=request.args.get('default_action'))
