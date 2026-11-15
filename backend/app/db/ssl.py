"""ბაზასთან TLS-კავშირის კონფიგურაცია.

Supabase-ის სერტიფიკატი მათი საკუთარი CA-თია ხელმოწერილი და საჯარო trust store-ში
არ არის — ამიტომ სრული ვერიფიკაცია (`verify-full`) მხოლოდ მაშინ მუშაობს, როცა
პროექტის CA ხელით გვაქვს ჩამოტვირთული.

რეჟიმები (`DB_SSL_MODE`):
  disable      — TLS გამორთულია (მხოლოდ ლოკალური კონტეინერისთვის)
  require      — ტრაფიკი დაშიფრულია, სერვერი არ მოწმდება.
                 ესაა Supabase-ის საკუთარი connection string-ის ნაგულისხმევი
                 (`?sslmode=require`) და პლატფორმის რეკომენდებული მინიმუმი.
                 დეპლოიზე (`is_deployed`) ამ რეჟიმში გაშვებისას ერთი warning იწერება.
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

    if settings.is_deployed:
        # A warning, not a refusal: production keeps starting exactly as it did.
        # The encryption still holds; what is missing is proof of who answers.
        # Called once per process (session.py at import, alembic/env.py per run).
        logger.warning(
            "The database connection is encrypted but the server is not "
            "authenticated (DB_SSL_MODE=require). Set DB_SSL_MODE=verify-full and "
            "DB_SSL_ROOT_CERT to the Supabase CA file - docs/deployment.md, "
            "section 'ბაზასთან TLS'."
        )

    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return {"ssl": context}
