"""Caching implementation"""

from typing import Any, Union, Optional
from threading import Lock
import time
from functools import wraps
import hashlib
import pickle

from flask import Flask, current_app
from flask_redis import FlaskRedis

from . import Plugin


class CacheDriver:
    """\
    Cache driver base class/implementation documentation.

    A cache driver implements the raw storage and retrieval of cache keys.
    """

    def require_config(self, config: dict) -> dict:
        """\
        Modify the config keys of the caching plugin, in order to mark certain
        config keys as required for this driver
        """
        return config

    def get_flask_plugins(self):
        """\
        Get required flask plugins; see base plugin class
        """

    def set(self, key: str, value: Any, expires_at: Optional[Union[int, float]]=None):
        """\
        Set the value of the given cache key to value, optionally expiring at the given unix timestamp.

        The timestamp may be expressed as a float for convenience, however actual resolution will
        be dependent upon the underlying cache backend.

        Implementation is required.
        """
        raise NotImplementedError()

    def get(self, key: str) -> Any:
        """\
        Get the value for the given key, raising KeyError if it cannot be found.

        Implementation is required.
        """
        raise NotImplementedError()

    def delete(self, key: str):
        """\
        Delete the value for the given key, raising KeyError if it cannot be found.

        Implementation is required.
        """
        raise NotImplementedError()

    def contains(self, key: str) -> bool:
        """\
        Return true or false to indicate the existence of a key.

        Implementation is optional.
        """
        raise NotImplementedError()


class MemoryCacheDriver(CacheDriver):
    """\
    An in-memory thread-safe cache driver.  See parent class for function information
    """

    def __init__(self):
        self.data = {}
        self.lock = Lock()

    def set(self, key: str, value: Any, expires_at: Optional[Union[int, float]]=None):
        with self.lock:
            self.data[key] = {'expires': expires_at, 'data': value}

    def get(self, key: str) -> Any:
        with self.lock:
            out = self.data[key]
            if out['expires'] is not None and out['expires'] < time.time():
                del self.data[key]
                raise KeyError(key)
            return out['data']

    def delete(self, key: str):
        with self.lock:
            del self.data[key]

    def contains(self, key: str) -> bool:
        with self.lock:
            return key in self.data


class RedisCacheDriver(CacheDriver):
    """\
    Mapping to Redis
    """

    def require_config(self, config: dict) -> dict:
        config['REDIS_URL']['required'] = True
        return config

    def get_flask_plugins(self):
        self.redis = FlaskRedis()
        return [self.redis]

    def set(self, key: str, value: Any, expires_at: Optional[Union[int, float]]=None):
        if expires_at is not None:
            self.redis.set(key, pickle.dumps(value), pxat=int(expires_at * 1000))
        else:
            self.redis.set(key, pickle.dumps(value))

    def get(self, key: str) -> Any:
        res = self.redis.get(key)
        if res is None:
            raise KeyError(key)
        return pickle.loads(res)

    def delete(self, key: str):
        # for compatibility - redis doesn't care if the key doesn't exist
        if not self.contains(key):
            raise KeyError(key)
        self.redis.delete(key)

    def contains(self, key: str) -> bool:
        return self.redis.exists(key) > 0


def _with_driver(callback):
    """\
    Internal function to automatically pass the current app's cache driver into
    a function
    """

    @wraps(callback)
    def _with_driver_wrapper(*args, **kwargs):
        driver = None
        try:
            driver = current_app._cache_driver
        except AttributeError:
            pass
        return callback(driver, *args, **kwargs)
    return _with_driver_wrapper


@_with_driver
def set(driver: Optional[CacheDriver], key: str, value: Any, expires_in: Optional[Union[int, float]]=None, expires_at: Optional[Union[int, float]]=None):
    """\
    Shorthand function for calling the same function on the application's cache
    driver, with sensible default behavior if no driver exists.
    """

    if driver:
        if expires_in is not None:
            expires_at = time.time() + expires_in
        return driver.set(key, value, expires_at=expires_at)


@_with_driver
def get(driver: Optional[CacheDriver], key: str, raise_missing: bool=False) -> Any:
    """\
    Shorthand function for calling the same function on the application's cache
    driver, with sensible default behavior if no driver exists.
    """

    if driver:
        try:
            return driver.get(key)
        except KeyError:
            if raise_missing:
                raise
    return None


@_with_driver
def delete(driver: Optional[CacheDriver], key: str, raise_missing: bool=False):
    """\
    Shorthand function for calling the same function on the application's cache
    driver, with sensible default behavior if no driver exists.
    """

    if not driver:
        return True
    try:
        driver.delete(key)
        return True
    except KeyError:
        if raise_missing:
            raise
        return False


@_with_driver
def contains(driver: Optional[CacheDriver], key: str) -> bool:
    """\
    Shorthand function for calling the same function on the application's cache
    driver, with sensible default behavior if no driver exists.
    """

    if driver:
        try:
            return driver.contains(key)
        except NotImplementedError:
            try:
                _ = driver.get(key)
                return True
            except KeyError:
                return False
    return False


@_with_driver
def get_or_fetch(driver: Optional[CacheDriver], key: str, callback, expires_in: Optional[Union[int, float]]=None, expires_at: Optional[Union[int, float]]=None):
    """\
    Shorthand function for calling the same function on the application's cache
    driver, with sensible default behavior if no driver exists.
    """

    if not driver:
        return callback()
    try:
        return get(key, raise_missing=True)
    except KeyError:
        value = callback()
        set(key, value, expires_in=expires_in, expires_at=expires_at)
        return value


def make_key(*args, **kwargs) -> str:
    """\
    Given a list of key parts and optional kwargs, assemble a cache key.

    Args are stringified and concatenated with ":", at least one is required.
    If kwargs are present, they are sorted by key, and hashed, and appended to
    the key.
    """

    if not args:
        raise ValueError("At least one argument is required")

    parts = list(map(str, args))
    if kwargs:
        kp = []
        for k in sorted(kwargs.keys()):
            kp.append(k + ':' + str(kwargs[k]))
        parts.append(hashlib.new('sha256', ':'.join(kp).encode('utf-8')).hexdigest())
    return ':'.join(parts)


class CachePlugin(Plugin):
    """\
    Enable caching on the application
    """

    def __init__(self, app: Optional[Flask]=None, driver: Optional[CacheDriver]=None):
        """\
        Initialize the cache plugin with an optional flask app.
        If no cache driver is provided, the memory cache driver is used.
        """

        self.driver = driver or MemoryCacheDriver()
        super().__init__(app=app)

    def get_config(self):
        return self.driver.require_config({
            'REDIS_URL': {
                'description': "URI to connect to Redis, like redis://:password@localhost:6379/0 or unix://:password@/path/to/socket.sock?db=0",
            },
        })

    def get_flask_plugins(self):
        return self.driver.get_flask_plugins()

    def init_app(self, app):
        super().init_app(app)
        app._cache_driver = self.driver
