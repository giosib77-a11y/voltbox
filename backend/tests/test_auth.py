"""Phase 4 — ავტორიზაციის ტესტები."""

import httpx
import pytest

REGISTRATION = {
    "firstName": "ნინო",
    "lastName": "კაპანაძე",
    "email": "nino@example.ge",
    "password": "supersecret1",
}


async def _register(client: httpx.AsyncClient, **overrides: object) -> httpx.Response:
    return await client.post("/api/v1/auth/register", json={**REGISTRATION, **overrides})


async def _auth_header(client: httpx.AsyncClient) -> dict[str, str]:
    token = (await _register(client)).json()["token"]
    return {"Authorization": f"Bearer {token}"}


#: The httpOnly cookie the refresh token travels in.
COOKIE = "voltbox_refresh"


async def test_registration_returns_a_session(client: httpx.AsyncClient) -> None:
    response = await _register(client)

    assert response.status_code == 201
    body = response.json()
    # The refresh token is not in the body: it is set as an httpOnly cookie, so
    # script on the page can use the session but cannot copy it out.
    assert set(body) == {"user", "token", "expiresAt"}
    assert "refreshToken" not in response.text
    assert client.cookies.get(COOKIE)
    assert body["user"]["email"] == "nino@example.ge"
    assert "passwordHash" not in body["user"]


async def test_duplicate_email_is_a_conflict(client: httpx.AsyncClient) -> None:
    await _register(client)
    response = await _register(client)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


async def test_email_uniqueness_ignores_case(client: httpx.AsyncClient) -> None:
    await _register(client)
    response = await _register(client, email="NINO@Example.GE")

    assert response.status_code == 409


