"""ყველა API-სქემის ბაზისი.

ბაზა snake_case-ია, API — camelCase, რადგან frontend უკვე `totalPages`,
`orderNumber`, `discountPercent`, `hasDiscount`, `inStock`, `isLowStock`-ს ელოდება.
ალიასს ავტომატურად ვაგენერირებთ — camelCase სახელები ხელით არსად არ იწერება.
"""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    """გამომავალი (response) მოდელების ბაზისი."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        ser_json_timedelta="iso8601",
    )


class ApiRequest(BaseModel):
    """შემომავალი (request) მოდელების ბაზისი.

    `extra="forbid"` განზრახ: თუ კლიენტი უცნობ ველს გამოგზავნის (მაგ. `price`
    შეკვეთაში), მოთხოვნა 400-ით ჩავარდება. კონტრაქტის რეგრესია ხმაურით უნდა
    გამოჩნდეს, არა ჩუმად იგნორირდეს — იხ. §10 ფასის გაყალბების დაცვა.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        str_strip_whitespace=True,
    )
