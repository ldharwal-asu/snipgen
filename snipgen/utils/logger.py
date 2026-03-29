"""Logging configuration for SnipGen."""

import logging
import sys


def get_logger(name: str, verbose: bool = False) -> logging.Logger:
    """Return a configured logger for the given module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                              datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if verbose else logging.WARNING)
    return logger


def configure_root(verbose: bool = False) -> None:
    """Configure the root snipgen logger level (called once from CLI)."""
    logging.getLogger("snipgen").setLevel(
        logging.DEBUG if verbose else logging.INFO
    )
