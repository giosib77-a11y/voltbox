"""პაგინაციის საერთო პარამეტრები და პასუხის კონვერტი.

frontend ყველა სიისგან ზუსტად ამ ფორმას ელოდება:
    {items, total, page, totalPages, limit, facets}
"""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.base import ApiModel

# Upper bound of every `page` input. Without one, `page=9223372036854775807` makes
# OFFSET (page - 1) * limit overflow int64 and asyncpg answers 500. 10 000 is far
# beyond any real page count at this catalogue size, and 10 000 * max_page_size
# stays inside int64 by a wide margin. Past it the answer is a 400, not a clamp.
MAX_PAGE = 10_000


class PageParams(BaseModel):
    """`limit`-ის ზედა ზღვარს განზრახ არ ვჭრით ჩუმად — 400-ს ვაბრუნებთ.

    ჩუმი clamp კლიენტს აფიქრებინებს, რომ 500 ჩანაწერი მიიღო, სინამდვილეში კი 100.
    """

    page: int = Field(default=1, ge=1, le=MAX_PAGE)
    limit: int = Field(default=settings.default_page_size, ge=1, le=settings.max_page_size)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def page_params(
    page: Annotated[int, Query(ge=1, le=MAX_PAGE, description="1-based page number")] = 1,
    limit: Annotated[
        int,
        Query(ge=1, le=settings.max_page_size, description="Items per page"),
    ] = settings.default_page_size,
) -> PageParams:
    return PageParams(page=page, limit=limit)


class Page[T](ApiModel):
    items: list[T]
    total: int
    page: int
    total_pages: int
    limit: int


def total_pages(total: int, limit: int) -> int:
    """ცარიელ შედეგზე 0 — frontend `totalPages > 1`-ს ამოწმებს პაგინაციის საჩვენებლად."""
    if total <= 0:
        return 0
    return -(-total // limit)
