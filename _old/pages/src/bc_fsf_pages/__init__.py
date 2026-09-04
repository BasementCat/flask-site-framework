"""Render static-ish pages"""

from typing import List, Union

import re
import json

from flask import current_app, url_for, g

from bc_fsf_base import Plugin
from bc_fsf_base import cache, event
from bc_fsf_base.jinja import route_matches


class PagesPlugin(Plugin):
    """\
    Provide an implementation of pages for a site, loading from jinja templates
    """

    def get_blueprints(self):
        from .views import pages
        return [(None, pages.bp)]

    def init_app(self, app):
        super().init_app(app)
        event.subscribe('meta.content', self.get_current_page_info)
        event.subscribe('sitemap.urls', self.get_sitemap_urls)
        event.subscribe('robots.txt.rules', self.robots_txt_exclude)
        event.subscribe('base.template.meta_tags', self.add_noindex_tag)

    def get_current_page_info(self, event, value, *args, **kwargs):
        """\
        Get metadata for the currently loaded page
        """

        if 'pages_current_slug' in g:
            page = self.list_pages(slug=g.pages_current_slug)
            if page and len(page) == 1:
                value.update(page[0])
        return value

    def get_sitemap_urls(self, event, urls, *args, **kwargs):
        """\
        Get URLs to add to the sitemap based on the page configuration
        """

        default = {'changefreq': 'monthly', 'priority': 0.5}
        for p in self.list_pages():
            if p.get('show_in_sitemap') is None:
                if not p.get('show_in_nav'):
                    continue
            elif not p.get('show_in_sitemap'):
                continue

            u = dict(default, **{'url': p['ext_url']})
            if p.get('sitemap_changefreq'):
                u['changefreq'] = p['sitemap_changefreq']
            if p.get('sitemap_priority'):
                u['priority'] = p['sitemap_priority']
            mod = p.get('updated_at') or p.get('created_at')
            if mod:
                u['modified'] = mod
            urls.append(u)
        return urls

    def robots_txt_exclude(self, event, rules, *args, **kwargs):
        """\
        Get URLs to exclude via robots.txt
        """

        exclusions = {}
        for p in self.list_pages():
            if p.get('noindex'):
                exclusions.setdefault('*', []).append(p['url'])
            elif p.get('robots_exclude'):
                ex = p['robots_exclude']
                if not isinstance(ex, list):
                    ex = [ex]
                for ua in ex:
                    exclusions.setdefault(ua, []).append(p['url'])

        for ua, ex in exclusions.items():
            rules.append(f'User-Agent: {ua}')
            for url in ex:
                rules.append(f'Disallow: {url}')

        return rules

    def add_noindex_tag(self, event, tags, *args, **kwargs):
        """\
        Add a noindex tag to the page, if configured
        """

        if 'pages_current_slug' in g:
            page = self.list_pages(slug=g.pages_current_slug)
            if page and len(page) == 1:
                if page[0].get('noindex'):
                    tags.append('<meta name="robots" content="noindex" />')
        return tags

    @staticmethod
    def _list_pages():
        """\
        Get a list of all discovered pages
        """

        out = []
        for template in current_app.jinja_env.loader.list_templates():
            # For now, assume that all pages are in pages/* and there is no nesting (the route doesn't allow it anyway)
            parts = template.split('/')
            if len(parts) == 2 and parts[0] == 'pages':
                slug = parts[1].split('.')[0]
                props = {
                    'url': url_for('pages.view', page=slug),
                    'ext_url': url_for('pages.view', page=slug, _external=True),
                    'slug': slug,
                    'title': ' '.join(re.split(r'[_-]+', slug)).title(),
                    'is_home': False,
                    'show_in_nav': True,
                    'priority': 100,
                }
                data, _, _ = current_app.jinja_env.loader.get_source(current_app.jinja_env, template)
                if '{# {{{' in data:
                    data = data.split('{# {{{', 1)[1].split('}}} #}')[0]
                    props.update(json.loads('{' + data + '}'))
                if props['is_home']:
                    props.update({
                        'url': url_for('pages.view'),
                        'ext_url': url_for('pages.view', _external=True),
                    })
                out.append(props)
        return out

    def list_pages(self, **filters) -> List[dict]:
        """\
        List pages matching the filters against the page metadata
        """

        out = cache.get_or_fetch(
            'pages_plugin_list',
            self._list_pages,
            expires_in=300
        )
        def _flt(p):
            for k, v in filters.items():
                if p.get(k) != v:
                    return False
            return True
        return list(sorted(filter(_flt, out), key=lambda p: p.get('priority', 100)))


@PagesPlugin.jinja_global()
def list_pages(**filters) -> List[dict]:
    """List pages, but in a template"""

    return current_app.plugins['pages'].list_pages(**filters)


@PagesPlugin.jinja_global()
def get_page(**filters) -> Union[None, dict]:
    """\
    Get a single page within a template, or None if the number of matching
    pages is not 1
    """

    pages = current_app.plugins['pages'].list_pages(**filters)
    if len(pages) != 1:
        return None
    return pages[0]


@PagesPlugin.jinja_global()
def page_url(**filters) -> Union[None, str]:
    """\
    Get the URL for a page matching filters, as with get_page, the number of
    matching pages must be 1
    """

    page = get_page(**filters)
    if not page:
        # TODO: log
        return '#'
    return page['url']


@PagesPlugin.jinja_global()
def page_route_matches(slug: str) -> bool:
    """Determine if the current route matches the given page slug"""

    return route_matches('pages.view', page=slug)
