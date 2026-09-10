"""Commands for base plugins"""

from typing import Optional

import click
from flask import current_app
from flask.cli import AppGroup
import arrow
from tabulate import tabulate


cli_email = AppGroup('mail')


@cli_email.command('test')
@click.argument('email')
@click.option('-t', '--template', help="Render using this template")
def test_email(email: str, template: Optional[str]):
    """\
    Send a test email
    """
    now = arrow.utcnow()
    subject = f"Test email from {current_app.config.get('SITE_NAME')} - {now.format('YYYY-MM-DD')}"
    body = (
        f"This is a test email sent from {current_app.config.get('SITE_NAME')}.\n"
        f"It was sent at {now} to {email}\n"
    )
    if template:
        current_app.plugins['email'] \
            .create(subject=subject, to=[email]) \
            .render(template, subject=subject, to=[email], body=body) \
            .send_message()
    else:
        current_app.plugins['email'] \
        .create(subject=subject, text_body=body, to=[email]) \
        .send_message()
