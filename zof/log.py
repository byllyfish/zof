"""Logging configuration."""

import logging
import os

logger = logging.getLogger(__package__)

ZOFDEBUG = int(os.getenv('ZOFDEBUG', '0'))

if ZOFDEBUG > 0:  # pragma: no cover
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    logger.debug('ZOFDEBUG=%d enabled', ZOFDEBUG)
