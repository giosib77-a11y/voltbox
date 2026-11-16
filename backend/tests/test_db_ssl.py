"""The three `DB_SSL_MODE` settings, as `build_connect_args()` turns them into an SSL context.

`require` encrypts and does not authenticate the server; only `verify-full`
with the project's CA does. Before these tests nothing checked either: a
`verify-full` that quietly verified nothing, or a mistyped CA path that
surfaced as a bare FileNotFoundError, would both have passed CI.

No connection is opened - the contexts are inspected, not used. The CA file is
one certificate cut out of certifi's public bundle (a public root, not a secret).
"""

import logging
import ssl
from pathlib import Path
from typing import Any

import certifi
import pytest
from app import main as app_main
from app.core.config import Settings
from app.db import ssl as db_ssl

REMOTE_PASSWORD = "s3cretpw"
REMOTE_URL = f"postgresql://postgres:{REMOTE_PASSWORD}@db.example-ref.supabase.co:5432/postgres"
LOCAL_URL = "postgresql://voltbox:voltbox@localhost:55432/voltbox"


def _settings(
    *,
    mode: str,
    root_cert: str = "",
    url: str = REMOTE_URL,
    app_env: str = "development",
) -> Settings:
    return Settings(
        app_env=app_env,
        database_url=url,
        jwt_secret="x" * 40,
        db_ssl_mode=mode,
        db_ssl_root_cert=root_cert,
    )


def _use(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> None:
    monkeypatch.setattr(db_ssl, "settings", _settings(**kwargs))


@pytest.fixture
def ca_file(tmp_path: Path) -> Path:
    """A one-certificate PEM file: the first root in certifi's bundle."""
    bundle = Path(certifi.where()).read_text(encoding="ascii")
    first = bundle.split("-----END CERTIFICATE-----")[0]
    pem = first[first.index("-----BEGIN CERTIFICATE-----") :] + "-----END CERTIFICATE-----\n"
    path = tmp_path / "ca.crt"
    path.write_text(pem, encoding="ascii")
    return path


def _context(args: dict[str, Any]) -> ssl.SSLContext:
    context = args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    return context


def _db_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "voltbox.db" and r.levelno == logging.WARNING]


class TestDisable:
    def test_no_tls_at_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _use(monkeypatch, mode="disable")
        assert db_ssl.build_connect_args() == {}

    def test_even_with_a_ca_configured(
        self, monkeypatch: pytest.MonkeyPatch, ca_file: Path
    ) -> None:
        _use(monkeypatch, mode="disable", root_cert=str(ca_file))
        assert db_ssl.build_connect_args() == {}


