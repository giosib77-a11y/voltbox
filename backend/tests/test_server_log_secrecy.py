"""The server's own loggers must not write what JsonFormatter would scrub.

A 500 on the registration path leaves Postgres's `DETAIL:  Key (email)=(...)
already exists.` in the exception. Starlette then re-raises it, and the one that
writes it is not our `voltbox.error` handler but uvicorn: "Exception in ASGI
application" plus the traceback, on `uvicorn.error`. Under gunicorn
UvicornWorker gives that logger gunicorn's plain handler and turns propagation
off - before the application's lifespan runs `configure_logging()` - so the
customer's email was written three times per crash, unscrubbed (A-034).

These tests therefore wire the loggers the way the server does FIRST and call
`configure_logging()` after, in lifespan order. Logging to `uvicorn.error` after
`configure_logging()` alone proves nothing: with no handler of its own the
record would propagate to the root handler and be scrubbed on the old code too.
"""

import io
import json
import logging
from collections.abc import Callable, Generator
from pathlib import Path

import pytest
import uvicorn.config
import uvicorn.logging
from app.core.logging import JsonFormatter, configure_logging

EMAIL = "x@y.com"
DETAIL = f"DETAIL:  Key (email)=({EMAIL}) already exists."
PLAIN_FORMAT = "[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s"

WATCHED = ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn.error", "voltbox.error")


@pytest.fixture(autouse=True)
def restore_logging() -> Generator[None]:
    """Put every logger these tests touch back, so no other test sees them."""
    loggers = [logging.getLogger(), *(logging.getLogger(name) for name in WATCHED)]
    saved = [(lg, list(lg.handlers), lg.propagate, lg.disabled, lg.level) for lg in loggers]
    try:
        yield
    finally:
        for lg, handlers, propagate, disabled, level in saved:
            lg.handlers[:] = handlers
            lg.propagate = propagate
            lg.disabled = disabled
            lg.setLevel(level)


@pytest.fixture
def output() -> io.StringIO:
    """Everything the logging system writes during a test, whichever handler."""
    return io.StringIO()


def _wire_like_uvicorn_worker(name: str, output: io.StringIO) -> None:
    """What UvicornWorker.__init__ does to `uvicorn.error`: gunicorn's own plain
    handler, and no propagation to root."""
    handler = logging.StreamHandler(output)
    handler.setFormatter(logging.Formatter(PLAIN_FORMAT))
    logger = logging.getLogger(name)
    logger.handlers = [handler]
    logger.propagate = False


def _wire_like_uvicorn_dev(output: io.StringIO) -> None:
    """`uvicorn app.main:app`: what uvicorn's LOGGING_CONFIG does to `uvicorn`
    and `uvicorn.error`, built by hand with the handler pointed at `output`.

    Not `dictConfig(LOGGING_CONFIG)`: a non-incremental dictConfig closes every
    handler in the process (`logging.shutdown` on `_handlerList`), and pytest's
    `--log-file` handler, a FileHandler in mode 'w', then drops records silently
    (A-070). Values are read from LOGGING_CONFIG so they cannot drift from it.
    `uvicorn.access` is left out: no test here relies on its dev wiring (the
    access-log test uses the worker wiring and `configure_logging` disables it).
    """
    config = uvicorn.config.LOGGING_CONFIG
    formatter_config = config["formatters"]["default"]
    loggers = config["loggers"]
    assert loggers["uvicorn"]["handlers"] == ["default"], "uvicorn's wiring changed"
    assert "handlers" not in loggers["uvicorn.error"], "uvicorn's wiring changed"

    handler = logging.StreamHandler(output)
    handler.setFormatter(
        uvicorn.logging.DefaultFormatter(
            fmt=formatter_config["fmt"], use_colors=formatter_config["use_colors"]
        )
    )
    parent = logging.getLogger("uvicorn")
    parent.handlers = [handler]
    parent.setLevel(loggers["uvicorn"]["level"])
    parent.propagate = loggers["uvicorn"]["propagate"]

    # No handler of its own: its records propagate to `uvicorn`.
    child = logging.getLogger("uvicorn.error")
    child.handlers = []
    child.setLevel(loggers["uvicorn.error"]["level"])
    child.propagate = True


def _configure(output: io.StringIO) -> None:
    """Run the lifespan step, then point the new root handler at `output`."""
    configure_logging()
    for handler in logging.getLogger().handlers:
        assert isinstance(handler, logging.StreamHandler)
        handler.setStream(output)


def _violation() -> BaseException:
    try:
        raise RuntimeError(f'duplicate key value violates unique constraint "ix"\n{DETAIL}')
    except RuntimeError as exc:
        return exc


def _log_the_crash(name: str) -> None:
    exc = _violation()
    logging.getLogger(name).error(
        "Exception in ASGI application\n", exc_info=(type(exc), exc, exc.__traceback__)
    )


def _log_the_value_in_the_message(name: str) -> None:
    logging.getLogger(name).error("insert failed: %s", DETAIL)


WIRINGS: dict[str, Callable[[str, io.StringIO], None]] = {
    "uvicorn_worker": _wire_like_uvicorn_worker,
    "uvicorn_dev": lambda name, output: _wire_like_uvicorn_dev(output),
}


