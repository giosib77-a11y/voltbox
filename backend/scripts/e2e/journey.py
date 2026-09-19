"""Section 18: the whole shop, over the network, on an empty database.

Not ASGI transport this time - a real uvicorn on :8100 and the real built
frontend on :4173. That is the difference between "the code is right" and "the
system is right": CORS, compression, proxy headers, cookies and the served
bundle only exist once something is actually listening on a socket.

The story it walks is the one that has to work on day one, in order:

    the owner sets the shop up  ->  a customer buys  ->  the shop fulfils
    ->  the customer sees it happen

with the cross-cutting checks a running server makes possible at the end.
"""

import io
import shutil
import struct
import sys
import zlib

import httpx

API = "http://127.0.0.1:8100"
V1 = f"{API}/api/v1"
ADMIN = f"{V1}/admin"
SHOP = "http://localhost:4173"

#: Resolved rather than bare, so ruff's "partial executable path" warning is
#: answered with a fact instead of a suppression.
DOCKER = shutil.which("docker") or "docker"

results: list[tuple[str, bool]] = []
# Only a real text stream has reconfigure; one replaced by a wrapper is left as is.
if isinstance(sys.stdout, io.TextIOWrapper):
    sys.stdout.reconfigure(encoding="utf-8")


def check(label: str, condition: object, detail: str = "") -> bool:
    ok = bool(condition)
    results.append((label, ok))
    print(f"  [{'OK  ' if ok else 'FAIL'}] {label}" + (f"  -> {detail}" if detail else ""))
    return ok


