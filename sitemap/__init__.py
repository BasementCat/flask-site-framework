"""Generate sitemaps/robots.txt"""

from typing import List, Dict, Any, Union

import logging
import json
import os
import shutil

from flask import current_app, url_for
import arrow

from app.plugins.base import Plugin
from app.plugins.base import event


logger = logging.getLogger(__name__)


class SitemapPlugin(Plugin):
    """\
    Sitemap implementation for a site
    """

    def get_config(self):
        return {
            'SITEMAP_INDEX': {
                'parser': int,
                'default': 0,
                'description': "Enable sitemap index, with this many URLs per file (files must not be larger than 50MB or 50,000 URLs)",
            },
            'SITEMAP_AGE': {
                'parser': int,
                'default': 3600,
                'description': "Regenerate sitemaps after this duration",
            },
            'SITEMAP_AUTO': {
                'parser': bool,
                'default': True,
                'description': "Autogenerate sitemaps on request as necessary - if using a cron, disable for a performance boost",
            },
        }

    def get_blueprints(self):
        from . import view
        return [(None, view.bp_sm)]

    def get_commands(self):
        from . import commands
        return [commands.cli_sm]

    def init_app(self, app):
        super().init_app(app)
        event.subscribe('robots.txt.rules', self.robots_txt_sitemap, priority=10000)

    def robots_txt_sitemap(self, event, rules, *args, **kwargs):
        """Add the sitemap URL to robots.txt"""

        if current_app.config.get('SITEMAP_INDEX'):
            u = url_for('sitemap.get_sitemap_index', _external=True)
        else:
            u = url_for('sitemap.get_sitemap', _external=True)

        rules.append(f'Sitemap: {u}')
        return rules

    def _make_sitemap_file(self, urls: List[Dict[str, Any]]) -> bytes:
        """\
        Given a list of URL data, generate a utf-8 encoded sitemap file
        """

        out = '''\
            <?xml version="1.0" encoding="UTF-8"?>
            <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        '''
        for url in urls:
            if url.get('url'):
                out += '<url><loc>' + url['url'] + '</loc>'
            if url.get('modified'):
                out += '<lastmod>' + arrow.get(url['modified']).format('YYYY-MM-DD') + '</lastmod>'
            if url.get('changefreq'):
                out += '<changefreq>' + url['changefreq'] + '</changefreq>'
            if url.get('priority'):
                out += '<priority>{:1.1f}</priority>'.format(url['priority'])
            out += '</url>'

        out += '</urlset>'
        return out.strip().encode('utf-8')

    def _make_sitemap_index(self, n: int) -> bytes:
        """\
        Given the highest numbered sitemap file, generate a utf-8 encoded
        sitemap index file
        """

        out = '''\
            <?xml version="1.0" encoding="UTF-8"?>
            <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        '''
        for i in range(1, n+1):
            out += '<sitemap><loc>' + url_for('sitemap.get_sitemap_n', idx=i, _external=True) + '</loc></sitemap>'
        out += '</sitemapindex>'
        return out.strip().encode('utf-8')

    def clear_sitemap(self):
        """Delete all sitemap files"""

        if os.path.exists(self.tempdir):
            shutil.rmtree(self.tempdir)

    def generate_sitemap(self):
        """Generate sitemap files for later use"""

        tempdir = self.tempdir
        urls = event.publish('sitemap.urls', [])
        if not urls:
            return

        if current_app.config.get('SITEMAP_INDEX'):
            chunk_size = min(current_app.config['SITEMAP_INDEX'], 50000)
            n = 0
            for i in range(0, len(urls), chunk_size):
                n += 1
                with open(os.path.join(tempdir, f'sitemap_{n}.xml'), 'wb') as fp:
                    res = self._make_sitemap_file(urls[i:i+chunk_size])
                    written = 0
                    while written < len(res):
                        written += fp.write(res[written:])
            with open(os.path.join(tempdir, 'sitemap_index.xml'), 'wb') as fp:
                res = self._make_sitemap_index(n)
                written = 0
                while written < len(res):
                    written += fp.write(res[written:])
        else:
            if len(urls) >= 50000:
                logger.error("Sitemap is limited to 50000 urls, have %d, must configure SITEMAP_INDEX size", len(urls))
            elif len(urls) >= 45000:
                logger.warning("Sitemap is limited to 50000 urls, have %d, should configure SITEMAP_INDEX size soon", len(urls))

            with open(os.path.join(tempdir, 'sitemap.xml'), 'wb') as fp:
                res = self._make_sitemap_file(urls)
                written = 0
                while written < len(res):
                    written += fp.write(res[written:])

        with open(os.path.join(tempdir, 'sitemap_meta.json'), 'w') as fp:
            json.dump({'generated': str(arrow.utcnow())}, fp)

    def maybe_generate_sitemap(self):
        """\
        Generate sitemap files if they are missing or expired, and configured to
        automatically do so
        """

        gentime = None
        try:
            with open(os.path.join(self.tempdir, 'sitemap_meta.json'), 'r') as fp:
                meta = json.load(fp)
                gentime = arrow.get(meta['generated'])
        except:
            pass

        if not gentime or (arrow.utcnow() - gentime).total_seconds() >= current_app.config['SITEMAP_AGE']:
            if not current_app.config['SITEMAP_AUTO']:
                logger.error("Sitemap is expired or not present, but SITEMAP_AUTO is false, not generating")
                return
            self.generate_sitemap()

    def get_sitemap(self) -> Union[bytes, bool]:
        """Get the main sitemap file, if configured"""

        self.maybe_generate_sitemap()
        try:
            with open(os.path.join(self.tempdir, 'sitemap.xml'), 'rb') as fp:
                return fp.read()
        except:
            return False

    def get_sitemap_index(self) -> Union[bytes, bool]:
        """Get the sitemap index file, if configured"""

        self.maybe_generate_sitemap()
        try:
            with open(os.path.join(self.tempdir, 'sitemap_index.xml'), 'rb') as fp:
                return fp.read()
        except:
            return False

    def get_sitemap_by_number(self, idx: int) -> Union[bytes, bool]:
        """Get a numbered sitemap file, if configured"""

        self.maybe_generate_sitemap()
        try:
            with open(os.path.join(self.tempdir, f'sitemap_{idx}.xml'), 'rb') as fp:
                return fp.read()
        except:
            return False


