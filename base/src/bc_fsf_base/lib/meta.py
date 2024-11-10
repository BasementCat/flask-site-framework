"""\
Meta tag and LD+JSON generation
"""

from typing import List, Optional, Generator, Iterable, Callable, Any, Tuple, Union

import re
import json

from flask import request, current_app
import arrow
import purl


def make_full_url(url: str) -> str:
    """\
    Given an URL or path, return a fully qualified URL using the current
    request's hostname/port/scheme
    """

    if url is not None and url.startswith('/'):
        base = str(purl.URL(request.url).path('').query('').fragment(''))
        url = base.rstrip('/') + url
    return url


class ContentDescriptor:
    """\
    An object representing a piece of content, for generating meta tags.
    """

    @classmethod
    def parse_images_videos(cls, data: dict, base_key: str) -> dict:
        """\
        Parse image and video data from the content dict, producing a new dict
        with the available properties.

        * data: Content dict
        * base_key: Key within the content dict that contains the images or videos to parse
        """

        default = {
            'url': None,
            'mime': None,
            'width': None,
            'height': None,
            'alt': None,
        }
        multi_key = base_key + 's'
        items = data.get(multi_key)
        if not items:
            if data.get(base_key):
                items = list(filter(None, [data[base_key]]))
        for i in items or []:
            if not isinstance(i, dict):
                i = {'url': i}
            i = dict(default, **i)
            i['url'] = make_full_url(i['url'])
            if i['url']:
                yield i

    @classmethod
    def parse_authors(cls, data: dict) -> dict:
        """\
        Parse author data from the content dict, producing a new dict with the
        available properties.

        * data: Content dict
        """

        default = {
            'url': None,
            'name': None,
            'first_name': None,
            'last_name': None,
            'username': None,
        }
        authors = data.get('authors')
        if not authors:
            if data.get('author'):
                authors = list(filter(None, [data['author']]))
        for a in authors or []:
            if not isinstance(a, dict):
                a = {'name': a}
            a = dict(default, **a)
            a['url'] = make_full_url(a['url'])

            combined_name = ' '.join(filter(None, (a['first_name'], a['last_name']))) or None
            split_name = a['name'].split(' ', 1) if a['name'] else (None, None)
            a['name'] = a['name'] or combined_name or a['username']
            a['first_name'] = a['first_name'] or split_name[0]
            a['last_name'] = a['last_name'] or split_name[1]
            a['username'] = a['username'] or re.sub(r'[^\w\d_-]+', '_', a['name'] or combined_name or '').lower() or None
            if a['name']:
                yield a

    @classmethod
    def parse_cs(cls, data: dict, key: str) -> List[str]:
        """\
        Parse comma-separated data from the content dict, returning a list of
        items.

        * data: Content dict
        * key: Key in the content dict to parse
        """
        items = data.get(key)
        if items and not isinstance(items, list):
            return re.split(r',\s*', items)
        return items or []

    def __init__(self, data: dict):
        """\
        Parse a dictionary of data representing content into a standardized
        format used to generate meta tags and LD JSON.

        * data: Content dict
        """

        self.site_name = data.get('site_name') or current_app.config.get('SITE_NAME')
        self.site_logo = data.get('site_logo')
        self.site_description = data.get('site_description')
        self.site_email = data.get('site_email')
        self.copyright = data.get('copyright')
        self.url = request.url
        self.title = data.get('title')
        self.description = data.get('description') or data.get('summary') or data.get('excerpt')
        self.is_adult = data.get('is_adult') or False
        # Should be website, article, profile, or organization
        self.content_type = data.get('content_type') or 'website'
        self.images = list(self.parse_images_videos(data, 'image'))
        self.videos = list(self.parse_images_videos(data, 'video'))
        self.authors = list(self.parse_authors(data))
        self.published_at = arrow.get(data['published_at']) if data.get('published_at') else None
        self.modified_at = arrow.get(data['modified_at']) if data.get('modified_at') else None
        self.expires_at = arrow.get(data['expires_at']) if data.get('expires_at') else None
        self.categories = self.parse_cs(data, 'categories')
        self.tags = self.parse_cs(data, 'tags')