@pytest.mark.parametrize("password", ["short1", "password", "12345678"])
async def test_weak_passwords_are_rejected(client: httpx.AsyncClient, password: str) -> None:
    response = await _register(client, password=password)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_login_returns_a_session(client: httpx.AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nino@example.ge", "password": "supersecret1"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["firstName"] == "ნინო"


@pytest.mark.parametrize(
    ("email", "password"),
    [("nino@example.ge", "wrong-password"), ("ghost@example.ge", "supersecret1")],
)
async def test_login_failures_are_indistinguishable(
    client: httpx.AsyncClient, email: str, password: str
) -> None:
    """უცნობი ელ. ფოსტისა და არასწორი პაროლის გარჩევა ბაზის აღრიცხვას მისცემდა
    საშუალებას — პასუხი ორივე შემთხვევაში ერთია."""
    await _register(client)

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.json()["error"]["message"] == "Invalid email or password"


async def test_me_requires_a_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_me_rejects_a_malformed_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer nonsense"})

    assert response.status_code == 401


async def test_me_returns_the_current_user(client: httpx.AsyncClient) -> None:
    headers = await _auth_header(client)

    response = await client.get("/api/v1/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "nino@example.ge"


async def test_profile_update_persists(client: httpx.AsyncClient) -> None:
    headers = await _auth_header(client)

    response = await client.patch(
        "/api/v1/auth/me", headers=headers, json={"firstName": "მარიამ", "phone": "555123456"}
    )

    assert response.status_code == 200
    assert response.json()["firstName"] == "მარიამ"
    assert response.json()["phone"] == "555123456"
    assert response.json()["lastName"] == "კაპანაძე"  # უცვლელი ველი არ იკარგება


async def test_profile_email_change_detects_a_conflict(client: httpx.AsyncClient) -> None:
    await _register(client, email="taken@example.ge")
    headers = await _auth_header(client)

    response = await client.patch(
        "/api/v1/auth/me", headers=headers, json={"email": "taken@example.ge"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


async def test_refresh_rotates_the_token(client: httpx.AsyncClient) -> None:
    await _register(client)
    issued = client.cookies.get(COOKIE)

    first = await client.post("/api/v1/auth/refresh")

    assert first.status_code == 200
    assert client.cookies.get(COOKIE) != issued
    # Still not in the body, on this path either.
    assert "refreshToken" not in first.text


async def test_a_used_refresh_token_cannot_be_replayed(client: httpx.AsyncClient) -> None:
    """rotation-on-use: მოპარული ტოკენი მეორედ აღარ მუშაობს."""
    await _register(client)
    stolen = client.cookies.get(COOKIE)
    await client.post("/api/v1/auth/refresh")

    replay = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={stolen}"})

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_logout_revokes_the_refresh_token(client: httpx.AsyncClient) -> None:
    """გასვლა კლიენტის მხარეს წაშლა არ არის — სერვერზეც უნდა გაუქმდეს."""
    await _register(client)
    issued = client.cookies.get(COOKIE)

    logout = await client.post("/api/v1/auth/logout")
    # Presenting the old value directly: revoked in the database, not merely
    # forgotten by the browser.
    reuse = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={issued}"})

    assert logout.status_code == 200
    assert reuse.status_code == 401
    # And the browser is told to drop it, with the Path it was set on - a
    # mismatch there leaves the cookie in place and the logout half-done.
    assert client.cookies.get(COOKIE) is None
    assert f"{COOKIE}=" in logout.headers["set-cookie"]
    assert "Path=/api/v1/auth" in logout.headers["set-cookie"]


async def test_logout_without_a_token_is_idempotent(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout", json={})

    assert response.status_code == 200


async def test_password_change_requires_the_current_password(
    client: httpx.AsyncClient,
) -> None:
    headers = await _auth_header(client)

    response = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"currentPassword": "wrong-one", "newPassword": "brandnewpass9"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURRENT_PASSWORD"
    assert response.json()["error"]["details"][0]["field"] == "currentPassword"


async def test_password_change_invalidates_existing_sessions(
    client: httpx.AsyncClient,
) -> None:
    session = (await _register(client)).json()
    headers = {"Authorization": f"Bearer {session['token']}"}

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"currentPassword": "supersecret1", "newPassword": "brandnewpass9"},
    )
    reuse = await client.post("/api/v1/auth/refresh")
    relogin = await client.post(
        "/api/v1/auth/login", json={"email": "nino@example.ge", "password": "brandnewpass9"}
    )

    assert changed.status_code == 200
    assert reuse.status_code == 401  # ძველი სესიები უქმდება
    assert relogin.status_code == 200


async def test_unknown_field_in_the_body_is_rejected(client: httpx.AsyncClient) -> None:
    """კონტრაქტის რეგრესია ხმაურით უნდა გამოჩნდეს და არა ჩუმად იგნორირდეს."""
    response = await _register(client, role="admin")

    assert response.status_code == 400


async def test_the_refresh_cookie_is_out_of_reach_of_javascript(
    client: httpx.AsyncClient,
) -> None:
    """The whole point of the change, asserted on the attributes themselves.

    HttpOnly is what stops an XSS copying the token out; Path keeps it off
    every other request; SameSite keeps another site from causing one.
    """
    response = await _register(client)

    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Path=/api/v1/auth" in cookie
    assert "SameSite=strict" in cookie.replace("samesite", "SameSite")
    assert "Max-Age=" in cookie


async def test_refresh_no_longer_accepts_a_token_in_the_body(
    client: httpx.AsyncClient,
) -> None:
    """The old way out has to be gone, not merely unused.

    Leaving it would mean the cookie protects nothing: script could read a
    token from anywhere it could still find one and post it.
    """
    await _register(client)
    stolen = client.cookies.get(COOKIE)
    client.cookies.clear()

    response = await client.post("/api/v1/auth/refresh", json={"refreshToken": stolen})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_refresh_without_a_cookie_is_the_same_401_as_a_bad_one(
    client: httpx.AsyncClient,
) -> None:
    missing = await client.post("/api/v1/auth/refresh")
    bad = await client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}=not-a-real-token"}
    )

    assert missing.status_code == bad.status_code == 401
    assert missing.json() == bad.json()
