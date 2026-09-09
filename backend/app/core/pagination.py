"""პაგინაციის საერთო პარამეტრები და პასუხის კონვერტი.

frontend ყველა სიისგან ზუსტად ამ ფორმას ელოდება:
    {items, total, page, totalPages, limit, facets}
"""

from typing import Annotated

from fastapi import Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.base import ApiModel


class PageParams(BaseModel):
    """`limit`-ის ზედა ზღვარს განზრახ არ ვჭრით ჩუმად — 400-ს ვაბრუნებთ.

    ჩუმი clamp კლიენტს აფიქრებინებს, რომ 500 ჩანაწერი მიიღო, სინამდვილეში კი 100.
    """

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=settings.default_page_size, ge=1, le=settings.max_page_size)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def page_params(
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
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
