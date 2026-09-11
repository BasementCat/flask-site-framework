"""Core plugins"""

from typing import Optional, Iterable

import logging

from flask import Flask, Blueprint, current_app, request, render_template, g, abort, flash, redirect
from markupsafe import Markup
from jinja2.exceptions import TemplateNotFound
from flask_bootstrap import Bootstrap
from flask_mail import Mail, Message
from markdown import markdown

from . import Plugin, commands
from .cache import CacheDriver, MemoryCacheDriver
from .captcha import CaptchaDriver, AltchaCaptchaDriver
from .event import subscribe, publish
from .lib import meta
from . import views


logger = logging.getLogger(__name__)







class MetaPlugin(Plugin):
    """\
    Add meta tags for content to the page
    """

    def init_app(self, app):
        super().init_app(app)
        subscribe('base.template.meta_tags', self.get_meta_tags)

    @staticmethod
    def get_meta_tags(event, value, *args, **kwargs):
        content = publish('meta.content', {})
        try:
            value += list(meta.get_meta_for_content(content))
        except:
            logger.error("Failed to generate meta tags for content\n%s", content, exc_info=True)
        return value
