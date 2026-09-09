"""ბაზასთან TLS-კავშირის კონფიგურაცია.

Supabase-ის სერტიფიკატი მათი საკუთარი CA-თია ხელმოწერილი და საჯარო trust store-ში
არ არის — ამიტომ სრული ვერიფიკაცია (`verify-full`) მხოლოდ მაშინ მუშაობს, როცა
პროექტის CA ხელით გვაქვს ჩამოტვირთული.

რეჟიმები (`DB_SSL_MODE`):
  disable      — TLS გამორთულია (მხოლოდ ლოკალური კონტეინერისთვის)
  require      — ტრაფიკი დაშიფრულია, სერვერი არ მოწმდება.
                 ესაა Supabase-ის საკუთარი connection string-ის ნაგულისხმევი
                 (`?sslmode=require`) და პლატფორმის რეკომენდებული მინიმუმი.
  verify-full  — დაშიფვრა + სერვერის ავთენტიფიკაცია. მოითხოვს `DB_SSL_ROOT_CERT`-ს:
                 Dashboard → Settings → Database → SSL Configuration → Download.

⚠️ `require` MITM-ისგან არ იცავს. პროდაქშენისთვის CA ჩამოტვირთე და
`verify-full` ჩართე — ეს ერთი ცვლადის ცვლილებაა.
"""

import ssl
from typing import Any

from app.core.config import settings


def build_connect_args() -> dict[str, Any]:
    """asyncpg-ის `connect_args` — ერთი წყარო session.py-სთვისაც და alembic-ისთვისაც."""
    mode = settings.db_ssl_mode

    if mode == "disable" or not settings.requires_ssl:
        return {}

    if settings.db_ssl_root_cert:
        context = ssl.create_default_context(cafile=settings.db_ssl_root_cert)
        return {"ssl": context}

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
