import logging

from app.core.logging import configure_logging


def test_transport_loggers_do_not_emit_request_headers() -> None:
    configure_logging()

    for name in ("httpx", "httpcore", "hpack"):
        assert logging.getLogger(name).level == logging.WARNING
