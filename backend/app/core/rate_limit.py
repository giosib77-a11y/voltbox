"""მოთხოვნების სიხშირის შეზღუდვა.

storage_uri მეხსიერებაშია — ერთი პროცესისთვის საკმარისი. რამდენიმე worker-ზე
გადასვლისას აქ Redis-ის URI ჩაიწერება და გამოძახების ადგილები არ იცვლება.

ტესტებში გამორთულია: 5/წუთში ზღვარი ტესტების მესამე შესვლას დაბლოკავდა და
ჩავარდნები ლოგიკასთან კავშირს დაკარგავდნენ.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],
    enabled=settings.app_env != "test",
)

# ბრუტფორსის ზღვარი — შესვლასა და რეგისტრაციაზე მკაცრი
AUTH_RATE_LIMIT = "5/minute"
