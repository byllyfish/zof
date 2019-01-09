"""Public API."""

from typing import Optional, List, Dict, Coroutine, Any

import asyncio

from .controller import Controller, ZOF_CONTROLLER
from .configuration import Configuration
from .datapath import Datapath
from .driver import Driver
from .exception import RequestError

__all__ = ('run_controller', 'get_config', 'get_datapaths', 'find_datapath',
           'create_task', 'post_event', 'get_driver', 'Configuration',
           'Datapath', 'RequestError')


async def run_controller(app: object,
                         *,
                         config: Optional[Configuration] = None) -> int:
    """Run controller app using specified configuration."""
    controller = Controller(app, config)
    return await controller.run()


def _get_controller() -> Controller:
    """Return currently running controller instance."""
    return ZOF_CONTROLLER.get()


def get_config() -> Configuration:
    """Return current configuration."""
    return _get_controller().get_config()


def get_datapaths() -> List[Datapath]:
    """Return list of existing datapaths."""
    return _get_controller().get_datapaths()


def find_datapath(datapath_id: int) -> Optional[Datapath]:
    """Find datapath by datapath_id."""
    return _get_controller().find_datapath(datapath_id)


def create_task(coro: Coroutine) -> asyncio.Task:
    """Create a task."""
    return _get_controller().create_task(coro)


def post_event(event: Dict[str, Any]) -> None:
    """Post a custom event."""
    get_driver().post_event(event)


def get_driver() -> Driver:
    """Return current driver instance."""
    return _get_controller().get_driver()
