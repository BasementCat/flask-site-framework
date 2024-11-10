"""Simple priority event system"""

from typing import Callable, Any, Optional

event_callbacks = {}
"""All registered event callbacks"""


def subscribe(event: str, callback: Callable, priority: int=100) -> Any:
    """\
    Subscribe to an event.  When the event is published, the given callback is
    called with the event name, initial value (of a type dependent upon the
    event), and any provided *args/**kwargs.  The function must return the
    initial value (as appropriate), while some types of objects (list, dict, etc
    ) may be modified in place, the value MUST still be returned.

    Callbacks are called in order of ascending priority, callbacks having the
    same priority are called in order of subscription.
    """

    event_callbacks.setdefault(event, {}).setdefault(priority, []).append(callback)


def subscribes_to(event: str, priority: int=100) -> Callable:
    """\
    Decorator shorthand for calling `subscribe()`
    """

    def subscribes_impl(callback):
        subscribe(event, callback, priority=priority)
        return callback
    return subscribes_impl


def publish(event: str, init_arg: Optional[Any]=None, *args, **kwargs) -> Any:
    """\
    Publish an event, returning the value as passed through all subscribed
    callbacks.
    """

    cblist = event_callbacks.get(event, {})
    for pri in sorted(cblist.keys()):
        for cb in cblist.get(pri, []):
            init_arg = cb(event, init_arg, *args, **kwargs)
    return init_arg