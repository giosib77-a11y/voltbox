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
            db_ssl.build_connect_args()
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
            db_ssl.build_connect_args()
        assert len(_db_warnings(caplog)) == 1

    def test_the_warning_does_not_name_the_database_url(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="require", app_env="production")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.build_connect_args()
        assert REMOTE_PASSWORD not in caplog.text
        assert "example-ref" not in caplog.text

    def test_not_deployed_says_nothing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _use(monkeypatch, mode="require", app_env="development")
        with caplog.at_level(logging.DEBUG, logger="voltbox.db"):
            db_ssl.build_connect_args()
        assert _db_warnings(caplog) == []

    def test_deployed_with_a_ca_says_nothing(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, ca_file: Path
    ) -> None:
        _use(monkeypatch, mode="require", root_cert=str(ca_file), app_env="production")
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
        assert _db_warnings(caplog) == []
