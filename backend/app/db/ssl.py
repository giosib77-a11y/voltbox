"""ბაზასთან TLS-კავშირის კონფიგურაცია.

Supabase-ის სერტიფიკატი მათი საკუთარი CA-თია ხელმოწერილი და საჯარო trust store-ში
არ არის — ამიტომ სრული ვერიფიკაცია (`verify-full`) მხოლოდ მაშინ მუშაობს, როცა
პროექტის CA ხელით გვაქვს ჩამოტვირთული.

რეჟიმები (`DB_SSL_MODE`):
  disable      — TLS გამორთულია (მხოლოდ ლოკალური კონტეინერისთვის).
                 დეპლოიზე (`is_deployed`) არალოკალურ ბაზასთან — warning
                 „unencrypted“ (`log_tls_mode`).
  require      — ტრაფიკი დაშიფრულია, სერვერი არ მოწმდება.
                 ესაა Supabase-ის საკუთარი connection string-ის ნაგულისხმევი
                 (`?sslmode=require`) და პლატფორმის რეკომენდებული მინიმუმი.
                 დეპლოიზე (`is_deployed`) CA-ს გარეშე — warning „not authenticated“
                 (`log_tls_mode`, lifespan-იდან, ყოველ worker-ზე ერთხელ).
  verify-full  — დაშიფვრა + სერვერის ავთენტიფიკაცია (სერტიფიკატი CA-ს უნდა
                 ემთხვეოდეს და hostname-ს უნდა ფარავდეს). მოითხოვს `DB_SSL_ROOT_CERT`-ს:
                 Dashboard → Settings → Database → SSL Configuration → Download.

⚠️ `require` MITM-ისგან არ იცავს. პროდაქშენისთვის CA ჩამოტვირთე და
`verify-full` ჩართე — ეს ორი ცვლადის ცვლილებაა (docs/deployment.md, „ბაზასთან TLS").

`require` + `DB_SSL_ROOT_CERT`: სერვერი მაინც სრულად მოწმდება. ცვლადის დაყენება
ვერიფიკაციის განზრახვაა და მდუმარედ გამორთვა სახიფათო დაქვეითება იქნებოდა; რეჟიმის
სახელი ამ შემთხვევაში არაფერს ცვლის.
"""

import logging
import ssl
from typing import Any

from app.core.config import settings

logger = logging.getLogger("voltbox.db")


def _verifying_context(cafile: str) -> ssl.SSLContext:
    """Full verification against the CA in `cafile`: certificate chain and hostname."""
    try:
        context = ssl.create_default_context(cafile=cafile)
    except (OSError, ssl.SSLError) as exc:
        # The path is configuration, not a secret; the database URL is never
        # part of this message. A bare FileNotFoundError / SSLError would not
        # say which setting to fix.
        raise RuntimeError(
            f"DB_SSL_ROOT_CERT='{cafile}' cannot be used as a CA bundle "
            f"({type(exc).__name__}). It must be the path of a readable PEM "
            "certificate file (see docs/deployment.md, 'ბაზასთან TLS')."
        ) from exc
    # create_default_context already sets both; stated so the guarantee does not
    # depend on a library default.
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context


def build_connect_args() -> dict[str, Any]:
    """asyncpg-ის `connect_args` — ერთი წყარო session.py-სთვისაც და alembic-ისთვისაც."""
    mode = settings.db_ssl_mode

    if mode == "disable" or not settings.requires_ssl:
        return {}

    if settings.db_ssl_root_cert:
        return {"ssl": _verifying_context(settings.db_ssl_root_cert)}

    if mode == "verify-full":
        # ცხადი შეცდომა სჯობს მდუმარე დაქვეითებას verify-ის გარეშე რეჟიმზე
        raise RuntimeError(
            "DB_SSL_MODE=verify-full requires DB_SSL_ROOT_CERT. Download the project "
            "certificate from Supabase → Settings → Database → SSL Configuration."
        )

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}


def log_tls_mode() -> None:
    """Warn, on a deployed environment, when the database link is weaker than `verify-full`.

    A warning, not a refusal: production keeps starting exactly as it did. It is
    called from the lifespan (app/main.py), after `configure_logging`, so the line
    goes through the JSON logger; at import time (session.py) it came out as plain
    text. It runs once per worker process. `build_connect_args` itself stays
    silent - alembic/env.py calls it too and the check does not belong to a
    migration run. A local database host never uses TLS (`requires_ssl`), so it
    is not a finding. Neither line names the database URL.
    """
    if not settings.is_deployed or not settings.requires_ssl:
        return

    if settings.db_ssl_mode == "disable":
        # Even with DB_SSL_ROOT_CERT set: `disable` wins in build_connect_args.
        logger.warning(
            "The database connection is unencrypted (DB_SSL_MODE=disable) to a "
            "non-local host. Set DB_SSL_MODE=verify-full and DB_SSL_ROOT_CERT to "
            "the Supabase CA file - docs/deployment.md, section 'ბაზასთან TLS'."
        )
    elif settings.db_ssl_mode == "require" and not settings.db_ssl_root_cert:
        # The encryption holds; what is missing is proof of who answers.
        # The owner's check looks for 'not authenticated' - keep that phrase.
        logger.warning(
            "The database connection is encrypted but the server is not "
            "authenticated (DB_SSL_MODE=require). Set DB_SSL_MODE=verify-full and "
            "DB_SSL_ROOT_CERT to the Supabase CA file - docs/deployment.md, "
            "section 'ბაზასთან TLS'."
        )