class TestRequire:
    def test_encrypts_without_authenticating_the_server(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _use(monkeypatch, mode="require")
        context = _context(db_ssl.build_connect_args())
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE

    def test_with_a_ca_configured_it_still_verifies_fully(
        self, monkeypatch: pytest.MonkeyPatch, ca_file: Path
    ) -> None:
        # Setting DB_SSL_ROOT_CERT is an intent to verify; the mode name does not
        # switch that off.
        _use(monkeypatch, mode="require", root_cert=str(ca_file))
        context = _context(db_ssl.build_connect_args())
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED

    def test_deployed_warns_that_the_server_is_not_authenticated(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="require", app_env="production")
        with caplog.at_level(logging.WARNING, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        warnings = _db_warnings(caplog)
        assert len(warnings) == 1
        message = warnings[0].getMessage()
        assert "not authenticated" in message
        assert "verify-full" in message
        assert "docs/deployment.md" in message

    def test_staging_warns_too(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="require", app_env="staging")
        with caplog.at_level(logging.WARNING, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        assert len(_db_warnings(caplog)) == 1

    def test_the_warning_does_not_name_the_database_url(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="require", app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        assert REMOTE_PASSWORD not in caplog.text
        assert "example-ref" not in caplog.text

    def test_not_deployed_says_nothing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="require", app_env="development")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        assert _db_warnings(caplog) == []

    def test_deployed_with_a_ca_says_nothing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, ca_file: Path
    ) -> None:
        _use(monkeypatch, mode="require", root_cert=str(ca_file), app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        assert _db_warnings(caplog) == []

    def test_building_the_connect_args_is_silent(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # session.py calls it at import, before configure_logging: a line written
        # there would come out as plain text. The warning belongs to the lifespan.
        _use(monkeypatch, mode="require", app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.build_connect_args()
        assert _db_warnings(caplog) == []


class TestDisableWarning:
    """A-086: `disable` on a deployed environment is weaker than `require`, and said nothing."""

    @pytest.mark.parametrize("app_env", ["production", "staging"])
    def test_deployed_warns_that_the_connection_is_unencrypted(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, app_env: str
    ) -> None:
        _use(monkeypatch, mode="disable", app_env=app_env)
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        [record] = _db_warnings(caplog)
        message = record.getMessage()
        assert "unencrypted" in message
        assert "DB_SSL_MODE=verify-full" in message
        assert "DB_SSL_ROOT_CERT" in message
        assert "docs/deployment.md" in message
        # The owner's check for the `require` line must not match this one.
        assert "not authenticated" not in message
        assert REMOTE_PASSWORD not in caplog.text
        assert "example-ref" not in caplog.text

    def test_a_ca_does_not_silence_it(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, ca_file: Path
    ) -> None:
        # `disable` wins over DB_SSL_ROOT_CERT: no TLS is used at all.
        _use(monkeypatch, mode="disable", root_cert=str(ca_file), app_env="production")
        assert db_ssl.build_connect_args() == {}
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        assert len(_db_warnings(caplog)) == 1

    def test_not_deployed_says_nothing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="disable", app_env="development")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        assert _db_warnings(caplog) == []

    def test_a_local_database_says_nothing_even_when_deployed(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Nothing leaves the machine; the compose setup is `disable` + a local host.
        _use(monkeypatch, mode="disable", url=LOCAL_URL, app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.log_tls_mode()
        assert _db_warnings(caplog) == []

    def test_building_the_connect_args_is_silent(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="disable", app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.build_connect_args()
        assert _db_warnings(caplog) == []


class TestVerifyFull:
    def test_requires_the_certificate_and_the_hostname_with_the_ca_loaded(
        self, monkeypatch: pytest.MonkeyPatch, ca_file: Path
    ) -> None:
        _use(monkeypatch, mode="verify-full", root_cert=str(ca_file))
        context = _context(db_ssl.build_connect_args())
        assert context.check_hostname is True
        assert context.verify_mode == ssl.CERT_REQUIRED
        # Exactly the file's certificate was loaded - not the system store, not nothing.
        loaded = context.get_ca_certs(binary_form=True)
        expected = ssl.PEM_cert_to_DER_cert(ca_file.read_text(encoding="ascii"))
        assert loaded == [expected]

    def test_without_a_ca_setting_it_refuses_to_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _use(monkeypatch, mode="verify-full")
        with pytest.raises(RuntimeError, match="DB_SSL_MODE=verify-full requires DB_SSL_ROOT_CERT"):
            db_ssl.build_connect_args()

    def test_a_missing_file_names_the_setting(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        missing = tmp_path / "not-there.crt"
        _use(monkeypatch, mode="verify-full", root_cert=str(missing))
        with pytest.raises(RuntimeError) as caught:
            db_ssl.build_connect_args()
        message = str(caught.value)
        assert "DB_SSL_ROOT_CERT" in message
        assert str(missing) in message
        assert REMOTE_PASSWORD not in message
        assert "supabase.co" not in message

    def test_a_file_that_is_not_a_certificate_names_the_setting(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        junk = tmp_path / "junk.crt"
        junk.write_text("this is not a PEM certificate\n", encoding="ascii")
        _use(monkeypatch, mode="verify-full", root_cert=str(junk))
        with pytest.raises(RuntimeError, match="DB_SSL_ROOT_CERT"):
            db_ssl.build_connect_args()

    def test_a_directory_instead_of_a_file_names_the_setting(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _use(monkeypatch, mode="verify-full", root_cert=str(tmp_path))
        with pytest.raises(RuntimeError, match="DB_SSL_ROOT_CERT"):
            db_ssl.build_connect_args()

    def test_a_broken_ca_also_stops_require(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # require + a path that does not work must not quietly fall back to
        # "encrypted, unverified".
        _use(monkeypatch, mode="require", root_cert=str(tmp_path / "not-there.crt"))
        with pytest.raises(RuntimeError, match="DB_SSL_ROOT_CERT"):
            db_ssl.build_connect_args()

    def test_no_warning_when_verifying(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, ca_file: Path
    ) -> None:
        _use(monkeypatch, mode="verify-full", root_cert=str(ca_file), app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.build_connect_args()
            db_ssl.log_tls_mode()
        assert _db_warnings(caplog) == []


class TestLocalDatabase:
    @pytest.mark.parametrize("mode", ["require", "verify-full"])
    def test_a_local_url_never_uses_tls(self, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
        # verify-full with no CA would raise against a remote URL; locally the
        # container has no TLS to verify.
        _use(monkeypatch, mode=mode, url=LOCAL_URL)
        assert db_ssl.build_connect_args() == {}

    def test_a_local_url_in_production_does_not_warn(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="require", url=LOCAL_URL, app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.build_connect_args()
            db_ssl.log_tls_mode()
        assert _db_warnings(caplog) == []


class _StubEngine:
    async def dispose(self) -> None:
        return None


class TestLifespan:
    async def test_the_warning_is_written_after_logging_is_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Before A-086 it was written while session.py was imported, ahead of
        # configure_logging, so it came out as plain text.
        calls: list[str] = []
        monkeypatch.setattr(app_main, "configure_logging", lambda: calls.append("logging"))
        monkeypatch.setattr(app_main, "log_tls_mode", lambda: calls.append("tls"))
        monkeypatch.setattr(app_main, "engine", _StubEngine())
        async with app_main.lifespan(app_main.app):
            pass
        assert calls[:2] == ["logging", "tls"]


REMOTE_HOST = "db.example-ref.supabase.co"


class TestRequiresSsl:
    """A-081: only the host decides, not any `localhost` anywhere in the URL."""

    @pytest.mark.parametrize(
        "url",
        [
            "postgresql://voltbox:voltbox@localhost:55432/voltbox",
            "postgresql+asyncpg://voltbox:voltbox@127.0.0.1:55432/voltbox",
            "postgresql://voltbox:voltbox@[::1]:55432/voltbox",
            "postgresql://voltbox:voltbox@LOCALHOST/voltbox",
            "postgresql://voltbox@localhost/voltbox",
        ],
    )
    def test_a_local_host_does_not_require_tls(self, url: str) -> None:
        assert _settings(mode="require", url=url).requires_ssl is False

    @pytest.mark.parametrize(
        "url",
        [
            # the word in the password, the user, the database name, the query
            f"postgresql://postgres:localhost1234@{REMOTE_HOST}:5432/postgres",
            f"postgresql://postgres:127.0.0.1@{REMOTE_HOST}:5432/postgres",
            f"postgresql://localhost:pw@{REMOTE_HOST}:5432/postgres",
            f"postgresql://postgres:pw@{REMOTE_HOST}:5432/localhost",
            f"postgresql://postgres:pw@{REMOTE_HOST}:5432/postgres?application_name=localhost",
            f"postgresql+asyncpg://postgres:localhost1234@{REMOTE_HOST}:5432/postgres",
            # the password holds `@`, `:`, `/` or percent-encoding next to the word
            f"postgresql://postgres:p%40localhost%3A1@{REMOTE_HOST}:5432/postgres",
            f"postgresql://postgres:p@localhost:1@{REMOTE_HOST}:5432/postgres",
            f"postgresql://postgres:localhost:127.0.0.1@{REMOTE_HOST}:5432/postgres",
            # a remote host that merely starts or ends with the word
            "postgresql://postgres:pw@localhost.evil.example:5432/postgres",
            "postgresql://postgres:pw@notlocalhost:5432/postgres",
            # a local-looking host that the query string redirects
            "postgresql://postgres:pw@localhost/postgres?host=db.example.com",
            "postgresql://postgres:pw@localhost/postgres?hostaddr=203.0.113.7",
            # no host, or a URL that cannot be read: fail safe, TLS on
            "postgresql:///postgres?application_name=localhost",
            "not a url, but it mentions localhost",
            "",
        ],
    )
    def test_everything_else_requires_tls(self, url: str) -> None:
        assert _settings(mode="require", url=url).requires_ssl is True

    def test_a_remote_url_with_localhost_in_the_password_gets_tls(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The scenario of the finding: verify-full with no CA must refuse, not
        # open a plaintext connection to the remote database.
        url = f"postgresql://postgres:localhost1234@{REMOTE_HOST}:5432/postgres"
        _use(monkeypatch, mode="require", url=url)
        context = _context(db_ssl.build_connect_args())
        assert context.verify_mode == ssl.CERT_NONE
        _use(monkeypatch, mode="verify-full", url=url)
        with pytest.raises(RuntimeError, match="DB_SSL_ROOT_CERT"):
            db_ssl.build_connect_args()