class RobotsPlugin(Plugin):
    """Generate robots.txt"""

    def get_config(self):
        return {
            'ROBOTS_AGE': {
                'parser': int,
                'default': 3600,
                'description': "Regenerate robots.txt after this duration",
            },
            'ROBOTS_AUTO': {
                'parser': bool,
                'default': True,
                'description': "Autogenerate robots.txt on request as necessary - if using a cron, disable for a performance boost",
            },
        }

    def get_blueprints(self):
        from . import view
        return [(None, view.bp_rt)]

    def get_commands(self):
        from . import commands
        return [commands.cli_rt]

    def init_app(self, app):
        super().init_app(app)
        event.subscribe('robots.txt.rules', self.add_default_rules, priority=9000)

    def add_default_rules(self, event_, rules, *args, **kwargs):
        """\
        Publish an event to get default allow rules for robots.txt.

        This may be overridden if the default allow behavior is not desired.

        The rules, if present, are inserted near the end of the file (pri=9000)
        """

        default_allow = event.publish('robots.txt.default-allow', ['User-Agent: *', 'Allow: /'])
        rules += default_allow
        return rules

    def clear_robots(self):
        """Delete cached robots.txt"""

        if os.path.exists(self.tempdir):
            shutil.rmtree(self.tempdir)

    def generate_robots(self):
        """Generate a robots.txt file for later use"""

        tempdir = self.tempdir
        lines = event.publish('robots.txt.rules', [])
        if not lines:
            return

        with open(os.path.join(tempdir, 'robots.txt'), 'wb') as fp:
            for line in lines:
                fp.write((line + '\n').encode('utf-8'))

        with open(os.path.join(tempdir, 'robots_meta.json'), 'w') as fp:
            json.dump({'generated': str(arrow.utcnow())}, fp)

    def maybe_generate_robots(self):
        """\
        Generate a robots.txt file if it is missing or expired, and configured
        to automatically do so
        """

        gentime = None
        try:
            with open(os.path.join(self.tempdir, 'robots_meta.json'), 'r') as fp:
                meta = json.load(fp)
                gentime = arrow.get(meta['generated'])
        except:
            pass

        if not gentime or (arrow.utcnow() - gentime).total_seconds() >= current_app.config['ROBOTS_AGE']:
            if not current_app.config['ROBOTS_AUTO']:
                logger.error("Robots.txt is expired or not present, but ROBOTS_AUTO is false, not generating")
                return
            self.generate_robots()

    def get_robots(self) -> Union[bytes, bool]:
        """\
        Get the robots.txt file
        """

        self.maybe_generate_robots()
        try:
            with open(os.path.join(self.tempdir, 'robots.txt'), 'rb') as fp:
                return fp.read()
        except:
            return False
