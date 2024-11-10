"""Mailing list functionality"""

from typing import Optional

from flask import url_for, request, current_app
from markupsafe import Markup

from app.plugins.base import Plugin

from .models import Email


class MailingListPlugin(Plugin):
    """\
    Implements a mailing list for the application
    """

    def get_config(self):
        return {
            'MAILING_LIST_USE_CAPTCHA': {
                'parser': bool,
                'default': True,
                'description': "Use a captcha on the form, if available",
            },
        }

    def get_blueprints(self):
        from . import view
        return [('/mailing-list', view.bp)]

    def get_commands(self):
        from . import commands
        return [commands.cli]


@MailingListPlugin.jinja_global()
def mailing_list_subscribe(
    title: Optional[str]=None,
    text: Optional[str]=None,
    title_tag: str='h2',
    subscribe_text: str='Subscribe',
    next_url: Optional[str]=None,
    allow_skip: bool=False,
    skip_text: str='Skip',
    use_captcha: Optional[bool]=None,
    source: str='widget',
) -> Markup:
    """\
    Generate markup for subscribing to the mailing list.

    * title: Optional title to be displayed at the top of the widget
    * text: Optional text to be displayed below the title/above the form
    * title_tag: Tag to use for the title
    * subscribe_text: Text for the "subscribe" button
    * next_url: After subscribing the user is sent to this URL, or to the referrer
    * allow_skip: If true, add a button allowing the user to go directly to next_url if set
    * skip_text: Text for the "skip" button
    * use_captcha: If true, attempt to add a captcha to the form, if None use the config to determine if a captcha should be used (if false, do not use a captcha)
    * source: Attribute the mailing list signup to this arbitrary source
    """

    title_str = ''
    if title:
        title_str = f'<{title_tag}>{title}</{title_tag}>'

    form_action = url_for('mailing_list.subscribe')
    captcha = ''
    if use_captcha is True or (use_captcha is None and current_app.config.get('MAILING_LIST_USE_CAPTCHA')):
        cplugin = current_app.plugins.get('captcha')
        if cplugin:
            captcha = cplugin.get_captcha()

    text_str = ''
    if text:
        text_str = f'<p>{text}</p>'

    skip_str = ''
    if next_url and allow_skip:
        skip_str = f'<a href="{next_url}" class="btn btn-default">{skip_text}</a>'

    return Markup(f"""\
        <div class="well">
            {title_str}
            <form method="POST" action="{form_action}">
                <input type="hidden" name="source" value="{source}" />
                <input type="hidden" name="next_url" value="{next_url or request.url}" />
                {text_str}
                <div class="form-group">
                    <label for="name">Name</label>
                    <input type="text" class="form-control" id="name" name="name">
                </div>
                <div class="form-group">
                    <label for="email">Email</label>
                    <input type="email" class="form-control" id="email" name="email" required>
                </div>
                {captcha}
                <p>You will be sent an email to confirm your subscription.</p>
                <button type="submit" class="btn btn-primary">{subscribe_text}</button>
                {skip_str}
            </form>
        </div>
    """)
