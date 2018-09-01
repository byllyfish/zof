"""Logging configuration."""

import logging
import os

logger = logging.getLogger(__package__)

if os.getenv('ZOFDEBUG'):  # pragma: no cover
    logging.basicConfig()
    logger.setLevel(logging.DEBUG)
    logger.debug('ZOFDEBUG enabled')