def png(width: int = 900, height: int = 900) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"".join(b"\x00" + b"\x30\x60\xf0" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


CUSTOMER = {
    "firstName": "ნინო",
    "lastName": "კაპანაძე",
    "phone": "577445566",
    "city": "თბილისი",
    "address": "აღმაშენებლის 120, ბინა 7",
    "comment": "დარეკეთ მისვლამდე",
}


def main() -> None:
    c = httpx.Client(timeout=30, follow_redirects=True)

    print("\n=== 1. the owner opens the panel ===")
    login = c.post(
        f"{V1}/auth/login", json={"email": "owner@voltbox.ge", "password": "Thunder-Vault-91"}
    )
    check("the CLI-created admin can sign in", login.status_code == 200, str(login.status_code))
    admin_h = {"Authorization": f"Bearer {login.json()['token']}"}
    me = c.get(f"{ADMIN}/me", headers=admin_h)
    check("and the panel recognises them", me.status_code == 200 and me.json()["role"] == "admin")
    check(
        "their Georgian name survived the round trip",
        me.json()["firstName"] == "ნინო",
        me.json().get("firstName"),
    )

    dash = c.get(f"{ADMIN}/dashboard", headers=admin_h)
    check("the dashboard opens on an empty shop", dash.status_code == 200, str(dash.status_code))
    check(
        "and honestly reports nothing sold",
        dash.json()["salesTotal"] in ("0", "0.00") and dash.json()["activeProducts"] == 0,
        f"{dash.json()['salesTotal']} / {dash.json()['activeProducts']}",
    )

    print("\n=== 2. the owner fills the catalogue ===")
    cat = c.post(
        f"{ADMIN}/categories",
        headers=admin_h,
        json={
            "name": "დამტენები",
            "position": 1,
            "filters": [{"key": "brand", "label": "ბრენდი", "type": "checkbox"}],
        },
    )
    check("category created", cat.status_code == 201, str(cat.status_code))
    cat_id, cat_slug = cat.json()["id"], cat.json()["slug"]

    brand = c.post(f"{ADMIN}/brands", headers=admin_h, json={"name": "Anker", "country": "China"})
    check("brand created", brand.status_code == 201, str(brand.status_code))
    brand_id = brand.json()["id"]

    catalogue = [
        ("Anker PowerPort III", "89.00", "129.00", 12),
        ("Anker Nano 20W", "45.50", None, 3),
        ("Anker PowerLine 2m", "25.00", None, 0),
    ]
    products = []
    for name, price, old_price, stock in catalogue:
        body = {
            "name": name,
            "categoryId": cat_id,
            "brandId": brand_id,
            "price": price,
            "oldPrice": old_price,
            "stock": stock,
            "shortDescription": f"{name} — ორიგინალი",
            "description": "სრული აღწერა",
            "specs": {"watt": "20"},
            "isActive": True,
        }
        created = c.post(
            f"{ADMIN}/products",
            headers=admin_h,
            json={k: v for k, v in body.items() if v is not None},
        )
        products.append(created.json())
    check(
        "three products created",
        all(p.get("id") for p in products),
        str([p.get("slug") for p in products]),
    )
    check(
        "the opening stock is in the ledger",
        c.get(f"{ADMIN}/inventory/{products[0]['id']}/movements", headers=admin_h).json()["items"][
            0
        ]["reason"]
        == "initial",
    )

    photo = png()
    up = c.post(
        f"{ADMIN}/products/{products[0]['id']}/images",
        headers=admin_h,
        files={"file": ("anker.png", photo, "image/png")},
    )
    check("a photo uploads", up.status_code == 201, f"{up.status_code} {up.text[:120]}")

    print("\n=== 3. a customer arrives ===")
    listing = c.get(f"{V1}/products?limit=12")
    check("the catalogue is public", listing.status_code == 200, str(listing.status_code))
    check("all three are on sale", listing.json()["total"] == 3, str(listing.json()["total"]))
    check(
        "the sold-out one is marked, not hidden",
        any(item["inStock"] is False for item in listing.json()["items"]),
        str([(i["name"], i["inStock"]) for i in listing.json()["items"]]),
    )

    found = c.get(f"{V1}/search?q=anker")
    check("search finds them", len(found.json()) >= 3, str(len(found.json())))
    georgian = c.get(f"{V1}/products?q=დამტენი&limit=12")
    check("a Georgian query does not error", georgian.status_code == 200, str(georgian.status_code))

    by_category = c.get(f"{V1}/products?category={cat_slug}&limit=12")
    check(
        "the category filter narrows to it",
        by_category.json()["total"] == 3,
        str(by_category.json()["total"]),
    )
    cheap = c.get(f"{V1}/products?category={cat_slug}&price=0-50&limit=12")
    check("a price filter narrows further", cheap.json()["total"] == 2, str(cheap.json()["total"]))
    # An unknown filter key is resolved against the category's filter config and
    # found to be nothing, so it is ignored rather than refused - deliberate, so
    # a link from an older version of the site still opens.
    unknown = c.get(f"{V1}/products?category={cat_slug}&maxPrice=50&limit=12")
    check(
        "an unknown filter is ignored, not an error",
        unknown.status_code == 200,
        str(unknown.status_code),
    )

    detail = c.get(f"{V1}/products/{products[0]['slug']}")
    check("the product page loads", detail.status_code == 200, str(detail.status_code))
    check(
        "with the photo attached",
        len(detail.json()["images"]) == 1,
        str(len(detail.json()["images"])),
    )
    check(
        "and the discount computed",
        detail.json()["discountPercent"] == 31,
        str(detail.json().get("discountPercent")),
    )

    print("\n=== 4. they register and buy ===")
    register = c.post(
        f"{V1}/auth/register",
        json={
            "email": "nino@example.ge",
            "password": "Mountain-River-42",
            "firstName": "ნინო",
            "lastName": "კაპანაძე",
        },
    )
    check(
        "registration works",
        register.status_code == 201,
        f"{register.status_code} {register.text[:100]}",
    )
    shopper_h = {"Authorization": f"Bearer {register.json()['token']}"}

    saved = c.put(
        f"{V1}/cart",
        headers=shopper_h,
        json={"items": [{"productId": products[0]["id"], "qty": 2}]},
    )
    check("the cart is saved to the account", saved.status_code == 200, str(saved.status_code))
    reread = c.get(f"{V1}/cart", headers=shopper_h).json()["items"]
    check(
        "and reads back on another device", len(reread) == 1 and reread[0]["qty"] == 2, str(reread)
    )

    key = "3f1c2b7e-8a4d-4f6e-9c11-2b8e5d7a4c90"
    order_body = {
        "items": [{"productId": products[0]["id"], "qty": 2}],
        "customer": CUSTOMER,
        "paymentMethod": "cash",
    }
    placed = c.post(f"{V1}/orders", json=order_body, headers={**shopper_h, "Idempotency-Key": key})
    check(
        "the order goes through",
        placed.status_code == 201,
        f"{placed.status_code} {placed.text[:160]}",
    )
    order = placed.json()
    number = order["orderNumber"]
    check(
        "priced from the database, not the browser",
        order["totals"]["subtotal"] == "178.00",
        order["totals"]["subtotal"],
    )
    check(
        "free shipping above the threshold",
        order["totals"]["shipping"] == "0.00",
        order["totals"]["shipping"],
    )

    again = c.post(f"{V1}/orders", json=order_body, headers={**shopper_h, "Idempotency-Key": key})
    check(
        "a double submit returns the same order, not a second one",
        again.status_code in (200, 201) and again.json()["orderNumber"] == number,
        f"{again.status_code} {again.json().get('orderNumber')}",
    )

    after = c.get(f"{V1}/products/{products[0]['slug']}")
    check("stock came down by two", after.json()["stock"] == 10, str(after.json()["stock"]))

    # A key of its own: without one the API refuses the checkout before it
    # looks at stock, and this check would be about the header instead.
    greedy = c.post(
        f"{V1}/orders",
        headers={**shopper_h, "Idempotency-Key": "9d2e4c1a-5b7f-4e3a-8c6d-1f0a2b3c4d5e"},
        json={
            "items": [{"productId": products[2]["id"], "qty": 1}],
            "customer": CUSTOMER,
            "paymentMethod": "cash",
        },
    )
    check(
        "the sold-out product cannot be bought",
        greedy.status_code == 409,
        f"{greedy.status_code} {greedy.json()['error'].get('code')}",
    )
    check(
        "and the refusal is in Georgian to the shopper",
        greedy.json()["error"]["code"] == "INSUFFICIENT_STOCK",
    )

    mine = c.get(f"{V1}/orders", headers=shopper_h)
    check("the order is in their account", len(mine.json()) == 1, str(len(mine.json())))

    print("\n=== 5. the shop fulfils it ===")
    olist = c.get(f"{ADMIN}/orders", headers=admin_h)
    row = next((o for o in olist.json()["items"] if o["orderNumber"] == number), None)
    check("the panel shows the order", row is not None)
    if row is None:
        # Everything below needs its id; reading it from None was a TypeError
        # that ended the run without the summary.
        raise SystemExit("The order is not in the panel, so the rest of the journey cannot run.")
    check(
        "with the customer's name",
        row["customerName"] == "ნინო კაპანაძე",
        row["customerName"],
    )
    by_name = c.get(f"{ADMIN}/orders", headers=admin_h, params={"q": "კაპანაძე"})
    check("and finds it by that name", by_name.json()["total"] == 1, str(by_name.json()["total"]))

    order_id = row["id"]
    for step in ("confirmed", "processing", "shipped", "delivered"):
        moved = c.post(f"{ADMIN}/orders/{order_id}/status", headers=admin_h, json={"to": step})
        if not check(f"→ {step}", moved.status_code == 200, str(moved.status_code)):
            break

    seen = c.get(f"{V1}/orders/{number}", headers=shopper_h)
    check(
        "the customer sees it delivered",
        seen.json()["status"] == "delivered",
        seen.json()["status"],
    )

    final = c.get(f"{ADMIN}/dashboard", headers=admin_h)
    check(
        "the dashboard counts the sale",
        final.json()["salesTotal"] == "178.00",
        final.json()["salesTotal"],
    )
    check(
        "and names the best seller",
        final.json()["topProducts"][0]["name"] == "Anker PowerPort III",
        str(final.json()["topProducts"][:1]),
    )

    print("\n=== 6. what only a real server shows ===")
    preflight = c.request(
        "OPTIONS",
        f"{V1}/orders",
        headers={
            "Origin": SHOP,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )
    check(
        "the shop's origin is allowed through CORS",
        preflight.headers.get("access-control-allow-origin") == SHOP,
        preflight.headers.get("access-control-allow-origin"),
    )
    stranger = c.request(
        "OPTIONS",
        f"{V1}/orders",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    check(
        "another origin is not",
        "access-control-allow-origin" not in stranger.headers,
        stranger.headers.get("access-control-allow-origin"),
    )

    plain = c.get(f"{V1}/products?limit=48", headers={"Accept-Encoding": "identity"})
    packed = c.get(f"{V1}/products?limit=48", headers={"Accept-Encoding": "gzip"})
    on_wire = int(packed.headers.get("content-length") or 0)
    uncompressed = int(plain.headers.get("content-length") or len(plain.content))
    check(
        "responses are compressed on the wire",
        packed.headers.get("content-encoding") == "gzip",
        f"{uncompressed / 1024:.1f} KB -> {on_wire / 1024:.1f} KB",
    )

    headers = c.get(f"{V1}/health").headers
    check(
        "security headers are on a real response",
        all(
            h in headers
            for h in ("x-content-type-options", "x-frame-options", "content-security-policy")
        ),
        str(
            [
                h
                for h in ("x-content-type-options", "x-frame-options", "content-security-policy")
                if h not in headers
            ]
        ),
    )
    check("and a request id to quote", "x-request-id" in headers)

    sitemap = c.get(f"{API}/sitemap.xml")
    check("the sitemap is served", sitemap.status_code == 200, str(sitemap.status_code))
    check(
        "and lists the new products",
        all(p["slug"] in sitemap.text for p in products),
        str([p["slug"] for p in products if p["slug"] not in sitemap.text]),
    )
    check("but not the admin", "/admin" not in sitemap.text)

    missing = c.get(f"{V1}/products/no-such-product")
    check(
        "a 404 is the shared envelope",
        missing.status_code == 404 and missing.json()["error"]["code"] == "PRODUCT_NOT_FOUND",
        f"{missing.status_code} {missing.json().get('error', {}).get('code')}",
    )

    refused = [
        c.post(f"{V1}/auth/login", json={"email": "nino@example.ge", "password": "wrong"})
        for _ in range(8)
    ]
    codes = {r.status_code for r in refused}
    check("repeated bad logins are refused, not served", codes <= {401, 429}, str(sorted(codes)))
    check(
        "and the account survives a correct password afterwards or says why",
        c.post(
            f"{V1}/auth/login", json={"email": "nino@example.ge", "password": "Mountain-River-42"}
        ).status_code
        in (200, 401, 429),
    )

    print("\n=== 7. the built site is actually served ===")
    try:
        page = httpx.get(SHOP, timeout=10)
        check("the shop responds", page.status_code == 200, str(page.status_code))
        check(
            "with the configured domain in its share tags",
            f'content="{SHOP}/og-image.png"' in page.text,
            page.text.split('og:image" content="')[1].split('"')[0]
            if 'og:image" content="' in page.text
            else "no og:image at all",
        )
        check("and a canonical link", f'href="{SHOP}/"' in page.text)
        robots = httpx.get(f"{SHOP}/robots.txt", timeout=10)
        check(
            "robots.txt is served",
            robots.status_code == 200 and "Disallow: /admin" in robots.text,
            str(robots.status_code),
        )
        image = httpx.get(f"{SHOP}/og-image.png", timeout=10)
        check(
            "the sharing image is really there",
            image.status_code == 200 and image.headers["content-type"] == "image/png",
            str(image.status_code),
        )
        bundle = page.text.split('src="')[1].split('"')[0]
        asset = httpx.get(f"{SHOP}{bundle}", timeout=20)
        check("the bundle downloads", asset.status_code == 200, str(asset.status_code))
        # The exact base URL the build was given, not just "/api/v1" - that
        # string would be there whatever the bundle was pointed at.
        # The exact base URL the build was given, not just "/api/v1" - that
        # string would be there whatever the bundle was pointed at. localhost
        # rather than 127.0.0.1 because that is what the build was handed.
        wanted = "http://localhost:8100/api/v1"
        check(
            "and talks to this API",
            wanted in asset.text,
            f"{wanted} in {len(asset.text) // 1024} KB of bundle",
        )
    except httpx.HTTPError as exc:
        check("the shop responds", False, str(exc))

    print("\n=== 8. what the database is left holding ===")
    # The strongest statement available about a shop: the stock column and the
    # ledger that explains it cannot have drifted apart. Everything else here is
    # a story about one order; this is an invariant over all of them.
    import subprocess

    query = (
        "select bool_and(p.stock = coalesce(s.total, 0)) from products p "
        "left join (select product_id, sum(change) total from inventory_movements "
        "group by product_id) s on s.product_id = p.id"
    )
    agrees = subprocess.run(  # noqa: S603
        [DOCKER, "exec", "voltbox-pg", "psql", "-U", "voltbox", "-d", "voltbox_e2e", "-tAc", query],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    check("every product's stock equals the sum of its ledger", agrees == "t", agrees)

    orphans = subprocess.run(  # noqa: S603
        [
            DOCKER,
            "exec",
            "voltbox-pg",
            "psql",
            "-U",
            "voltbox",
            "-d",
            "voltbox_e2e",
            "-tAc",
            "select count(*) from orders o where not exists "
            "(select 1 from order_items i where i.order_id = o.id)",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    check("no order was left without its items", orphans == "0", orphans)

    c.close()
    failed = [label for label, ok in results if not ok]
    print(f"\n==== {len(results) - len(failed)}/{len(results)} passed ====")
    for label in failed:
        print("  FAILED:", label)
    # A failed check used to end the run with exit code 0, which only someone
    # reading the summary would notice. The nightly workflow reads the code.
    if failed:
        raise SystemExit(1)


main()
