"""Email functionality"""

from typing import Optional, Iterable

import click
from flask import current_app, render_template
from flask.cli import AppGroup
from jinja2.exceptions import TemplateNotFound
from flask_mail import Mail, Message
from markdown import markdown
import arrow

from . import Plugin


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
        current_app.email \
            .create(subject=subject, to=[email]) \
            .render(template, subject=subject, to=[email], body=body) \
            .send_message()
    else:
        current_app.email \
        .create(subject=subject, text_body=body, to=[email]) \
        .send_message()


class EmailMessage(Message):
    """\
    Represents an email message to be sent.
    """

    def __init__(self, plugin, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin = plugin

    @staticmethod
    def _render_candidate(candidates, *args, **kwargs):
        for tpl in candidates:
            try:
                return render_template(tpl, *args, **kwargs)
            except TemplateNotFound:
                pass

    def render(self, template_name: str, *args, text_args: Optional[dict]=None, html_args: Optional[dict]=None, **kwargs):
        """\
        Search for templates based on the given name, and render them as text or
        html content and apply to the message.

        Templates are searched for in "email/<template_name>", and if no HTML
        templates are found, the text content (which is expected to be markdown)
        is then rendered to HTML.

        Text: email/<template>/markdown.j2, email/<template>.md.j2
        HTML: email/<template>/html.j2, email/<template>.html.j2
        """

        text_candidates = [
            f'email/{template_name}/markdown.j2',
            f'email/{template_name}.md.j2',
        ]
        html_candidates = [
            f'email/{template_name}/html.j2',
            f'email/{template_name}.html.j2',
        ]
        text = self._render_candidate(text_candidates, *args, **(text_args or {}), **kwargs)
        html = self._render_candidate(html_candidates, *args, **(html_args or {}), **kwargs)
        if text and not html:
            html = markdown(text)
        if not (text or html):
            raise RuntimeError("No template candidates were found")
        self.body = text
        self.html = html
        return self

    def send_message(self):
        """\
        Send the message to its recipients
        """

        if not (self.body or self.html):
            raise ValueError("A body is required")

        if not (self.recipients or self.cc or self.bcc):
            raise ValueError("Recipients are required")

        return self.plugin.send_email(self)


class EmailPlugin(Plugin):
    """\
    Provides email sending functionality
    """

    def get_config(self):
        return {
            'MAIL_SERVER': {
                'required': True,
                'description': "Server to use to send email",
            },
            'MAIL_PORT': {
                'parser': int,
                'default': 25,
                'description': "Port on which to send email (usually 25(default) for plaintext, 587 for TLS/SSL",
            },
            'MAIL_USE_TLS': {
                'parser': bool,
                'default': False,
                'description': "Use TLS for the connection to the mail server",
            },
            'MAIL_USE_SSL': {
                'parser': bool,
                'default': False,
                'description': "Use SSL for the connection to the mail server",
            },
            'MAIL_USERNAME': {
                'description': "Username for mail server, if authentication is required",
            },
            'MAIL_PASSWORD': {
                'description': "Password for mail server, if authentication is required",
            },
            'MAIL_DEFAULT_SENDER': {
                'required': True,
                'description': "Default sender address for mail",
            },
        }

    def get_flask_plugins(self):
        self.mail = Mail()
        return [self.mail]

    def get_commands(self):
        return [cli_email]

    def create(self, subject: str, text_body: Optional[str]=None, html_body: Optional[str]=None, sender: Optional[str]=None, to: Optional[Iterable[str]]=None, reply_to: Optional[str]=None, cc: Optional[Iterable[str]]=None, bcc: Optional[Iterable[str]]=None) -> EmailMessage:
        """\
        Create a new EmailMessage with the given properties
        """

        return EmailMessage(
            self,
            subject=subject,
            recipients=to,
            body=text_body,
            html=html_body,
            sender=sender,
            cc=cc,
            bcc=bcc,
            reply_to=reply_to,
        )

    def send_email(self, message: Message):
        """\
        Send an email message
        """

        return self.mail.send(message)

