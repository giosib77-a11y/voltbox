"""Phase 4 — ავტორიზაციის ტესტები."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from app.core.config import settings
from app.core.security import decode_access_token
from app.db.models import RefreshToken, User
from app.db.session import get_db
from app.main import app
from httpx import ASGITransport
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


async def _families(db: AsyncSession, email: str) -> list[tuple[str, bool]]:
    """(family, is_revoked) for every refresh token of one account."""
    rows = (
        await db.execute(
            select(RefreshToken.family_id, RefreshToken.revoked_at)
            .join(User, User.id == RefreshToken.user_id)
            .where(User.email == email)
            .order_by(RefreshToken.created_at)
        )
    ).all()
    return [(str(r.family_id), r.revoked_at is not None) for r in rows]


async def test_a_replayed_token_ends_the_session_it_belonged_to(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """Rotation makes theft visible; this is the part that acts on it.

    A token that has been exchanged can never legitimately come back, so a
    second appearance means two copies exist. Answering 401 and leaving the
    thief's freshly rotated token working - which is what happened before -
    detects the theft and then ignores it.
    """
    await _register(client)
    stolen = client.cookies.get(COOKIE)

    # The real client rotates normally and carries on.
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200
    live = client.cookies.get(COOKIE)

    # Outside the retry grace window, the replay is theft.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.revoked_at.is_not(None))
        .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    await db.flush()

    replay = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={stolen}"})

    assert replay.status_code == 401
    # And the token the thief would have rotated into is dead too.
    after = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={live}"})
    assert after.status_code == 401

    assert all(revoked for _, revoked in await _families(db, "nino@example.ge"))


async def test_a_lost_response_is_a_retry_and_not_a_theft(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """The false positive worth avoiding.

    When a refresh succeeds but its reply never arrives, the browser still
    holds the token it spent - the Set-Cookie was in the lost reply - and its
    next attempt looks exactly like a replay. Ending the session over a dropped
    packet would be worse than the attack.
    """
    await _register(client)
    spent = client.cookies.get(COOKIE)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 200
    live = client.cookies.get(COOKIE)

    # Immediately, i.e. inside REUSE_GRACE.
    replay = await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={spent}"})

    assert replay.status_code == 401
    # The session survives: the client can still refresh with what it has.
    assert (
        await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={live}"})
    ).status_code == 200


async def test_one_devices_theft_does_not_sign_out_the_others(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """Families exist for this: the victim keeps the sessions that were safe."""
    await _register(client)
    phone = client.cookies.get(COOKIE)

    # A second login is a second family - another device.
    laptop_login = await client.post(
        "/api/v1/auth/login", json={"email": "nino@example.ge", "password": "supersecret1"}
    )
    laptop = laptop_login.cookies.get(COOKIE)

    # The phone's token is rotated, then the old one is replayed later.
    await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={phone}"})
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.revoked_at.is_not(None))
        .values(revoked_at=datetime.now(UTC) - timedelta(minutes=5))
    )
    await db.flush()
    await client.post("/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={phone}"})

    # The laptop was never in danger.
    still_valid = await client.post(
        "/api/v1/auth/refresh", headers={"Cookie": f"{COOKIE}={laptop}"}
    )
    assert still_valid.status_code == 200


async def test_rotation_keeps_a_session_in_one_family(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await _register(client)
    for _ in range(3):
        assert (await client.post("/api/v1/auth/refresh")).status_code == 200

    families = {family for family, _ in await _families(db, "nino@example.ge")}
    assert len(families) == 1


# ── expiry ───────────────────────────────────────────────────────────────────
#
# Both tokens carry a lifetime and both must actually stop working when it runs
# out. The access token's expiry is PyJWT's job; the refresh token's is a
# condition in our own UPDATE, and nothing was proving it.


async def test_an_expired_access_token_is_refused(client: httpx.AsyncClient) -> None:
    """Minted in the past rather than waited for, so the test stays fast."""

    await _register(client)
    user_id = (await _register(client, email="expired@example.ge")).json()["user"]["id"]

    past = datetime.now(UTC) - timedelta(hours=1)
    expired = jwt.encode(
        {
            "sub": user_id,
            "iat": int((past - timedelta(minutes=30)).timestamp()),
            "exp": int(past.timestamp()),
            "jti": "0" * 32,
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    # The signature is genuine; only the clock has moved.
    assert decode_access_token(expired) is None

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"


async def test_a_token_signed_with_another_key_is_refused(client: httpx.AsyncClient) -> None:
    """A valid-looking token is only valid if we signed it."""

    user_id = (await _register(client)).json()["user"]["id"]
    forged = jwt.encode(
        {
            "sub": user_id,
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "type": "access",
        },
        "not-the-secret-this-server-uses-at-all",
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


async def test_a_refresh_token_past_its_expiry_is_refused(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """The row is still there and not revoked - only out of date.

    Rotation and reuse detection both key on `revoked_at`, so an expired but
    unspent token would sail through if the date were not also checked.
    """
    await _register(client)
    assert client.cookies.get(COOKIE)

    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.revoked_at.is_(None))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db.commit()

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"


async def test_an_expired_refresh_token_is_not_treated_as_theft(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """Expiry is the ordinary end of a session, not an attack.

    Reuse detection revokes the whole family. Letting a token that simply timed
    out land there would end every other session the person has for no reason.
    """
    await _register(client)

    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.revoked_at.is_(None))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await db.commit()

    await client.post("/api/v1/auth/refresh")

    rows = (await db.scalars(select(RefreshToken))).all()
    # Still unrevoked: nothing was spent, so nothing looks like a replay.
    assert [row.revoked_at for row in rows] == [None]


# ── access tokens can be revoked after all ───────────────────────────────────
#
# An access token is a signed statement with a thirty minute life and no way to
# take it back. Revoking the refresh tokens stops a session being extended and
# does nothing about the access token already handed out - so changing a stolen
# password left the thief signed in for the rest of that half hour, at the one
# moment the owner is certain something is wrong.


async def test_changing_the_password_kills_the_access_token_too(
    client: httpx.AsyncClient,
) -> None:
    stolen = await _auth_header(client)
    assert (await client.get("/api/v1/auth/me", headers=stolen)).status_code == 200

    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=stolen,
        json={"currentPassword": REGISTRATION["password"], "newPassword": "brandnewpass9"},
    )
    assert changed.status_code == 200

    after = await client.get("/api/v1/auth/me", headers=stolen)

    assert after.status_code == 401
    assert after.json()["error"]["code"] == "INVALID_TOKEN"


async def test_the_owner_can_carry_on_immediately(client: httpx.AsyncClient) -> None:
    """The line must not catch the session being handed out to replace them."""
    header = await _auth_header(client)
    await client.post(
        "/api/v1/auth/change-password",
        headers=header,
        json={"currentPassword": REGISTRATION["password"], "newPassword": "brandnewpass9"},
    )

    signed_in = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": "brandnewpass9"},
    )
    fresh = {"Authorization": f"Bearer {signed_in.json()['token']}"}

    assert signed_in.status_code == 200
    assert (await client.get("/api/v1/auth/me", headers=fresh)).status_code == 200


async def test_one_accounts_revocation_leaves_another_alone(
    client: httpx.AsyncClient,
) -> None:
    """The line is per account, so it must not reach across to someone else."""
    mine = await _auth_header(client)
    other = (await _register(client, email="other@example.ge")).json()["token"]
    others_header = {"Authorization": f"Bearer {other}"}

    await client.post(
        "/api/v1/auth/change-password",
        headers=mine,
        json={"currentPassword": REGISTRATION["password"], "newPassword": "brandnewpass9"},
    )

    assert (await client.get("/api/v1/auth/me", headers=mine)).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers=others_header)).status_code == 200


async def test_a_token_without_a_version_is_refused(client: httpx.AsyncClient) -> None:
    """Every token this application mints carries `tv`.

    One that does not was either minted before the version existed or not by
    us. Neither is a reason to honour it, and the first is the reason the
    migration signs everyone out once.
    """
    user_id = (await _register(client)).json()["user"]["id"]
    versionless = jwt.encode(
        {
            "sub": user_id,
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "type": "access",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {versionless}"}
    )

    assert response.status_code == 401


async def test_an_ordinary_logout_does_not_sign_out_the_other_devices(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """Logging out here revokes this refresh token, not every access token.

    The line moves for a password change, which means "something is wrong,
    end everything". A logout means "I am done on this device", and pushing
    the line there would sign the person out of their phone as well.
    """
    header = await _auth_header(client)

    await client.post("/api/v1/auth/logout")

    assert (await client.get("/api/v1/auth/me", headers=header)).status_code == 200


# ── brute force, counted on the account ──────────────────────────────────────
#
# The limiter in front of /auth/login counts per IP, and a rented proxy list is
# a thousand times that allowance against one email. The account is the one
# thing every attempt against it has in common.


@pytest.fixture
async def realistic_client(db: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """A client whose requests each get their own session, and roll back on error.

    The shared-session client every other test uses cannot see this class of
    bug. Its `get_db` override hands the same session to every request and never
    rolls back, so a failed attempt keeps its changes and a missing commit looks
    like a working one. Production opens a session per request and discards it
    on an exception, which is exactly what has to be true for a failed sign-in
    to still be counted.
    """
    connection = await db.connection()
    factory = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def _fail_login(client: httpx.AsyncClient, times: int) -> httpx.Response:
    response = None
    for _ in range(times):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": REGISTRATION["email"], "password": "definitely-not-it"},
        )
    assert response is not None
    return response


async def test_enough_wrong_passwords_lock_the_account(
    realistic_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    client = realistic_client
    await _register(client)

    await _fail_login(client, settings.max_failed_logins)

    # Read back from the row, not from the instance this session is holding.
    # A failed request is rolled back by `get_db`, so the count only survives
    # if the route commits it - and the in-memory object would keep the
    # increment either way, which would make this test pass without the fix.
    user = await db.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    await db.refresh(user)
    assert user.locked_until is not None, "the failed attempts were not recorded"

    # Even the right password is refused now, and the answer says why.
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    assert response.status_code == 401
    body = response.json()["error"]
    assert body["code"] == "TOO_MANY_LOGIN_ATTEMPTS"
    assert body["details"]["retryAfterSeconds"] > 0


async def test_the_lock_needs_the_whole_threshold(
    realistic_client: httpx.AsyncClient, db: AsyncSession
) -> None:
    """One short, and signing in still works - a typo must not cost the account."""
    client = realistic_client
    await _register(client)

    await _fail_login(client, settings.max_failed_logins - 1)

    user = await db.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    await db.refresh(user)
    # The attempts were counted; they simply have not added up yet.
    assert user.failed_login_count == settings.max_failed_logins - 1
    assert user.locked_until is None

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    assert response.status_code == 200


async def test_signing_in_wipes_the_count(client: httpx.AsyncClient, db: AsyncSession) -> None:
    """Getting in proves the earlier attempts were the same person forgetting."""
    await _register(client)
    await _fail_login(client, settings.max_failed_logins - 1)

    await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    user = await db.scalar(select(User).where(User.email == REGISTRATION["email"]))
    assert user is not None
    await db.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is None


async def test_a_lock_that_has_expired_lets_them_back_in(
    client: httpx.AsyncClient, db: AsyncSession
) -> None:
    await _register(client)
    await _fail_login(client, settings.max_failed_logins)

    # Wind the clock forward rather than waiting fifteen minutes.
    await db.execute(
        update(User)
        .where(User.email == REGISTRATION["email"])
        .values(locked_until=datetime.now(UTC) - timedelta(seconds=1))
        .execution_options(synchronize_session="fetch")
    )
    await db.commit()

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )

    assert response.status_code == 200


async def test_locking_one_account_does_not_touch_another(client: httpx.AsyncClient) -> None:
    await _register(client)
    await _register(client, email="untouched@example.ge")

    await _fail_login(client, settings.max_failed_logins)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "untouched@example.ge", "password": REGISTRATION["password"]},
    )

    assert response.status_code == 200


async def test_an_unknown_email_still_answers_the_same_way(client: httpx.AsyncClient) -> None:
    """No account, nothing to count - and nothing new to learn from the reply."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody-at-all@example.ge", "password": "whatever-here"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