class Tag:
    """\
    Generate a meta tag based on content data.
    """

    def __init__(self, name: str, attr: Optional[str]=None, prop: str='property', const: Optional[str]=None):
        """\
        Instantiate a new tag object.

        * name: Name of the tag
        * attr: Attribute of the content descriptor to use for the tag value; defaults to the tag name, will strip leading 'og:' in this case
        * prop: Property of the tag in which to place the name - like 'property' or 'name' depending on the type of meta tag
        * const: If not None, if the property of the content descriptor is truthy, use this as the value instead of the value from the content
        """

        self.name = name
        self.attr = attr
        if not self.attr:
            self.attr = self.name
            if self.attr.startswith('og:'):
                self.attr = self.attr[3:]
        self.prop = prop
        self.const = const

    def __call__(self, cd: ContentDescriptor) -> Generator[str, None, None]:
        """\
        Generate the meta tag based on data in the content descriptor
        """

        if callable(self.attr):
            try:
                value = self.attr(cd)
            except (KeyError, AttributeError, IndexError):
                value = None
        else:
            value = getattr(cd, self.attr, None)

        if value == 'None':
            # hax
            value = None

        if self.const:
            if value:
                value = self.const
            else:
                value = None

        if value is not None:
            yield f'<meta {self.prop}="{self.name}" content="{value}" />'


class MultiTag:
    """\
    Generate several tags from properties of a content descriptor.
    """

    def __init__(self, attr: Union[Callable[[ContentDescriptor], Iterable[Any]], str], tags: Iterable[Tag]):
        """\
        Create a new instance to check the given attribute, and generate the
        given tags.

        If `attr` is callable, it is called with the content descriptor and its
        return value is used instead of a named attribute.
        """

        self.attr = attr
        self.tags = tags

    def __call__(self, cd: ContentDescriptor) -> Generator[str, None, None]:
        """\
        Iterate through values from the content attribute or callable return
        value, and the tags, and generate tags
        """

        if callable(self.attr):
            try:
                value = self.attr(cd)
            except (KeyError, AttributeError, IndexError):
                value = None
        else:
            value = getattr(cd, self.attr, None)

        if value:
            for item in value:
                for tag in self.tags:
                    yield from tag(item)


class LDProperty:
    """\
    Represents a property of an LD+JSON object
    """

    def __init__(self, key: str, attr: Optional[Union[Callable[[ContentDescriptor], Any], str]]=None, array: bool=False, transform: Callable[[Any], Any]=lambda v: v, const: Optional[Any]=None):
        """\
        Create an LD property having the given key, and retrieved from the given
        attribute of the content descriptor.

        * key: Key in the LD+JSON object
        * attr: String attribute, or callable receiving the content descriptor.  Defaults to key
        * array: If true, treat the value as a list
        * transform: A callable called on the value (or each item in value if array=True) to transform it
        * const: If not None, and the value is truthy, use as the value instead
        """

        self.key = key
        self.attr = attr or key
        self.array = array
        self.transform = transform
        self.const = const

    def __call__(self, cd: ContentDescriptor) -> Iterable[Tuple[str, Any]]:
        """\
        Yield key/value pairs representing properties to be added to the LD object
        """

        value = None
        try:
            if callable(self.attr):
                value = self.attr(cd)
            else:
                value = getattr(cd, self.attr, None)
        except (KeyError, AttributeError, IndexError):
            pass

        if value is not None:
            if self.array and not isinstance(value, list):
                value = [value]
            elif isinstance(value, list) and not self.array:
                value = value[0]

            if isinstance(value, list):
                value = list(map(self.transform, value))
            else:
                value = self.transform(value)

            if self.const is not None:
                value = self.const if value else None

            if value is not None:
                yield self.key, value