@pytest.mark.parametrize("log", [_log_the_crash, _log_the_value_in_the_message])
class TestTheServersOwnLoggers:
    @pytest.mark.parametrize(
        ("wiring", "name"),
        [
            ("uvicorn_worker", "uvicorn.error"),
            ("uvicorn_worker", "gunicorn.error"),
            ("uvicorn_dev", "uvicorn.error"),
            ("uvicorn_dev", "uvicorn"),
        ],
    )
    def test_the_value_is_not_written_and_the_column_is(
        self,
        log: Callable[[str], None],
        wiring: str,
        name: str,
        output: io.StringIO,
    ) -> None:
        WIRINGS[wiring](name, output)
        _configure(output)

        log(name)

        written = output.getvalue()
        assert written, "nothing was written at all, so the test proves nothing"
        assert EMAIL not in written
        assert "Key (email)=(" in written, "the column is the useful half"

    def test_every_server_logger_reaches_the_json_handler(
        self, log: Callable[[str], None], output: io.StringIO
    ) -> None:
        """Both wirings at once: whichever logger the server writes through,
        the line is JSON, scrubbed, and carries the logger's name."""
        for name in ("uvicorn.error", "gunicorn.error"):
            _wire_like_uvicorn_worker(name, output)
        _configure(output)

        for name in ("uvicorn.error", "gunicorn.error"):
            log(name)

        lines = [json.loads(line) for line in output.getvalue().splitlines()]
        assert [line["logger"] for line in lines] == ["uvicorn.error", "gunicorn.error"]
        assert EMAIL not in output.getvalue()


class TestTheFailingRowIsNotWritten:
    """A NOT NULL or CHECK violation quotes the whole row, not `Key (...)` (A-067)."""

    @pytest.mark.parametrize("name", ["uvicorn.error", "gunicorn.error"])
    def test_a_crash_on_the_server_logger(self, name: str, output: io.StringIO) -> None:
        _wire_like_uvicorn_worker(name, output)
        _configure(output)
        try:
            raise RuntimeError(
                'new row for relation "orders" violates check constraint "ck"\n'
                f"DETAIL:  Failing row contains (1, {EMAIL}, 555123456, null)."
            )
        except RuntimeError as exc:
            logging.getLogger(name).error(
                "Exception in ASGI application\n", exc_info=(type(exc), exc, exc.__traceback__)
            )

        written = output.getvalue()
        assert written, "nothing was written at all, so the test proves nothing"
        assert EMAIL not in written
        assert "555123456" not in written
        assert "Failing row contains (" in written

    def test_a_value_in_the_message(self, output: io.StringIO) -> None:
        _wire_like_uvicorn_worker("uvicorn.error", output)
        _configure(output)

        logging.getLogger("uvicorn.error").error(
            "insert failed: %s", f"DETAIL:  Failing row contains (1, {EMAIL}, x)."
        )

        assert EMAIL not in output.getvalue()


class TestTheDevWiringLeavesOtherHandlersAlone:
    def test_a_file_handler_on_root_is_not_closed(
        self, tmp_path: Path, output: io.StringIO
    ) -> None:
        """A-070: dictConfig closed every handler in the process, and a closed
        FileHandler in mode 'w' (pytest's `--log-file`) silently drops records."""
        log_file = tmp_path / "x.log"
        file_handler = logging.FileHandler(log_file, mode="w")
        root = logging.getLogger()
        root.addHandler(file_handler)
        try:
            _wire_like_uvicorn_dev(output)
            root.error("after the wiring")
            file_handler.flush()

            assert file_handler.stream is not None, "the wiring closed the handler"
            assert "after the wiring" in log_file.read_text()
        finally:
            root.removeHandler(file_handler)
            file_handler.close()


class TestTheRestOfTheLoggingSetupStays:
    def test_the_access_log_of_uvicorn_is_still_off(self, output: io.StringIO) -> None:
        _wire_like_uvicorn_worker("uvicorn.access", output)
        _configure(output)

        logging.getLogger("uvicorn.access").info("127.0.0.1 - GET / 200")

        assert output.getvalue() == ""

    def test_our_own_error_line_is_unchanged(self, output: io.StringIO) -> None:
        _configure(output)

        _log_the_crash("voltbox.error")

        line = json.loads(output.getvalue())
        assert line["logger"] == "voltbox.error"
        assert EMAIL not in output.getvalue()
        assert "Key (email)=(" in line["exception"]


class TestTheFormatterScrubsTheMessage:
    def test_a_value_in_the_arguments(self) -> None:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed: %s", (DETAIL,), None)

        line = JsonFormatter().format(record)

        assert EMAIL not in line
        assert "Key (email)=(" in line

    def test_a_traceback_already_rendered_by_another_formatter(self) -> None:
        """logging.Formatter caches the text in `exc_text`; a record that went
        through a plain handler first arrives with it set."""
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", (), None)
        record.exc_text = f"Traceback ...\n{DETAIL}"

        line = JsonFormatter().format(record)

        assert EMAIL not in line
        assert "Key (email)=(" in line
