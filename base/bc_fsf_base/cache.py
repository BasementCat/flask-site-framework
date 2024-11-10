"""Caching implementation"""

from typing import Any, Union, Optional

from threading import Lock
import time
from functools import wraps

from flask import current_app


class CacheDriver:
    """\
    Cache driver base class/implementation documentation.

    A cache driver implements the raw storage and retrieval of cache keys.
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
            if out['expires'] < time.time():
                del self.data[key]
                raise KeyError(key)
            return out['data']

    def delete(self, key: str):
        with self.lock:
            del self.data[key]

    def contains(self, key: str) -> bool:
        with self.lock:
            return key in self.data


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