class LDObject:
    """\
    Represents an LD+JSON object
    """

    def __init__(self, type_: str, properties: Iterable[LDProperty], is_root: bool=False, condition: Optional[Callable[[ContentDescriptor], bool]]=None):
        """\
        Create a new LD object.

        * type_: Type fo the object, for the "@type" key
        * is_root: If true, this is the root object and will contain a "@context" key
        * condition: Callable accepting the content descriptor, if the return value is not truthy, the object is not rendered
        """

        self.type_ = type_
        self.properties = properties
        self.is_root = is_root
        self.condition = condition

    def __call__(self, cd: ContentDescriptor) -> dict:
        """\
        Generate and return the LD object
        """

        if callable(self.condition) and not self.condition(cd):
            return
        out = {'@type': self.type_}
        if self.is_root:
            out['@context'] = 'https://schema.org'
        for prop in self.properties:
            for key, value in prop(cd):
                out[key] = value
        return out


class LDObjectList:
    """\
    Represents a list of LD objects to be rendered
    """

    def __init__(self, key: str, objects: Iterable[LDObject], condition: Optional[Callable[[ContentDescriptor], bool]]=None):
        """\
        Create a new LD object list with the given key and objects

        * key: Key to be set on the outer object
        * objects: LDObject instances to render
        * condition: A callable accepting the content descriptor, if the return value is not truthy, the list is not rendered
        """

        self.key = key
        self.objects = objects
        self.condition = None

    def __call__(self, cd: ContentDescriptor) -> Generator[Tuple[str, Any], None, None]:
        """\
        Generate the list of objects
        """

        if not callable(self.condition) or self.condition(cd):
            out = list(filter(None, (o(cd) for o in self.objects)))
            if out:
                yield self.key, out


def get_meta_for_content(content: dict) -> Generator[str, None, None]:
    """\
    Given the content dict, create a content descriptor and yield meta tags and
    an ld+json tag for the content
    """

    cd = ContentDescriptor(content)
    yield from get_tags_for_content(cd)
    yield from get_ld_for_content(cd)


def get_tags_for_content(cd: ContentDescriptor) -> Generator[str, None, None]:
    """\
    Given a content descriptor, generate meta tags for the content
    """
    possible_tags = [
        Tag('og:url'),
        Tag('og:site_name'),
        Tag('description', prop='name'),
        Tag('og:description'),
        Tag('rating', attr='is_adult', prop='name', const='adult'),
        Tag('og:title'),
        Tag('og:type', attr='content_type'),
        Tag('author', attr=lambda cd: cd.authors[0]['name'] if cd.authors else None, prop='name'),
        Tag('contact', attr='site_email', prop='name'),
        Tag('copyright', attr='copyright', prop='name'),

        MultiTag(lambda cd: cd.images, [
            Tag('og:image', attr=lambda item: item['url']),
            Tag('og:image:type', attr=lambda item: item['mime']),
            Tag('og:image:width', attr=lambda item: item['width']),
            Tag('og:image:height', attr=lambda item: item['height']),
            Tag('og:image:alt', attr=lambda item: item['alt']),
        ]),

        MultiTag(lambda cd: cd.videos, [
            Tag('og:video', attr=lambda item: item['url']),
            Tag('og:video:type', attr=lambda item: item['mime']),
            Tag('og:video:width', attr=lambda item: item['width']),
            Tag('og:video:height', attr=lambda item: item['height']),
            Tag('og:video:alt', attr=lambda item: item['alt']),
        ])
    ]
    if cd.content_type == 'website':
        pass
    elif cd.content_type == 'article':
        possible_tags += [
            Tag('article:published_time', attr=lambda cd: str(cd.published_at)),
            Tag('article:modified_time', attr=lambda cd: str(cd.modified_at)),
            Tag('article:expiration_time', attr=lambda cd: str(cd.expires_at)),
            MultiTag(lambda cd: cd.authors, [
                # Not sure if this is right, docs are unclear
                Tag('article:author', attr=lambda item: item['name']),
                Tag('article:author:first_name', attr=lambda item: item['first_name']),
                Tag('article:author:last_name', attr=lambda item: item['last_name']),
                Tag('article:author:username', attr=lambda item: item['username']),
            ]),
            Tag('article:section', attr=lambda cd: cd.categories[0]),
            MultiTag(lambda cd: cd.tags, [Tag('article:tag', attr=lambda item: item)]),
        ]
    elif cd.content_type == 'profile':
        possible_tags += [
            # Not sure if this is right, docs are unclear
            Tag('profile', attr=lambda cd: cd.authors[0]['name']),
            Tag('profile:first_name', attr=lambda cd: cd.authors[0]['first_name']),
            Tag('profile:last_name', attr=lambda cd: cd.authors[0]['last_name']),
            Tag('profile:username', attr=lambda cd: cd.authors[0]['username']),
        ]
    elif cd.content_type == 'organization':
        pass

    for tag in possible_tags:
        yield from tag(cd)


