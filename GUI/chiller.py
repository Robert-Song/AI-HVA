import logging

logger = logging.getLogger(__name__)


def test_logs():
    logger.debug("test debug message")
    logger.info("test info message")