def get_ld_for_content(cd: ContentDescriptor) -> Generator[str, None, None]:
    """\
    Given a content descriptor, generate LD+JSON tag for the content
    """

    ld_candidates = {
        'article': LDObject('NewsArticle', [
            LDProperty('headline', attr='title'),
            LDProperty('image', attr='images', array=True, transform=lambda i: i['url']),
            LDProperty('datePublished', attr='published_at', transform=str),
            LDProperty('dateModified', attr='modified_at', transform=str),
            LDProperty('author', attr='authors', array=True, transform=LDObject('Person', [
                LDProperty('name', attr=lambda a: a['name']),
                LDProperty('url', attr=lambda a: a['url']),
            ]))
        ], is_root=True),
        'organization': LDObject('Organization', [
            LDProperty('image', attr='images', transform=lambda i: i['url']),
            LDProperty('url'),
            LDProperty('logo', attr='site_logo', transform=lambda i: i['url']),
            LDProperty('name', attr='site_name'),
            LDProperty('description', attr='site_description'),
            LDProperty('email', attr='site_email'),
        ], is_root=True),
        'profile': LDObject('ProfilePage', [
            LDProperty('dateCreated', attr='published_at', transform=str),
            LDProperty('dateModified', attr='modified_at', transform=str),
            LDProperty('mainEntity', attr='authors', transform=LDObject('Person', [
                LDProperty('name', attr=lambda a: a['name']),
                LDProperty('alternateName', attr=lambda a: a['username']),
                LDProperty('identifier', attr=lambda a: a['id']),
                LDProperty('description', attr=lambda a: a['bio']),
                LDProperty('image', attr=lambda a: a['images'], transform=lambda i: i['url']),
                LDObjectList('interactionStatistic', [
                    LDObject('InteractionCounter', [
                        LDProperty('interactionType', attr=lambda a: a.get('follow_count'), const='https://schema.org/FollowAction'),
                        LDProperty('userInteractionCount', attr=lambda a: a.get('follow_count'), transform=int),
                    ], condition=lambda a: a.get('follow_count')),
                    LDObject('InteractionCounter', [
                        LDProperty('interactionType', attr=lambda a: a.get('like_count'), const='https://schema.org/LikeAction'),
                        LDProperty('userInteractionCount', attr=lambda a: a.get('like_count'), transform=int),
                    ], condition=lambda a: a.get('like_count')),
                ], condition=lambda a: a.get('like_count') or a.get('follow_count')),
                LDProperty('agentInteractionStatistic', attr=lambda a: a.get('post_count'), transform=LDObject('InteractionCounter', [
                    LDProperty('interactionType', attr=lambda pc: pc, const='https://schema.org/WriteAction'),
                    LDProperty('userInteractionCount', attr=lambda pc: pc, transform=int),
                ], condition=lambda pc: pc))
            ]))
        ], is_root=True),
    }
    ld = ld_candidates.get(cd.content_type)
    if ld:
        yield '<script type="application/ld+json">{}</script>'.format(json.dumps(ld(cd)))


if __name__ == '__main__':
    import sys
    from flask import Flask
    app = Flask(__name__)

    base_data = {
        'site_name': 'Example Site',
        'title': 'Example Page title',
        'summary': "This is an example summary of a post, page, site, etc",
        'is_adult': True,
        # Should be website, article, profile, or organization
        'content_type': 'website',
        'images': [
            {
                'url': '/url/to/image1.jpg',
                'mime': 'image/jpeg',
                'width': 800,
                'height': 600,
                'alt': 'foo',
            },
            {
                'url': 'http://example.com/url/to/image2.jpg',
                'alt': 'bar',
            },
            '/url/to/image3.jpg',
        ],
        'videos': [
            {
                'url': '/url/to/video1.mp4',
                'mime': 'video/mp4',
                'width': 800,
                'height': 600,
                'alt': 'foo',
            },
            {
                'url': 'http://example.com/url/to/video2.mp4',
                'alt': 'bar',
            },
            '/url/to/video3.mp4',
        ],
        'authors': [
            {
                'url': '/profile/author1',
                'name': 'Test Author1',
                'first_name': 'Test',
                'last_name': 'Author1',
                'username': 'author1',
                'like_count': 3,
                'follow_count': 4,
                'post_count': 5,
            },
            {
                'url': '/profile/author2',
                'name': 'Test Author2',
            },
            {
                'url': '/profile/author3',
                'first_name': 'Test',
                'last_name': 'Author3',
            },
            'Test Author4',
        ],
        'published_at': '2024-03-01 12:34:56',
        'modified_at': '2024-04-05 23:45:01',
        # expires_at
        'categories': ['Food', 'Travel'],
        'tags': ['events', 'foo', 'bar'],
    }
    tests = [
        [
            base_data,
            [
                '<meta property="og:url" content="http://localhost/" />',
                '<meta property="og:site_name" content="Example Site" />',
                '<meta name="description" content="This is an example summary of a post, page, site, etc" />',
                '<meta property="og:description" content="This is an example summary of a post, page, site, etc" />',
                '<meta name="rating" content="adult" />',
                '<meta property="og:title" content="Example Page title" />',
                '<meta property="og:type" content="website" />',
                '<meta property="og:image" content="http://localhost/url/to/image1.jpg" />',
                '<meta property="og:image:type" content="image/jpeg" />',
                '<meta property="og:image:width" content="800" />',
                '<meta property="og:image:height" content="600" />',
                '<meta property="og:image:alt" content="foo" />',
                '<meta property="og:image" content="http://example.com/url/to/image2.jpg" />',
                '<meta property="og:image:alt" content="bar" />',
                '<meta property="og:image" content="http://localhost/url/to/image3.jpg" />',
                '<meta property="og:video" content="http://localhost/url/to/video1.mp4" />',
                '<meta property="og:video:type" content="video/mp4" />',
                '<meta property="og:video:width" content="800" />',
                '<meta property="og:video:height" content="600" />',
                '<meta property="og:video:alt" content="foo" />',
                '<meta property="og:video" content="http://example.com/url/to/video2.mp4" />',
                '<meta property="og:video:alt" content="bar" />',
                '<meta property="og:video" content="http://localhost/url/to/video3.mp4" />',
            ],
            None,
        ],
        [
            dict(base_data, **{
                'content_type': 'article',
            }),
            [
                '<meta property="og:url" content="http://localhost/" />',
                '<meta property="og:site_name" content="Example Site" />',
                '<meta name="description" content="This is an example summary of a post, page, site, etc" />',
                '<meta property="og:description" content="This is an example summary of a post, page, site, etc" />',
                '<meta name="rating" content="adult" />',
                '<meta property="og:title" content="Example Page title" />',
                '<meta property="og:type" content="article" />',
                '<meta property="og:image" content="http://localhost/url/to/image1.jpg" />',
                '<meta property="og:image:type" content="image/jpeg" />',
                '<meta property="og:image:width" content="800" />',
                '<meta property="og:image:height" content="600" />',
                '<meta property="og:image:alt" content="foo" />',
                '<meta property="og:image" content="http://example.com/url/to/image2.jpg" />',
                '<meta property="og:image:alt" content="bar" />',
                '<meta property="og:image" content="http://localhost/url/to/image3.jpg" />',
                '<meta property="og:video" content="http://localhost/url/to/video1.mp4" />',
                '<meta property="og:video:type" content="video/mp4" />',
                '<meta property="og:video:width" content="800" />',
                '<meta property="og:video:height" content="600" />',
                '<meta property="og:video:alt" content="foo" />',
                '<meta property="og:video" content="http://example.com/url/to/video2.mp4" />',
                '<meta property="og:video:alt" content="bar" />',
                '<meta property="og:video" content="http://localhost/url/to/video3.mp4" />',

                '<meta property="article:published_time" content="2024-03-01T12:34:56+00:00" />',
                '<meta property="article:modified_time" content="2024-04-05T23:45:01+00:00" />',
                # '<meta property="article:expiration_time" content="" />',
                
                '<meta property="article:author" content="Test Author1" />',
                '<meta property="article:author:first_name" content="Test" />',
                '<meta property="article:author:last_name" content="Author1" />',
                '<meta property="article:author:username" content="author1" />',

                '<meta property="article:author" content="Test Author2" />',
                '<meta property="article:author:first_name" content="Test" />',
                '<meta property="article:author:last_name" content="Author2" />',
                '<meta property="article:author:username" content="test_author2" />',

                '<meta property="article:author" content="Test Author3" />',
                '<meta property="article:author:first_name" content="Test" />',
                '<meta property="article:author:last_name" content="Author3" />',
                '<meta property="article:author:username" content="test_author3" />',

                '<meta property="article:author" content="Test Author4" />',
                '<meta property="article:author:first_name" content="Test" />',
                '<meta property="article:author:last_name" content="Author4" />',
                '<meta property="article:author:username" content="test_author4" />',
                
                '<meta property="article:section" content="Food" />',
                '<meta property="article:tag" content="events" />',
                '<meta property="article:tag" content="foo" />',
                '<meta property="article:tag" content="bar" />',
            ],
            {
                "@type": "NewsArticle",
                "@context": "https://schema.org",
                "headline": "Example Page title",
                "image": [
                    "http://localhost/url/to/image1.jpg",
                    "http://example.com/url/to/image2.jpg",
                    "http://localhost/url/to/image3.jpg"
                ],
                "datePublished": "2024-03-01T12:34:56+00:00",
                "dateModified": "2024-04-05T23:45:01+00:00",
                "author": [
                    {
                        "@type": "Person",
                        "name": "Test Author1",
                        "url": "http://localhost/profile/author1"
                    },
                    {
                        "@type": "Person",
                        "name": "Test Author2",
                        "url": "http://localhost/profile/author2"
                    },
                    {
                        "@type": "Person",
                        "name": "Test Author3",
                        "url": "http://localhost/profile/author3"
                    },
                    {
                        "@type": "Person",
                        "name": "Test Author4"
                    }
                ]
            }
        ],
        [
            dict(base_data, **{
                'content_type': 'profile',
            }),
            [
                '<meta property="og:url" content="http://localhost/" />',
                '<meta property="og:site_name" content="Example Site" />',
                '<meta name="description" content="This is an example summary of a post, page, site, etc" />',
                '<meta property="og:description" content="This is an example summary of a post, page, site, etc" />',
                '<meta name="rating" content="adult" />',
                '<meta property="og:title" content="Example Page title" />',
                '<meta property="og:type" content="profile" />',
                '<meta property="og:image" content="http://localhost/url/to/image1.jpg" />',
                '<meta property="og:image:type" content="image/jpeg" />',
                '<meta property="og:image:width" content="800" />',
                '<meta property="og:image:height" content="600" />',
                '<meta property="og:image:alt" content="foo" />',
                '<meta property="og:image" content="http://example.com/url/to/image2.jpg" />',
                '<meta property="og:image:alt" content="bar" />',
                '<meta property="og:image" content="http://localhost/url/to/image3.jpg" />',
                '<meta property="og:video" content="http://localhost/url/to/video1.mp4" />',
                '<meta property="og:video:type" content="video/mp4" />',
                '<meta property="og:video:width" content="800" />',
                '<meta property="og:video:height" content="600" />',
                '<meta property="og:video:alt" content="foo" />',
                '<meta property="og:video" content="http://example.com/url/to/video2.mp4" />',
                '<meta property="og:video:alt" content="bar" />',
                '<meta property="og:video" content="http://localhost/url/to/video3.mp4" />',

                '<meta property="profile" content="Test Author1" />',
                '<meta property="profile:first_name" content="Test" />',
                '<meta property="profile:last_name" content="Author1" />',
                '<meta property="profile:username" content="author1" />',
            ],
            {
                "@type": "ProfilePage",
                "@context": "https://schema.org",
                "dateCreated": "2024-03-01T12:34:56+00:00",
                "dateModified": "2024-04-05T23:45:01+00:00",
                "mainEntity": {
                    "@type": "Person",
                    "name": "Test Author1",
                    "alternateName": "author1",
                    "interactionStatistic": [
                        {
                            "@type": "InteractionCounter",
                            "interactionType": "https://schema.org/FollowAction",
                            "userInteractionCount": 4
                        },
                        {
                            "@type": "InteractionCounter",
                            "interactionType": "https://schema.org/LikeAction",
                            "userInteractionCount": 3
                        }
                    ],
                    "agentInteractionStatistic": {
                        "@type": "InteractionCounter",
                        "interactionType": "https://schema.org/WriteAction",
                        "userInteractionCount": 5
                    }
                }
            }
        ],
        [
            dict(base_data, **{
                'content_type': 'organization',
            }),
            [
                '<meta property="og:url" content="http://localhost/" />',
                '<meta property="og:site_name" content="Example Site" />',
                '<meta name="description" content="This is an example summary of a post, page, site, etc" />',
                '<meta property="og:description" content="This is an example summary of a post, page, site, etc" />',
                '<meta name="rating" content="adult" />',
                '<meta property="og:title" content="Example Page title" />',
                '<meta property="og:type" content="organization" />',
                '<meta property="og:image" content="http://localhost/url/to/image1.jpg" />',
                '<meta property="og:image:type" content="image/jpeg" />',
                '<meta property="og:image:width" content="800" />',
                '<meta property="og:image:height" content="600" />',
                '<meta property="og:image:alt" content="foo" />',
                '<meta property="og:image" content="http://example.com/url/to/image2.jpg" />',
                '<meta property="og:image:alt" content="bar" />',
                '<meta property="og:image" content="http://localhost/url/to/image3.jpg" />',
                '<meta property="og:video" content="http://localhost/url/to/video1.mp4" />',
                '<meta property="og:video:type" content="video/mp4" />',
                '<meta property="og:video:width" content="800" />',
                '<meta property="og:video:height" content="600" />',
                '<meta property="og:video:alt" content="foo" />',
                '<meta property="og:video" content="http://example.com/url/to/video2.mp4" />',
                '<meta property="og:video:alt" content="bar" />',
                '<meta property="og:video" content="http://localhost/url/to/video3.mp4" />',
            ],
            {
                "@type": "Organization",
                "@context": "https://schema.org",
                "image": "http://localhost/url/to/image1.jpg",
                "url": "http://localhost/",
                "name": "Example Site"
            }
        ],
    ]
    with app.app_context(), app.test_request_context():
        for test_data, expected_tags, expected_ld in tests:
            try:
                res = list(get_meta_for_content(test_data))
                for t in expected_tags:
                    assert t in res, f"Missing tag: {repr(t)}"
                for t in res:
                    if not t.startswith('<script'):
                        assert t in expected_tags, f"Unexpected tag: {repr(t)}"
                ld = [t for t in res if t.startswith('<script')]
                assert len(ld) < 2, "Too many ld tags present"
                if expected_ld is None:
                    assert len(ld) < 1, "LD tag present, expected none"
                else:
                    assert ld, "LD missing"
                    ld = ld[0]
                    ld = re.sub(r'^<script[^>]+>', '', ld)
                    ld = re.sub(r'</script>$', '', ld)
                    ld = json.loads(ld)
                    assert ld == expected_ld, f"LD mismatch\nExpected:\n{json.dumps(expected_ld, indent=4)}\n\nActual:\n{json.dumps(ld, indent=4)}"
            except AssertionError as e:
                print(f"Error: {e}")
                print("\nTags:\n" + '\n'.join((t for t in res if not t.startswith('<script'))))
                sys.exit(1)
    print("OK")