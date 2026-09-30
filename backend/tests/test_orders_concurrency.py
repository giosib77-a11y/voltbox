"""Phase 6 — რბოლის პირობები.

ეს ტესტები საერთო ტრანზაქციულ `db` fixture-ს *არ* იყენებენ: overselling მხოლოდ
რეალურ, ერთმანეთისგან დამოუკიდებელ კავშირებზე ჩანს. ამიტომ აქ ცალკე სესიები
იქმნება და მონაცემები ბოლოს ხელით იწმინდება.
"""

import asyncio
import uuid
from collections import Counter
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.config import settings
from app.core.errors import ConflictError, UnauthorizedError
from app.db.models import (
    REASON_ORDER_CANCELLED,
    Brand,
    Category,
    InventoryMovement,
    Order,
    OrderItem,
    PasswordResetToken,
    Product,
    ProductImage,
    RefreshToken,
    User,
)
from app.db.session import SessionLocal
from app.services import auth as auth_service
from app.services import order as order_service
from sqlalchemy import Row, delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_user

CUSTOMER = {
    "first_name": "გიორგი",
    "last_name": "ბერიძე",
    "phone": "555123456",
    "city": "თბილისი",
    "address": "ჭავჭავაძის გამზირი 42",
}


@pytest.fixture
async def last_unit() -> AsyncGenerator[Product]:
    """ერთი პროდუქტი, მარაგში ზუსტად 1 ცალით — ცალკე კავშირზე დაწერილი."""
    async with SessionLocal() as setup:
        category = Category(slug="race", name="race", filters=[])
        brand = Brand(slug="race-brand", name="RaceBrand")
        setup.add_all([category, brand])
        await setup.flush()
        product = Product(
            slug="the-last-one",
            name="The Last One",
            category_id=category.id,
            brand_id=brand.id,
            price=Decimal("50.00"),
            stock=1,
        )
        setup.add(product)
        await setup.flush()
        setup.add(ProductImage(product_id=product.id, url="/a.svg", is_primary=True))
        await setup.commit()
        product_id = product.id

    async with SessionLocal() as session:
        loaded = await session.scalar(select(Product).where(Product.id == product_id))
        assert loaded is not None
        yield loaded

    async with SessionLocal() as cleanup:
        await cleanup.execute(delete(OrderItem).where(OrderItem.product_id == product_id))
        await cleanup.execute(
            delete(Order).where(
                Order.id.in_(select(OrderItem.order_id).where(OrderItem.product_id == product_id))
            )
        )
        await cleanup.execute(delete(Order).where(Order.customer["city"].astext == "თბილისი"))
        await cleanup.execute(delete(ProductImage).where(ProductImage.product_id == product_id))
        await cleanup.execute(delete(Product).where(Product.id == product_id))
        await cleanup.execute(delete(Category).where(Category.slug == "race"))
        await cleanup.execute(delete(Brand).where(Brand.slug == "race-brand"))
        await cleanup.commit()


async def _try_order(product_id: object) -> str:
    """ერთი შეკვეთა საკუთარ კავშირზე. → "ok" ან "conflict"."""
    async with SessionLocal() as session:
        try:
            await order_service.create_order(
                session,
                items=[(product_id, 1)],  # type: ignore[list-item]
                customer=dict(CUSTOMER),
                payment_method="cash",
                user=None,
            )
            await session.commit()
        except ConflictError:
            await session.rollback()
            return "conflict"
        return "ok"


async def test_two_parallel_orders_for_the_last_unit(last_unit: Product) -> None:
    """ერთი უნდა გაიაროს, მეორემ 409 უნდა დააბრუნოს — მარაგი ვერ გახდება უარყოფითი."""
    results = await asyncio.gather(_try_order(last_unit.id), _try_order(last_unit.id))

    assert sorted(results) == ["conflict", "ok"]

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
    assert stock == 0


async def test_order_numbers_are_unique_under_concurrency(last_unit: Product) -> None:
    """ნომერი sequence-იდან მოდის — random()+retry დუბლიკატს დაუშვებდა."""
    async with SessionLocal() as session:
        numbers = {await order_service._next_order_number(session) for _ in range(50)}

    assert len(numbers) == 50


async def test_cancellation_restores_stock(last_unit: Product, db: AsyncSession) -> None:
    async with SessionLocal() as session:
        order = await order_service.create_order(
            session,
            items=[(last_unit.id, 1)],
            customer=dict(CUSTOMER),
            payment_method="cash",
            user=None,
        )
        await session.commit()
        order_id = order.id

    async with SessionLocal() as session:
        stored = await session.scalar(select(Order).where(Order.id == order_id))
        assert stored is not None
        await order_service.cancel(session, stored)
        await session.commit()

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
    assert stock == 1


async def _order_with_key(product_id: object, key: str, *, qty: int = 1) -> tuple[str, str]:
    """One checkout on its own connection. → (outcome, detail).

    Outcomes: ("ok", order_number) for a created or replayed order,
    ("conflict", code) for a refusal, ("error", type) for anything else - which
    is the case that used to happen and must not any more.
    """
    async with SessionLocal() as session:
        try:
            order = await order_service.create_order(
                session,
                items=[(product_id, qty)],  # type: ignore[list-item]
                customer=dict(CUSTOMER),
                payment_method="cash",
                user=None,
                idempotency_key=key,
            )
            number = order.order_number
            await session.commit()
        except ConflictError as exc:
            await session.rollback()
            return "conflict", exc.code
        except Exception as exc:
            # Deliberately broad, and it hides nothing: the caller asserts
            # that no outcome is "error", so anything caught here fails the
            # test by name instead of being swallowed.
            await session.rollback()
            return "error", type(exc).__name__
        return "ok", number


async def test_parallel_duplicates_of_one_key_make_one_order(last_unit: Product) -> None:
    """Five simultaneous submissions of the same checkout.

    Before the key was claimed up front, the losers of this race died on the
    unique index and the shopper saw a 500 for an order that had in fact gone
    through.
    """
    key = str(uuid.uuid4())
    results = await asyncio.gather(*(_order_with_key(last_unit.id, key) for _ in range(5)))

    outcomes = {outcome for outcome, _ in results}
    assert outcomes == {"ok"}, results

    numbers = {detail for _, detail in results}
    assert len(numbers) == 1, f"expected one order, got {numbers}"

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
        orders = await check.scalar(
            select(func.count()).select_from(Order).where(Order.idempotency_key == key)
        )
    # Charged exactly once, out of a stock of one.
    assert stock == 0
    assert orders == 1


async def test_the_last_unit_does_not_turn_a_duplicate_into_out_of_stock(
    last_unit: Product,
) -> None:
    """Two duplicates competing for the only unit both get the order.

    This is why the claim has to come before the stock check: the duplicate
    would otherwise reach the check while the original was still uncommitted,
    find nothing left, and tell the shopper the item sold out - to them, in
    between two clicks of their own.
    """
    key = str(uuid.uuid4())
    first, second = await asyncio.gather(
        _order_with_key(last_unit.id, key), _order_with_key(last_unit.id, key)
    )

    assert first[0] == "ok" and second[0] == "ok", (first, second)
    assert first[1] == second[1]


async def test_two_different_keys_still_compete_for_the_last_unit(last_unit: Product) -> None:
    """Idempotency must not become a way around the stock check.

    Two genuinely different checkouts are still two orders, and only one of
    them can have the last unit.
    """
    results = await asyncio.gather(
        _order_with_key(last_unit.id, str(uuid.uuid4())),
        _order_with_key(last_unit.id, str(uuid.uuid4())),
    )

    assert sorted(outcome for outcome, _ in results) == ["conflict", "ok"]
    conflicts = [detail for outcome, detail in results if outcome == "conflict"]
    assert conflicts == ["INSUFFICIENT_STOCK"]


async def _cancel(order_id: object) -> tuple[str, str]:
    """One cancellation on its own connection. → (outcome, detail)."""
    async with SessionLocal() as session:
        stored = await session.scalar(select(Order).where(Order.id == order_id))
        assert stored is not None
        try:
            await order_service.cancel(session, stored)
            await session.commit()
        except ConflictError as exc:
            await session.rollback()
            return "conflict", exc.code
        except Exception as exc:
            # Broad on purpose and hiding nothing: the caller asserts on the
            # outcomes, so anything caught here fails the test by name.
            await session.rollback()
            return "error", type(exc).__name__
        return "ok", "cancelled"


async def test_two_parallel_cancellations_restock_exactly_once(last_unit: Product) -> None:
    """Both readers used to see `pending` and both returned the stock.

    The item was ordered out of a stock of one, so a double restock is visible
    immediately: stock becomes 2 for a product only ever stocked with 1.
    """
    async with SessionLocal() as session:
        order = await order_service.create_order(
            session,
            items=[(last_unit.id, 1)],
            customer=dict(CUSTOMER),
            payment_method="cash",
            user=None,
        )
        await session.commit()
        order_id = order.id

    results = await asyncio.gather(_cancel(order_id), _cancel(order_id))

    assert sorted(outcome for outcome, _ in results) == ["conflict", "ok"], results
    refusals = [detail for outcome, detail in results if outcome == "conflict"]
    assert refusals == ["ORDER_NOT_CANCELLABLE"]

    async with SessionLocal() as check:
        stock = await check.scalar(select(Product.stock).where(Product.id == last_unit.id))
        movements = await check.scalar(
            select(func.count())
            .select_from(InventoryMovement)
            .where(
                InventoryMovement.order_id == order_id,
                InventoryMovement.reason == REASON_ORDER_CANCELLED,
            )
        )
    assert stock == 1, "the single unit came back once, not twice"
    assert movements == 1


async def _refresh(raw_token: str) -> tuple[str, str]:
    """One refresh on its own connection. → (outcome, detail)."""
    async with SessionLocal() as session:
        try:
            issued = await auth_service.refresh(session, raw_token=raw_token)
            await session.commit()
        except UnauthorizedError as exc:
            await session.rollback()
            return "rejected", exc.code
        except Exception as exc:
            # Broad on purpose and hiding nothing: the caller asserts on the
            # outcomes, so anything caught here fails the test by name.
            await session.rollback()
            return "error", type(exc).__name__
        return "ok", str(issued["refresh_token"])


async def test_one_refresh_token_can_only_be_spent_once(db: AsyncSession) -> None:
    """Two tabs restoring at the same moment used to get a session each.

    Rotation-on-use is what detects a stolen refresh token: a token that has
    already been spent must never work again. A read-then-update left a window
    where both callers saw `revoked_at IS NULL`, so the guarantee was only
    true when nothing happened in parallel.
    """
    async with SessionLocal() as setup:
        user = await make_user(setup, email="race@voltbox.ge")
        session = await auth_service._issue_session(setup, user)
        await setup.commit()
        raw_token = str(session["refresh_token"])

    results = await asyncio.gather(_refresh(raw_token), _refresh(raw_token))

    outcomes = sorted(outcome for outcome, _ in results)
    assert outcomes == ["ok", "rejected"], results
    assert [d for o, d in results if o == "rejected"] == ["INVALID_REFRESH_TOKEN"]

    async with SessionLocal() as check:
        spent = await check.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(
                RefreshToken.user_id == user.id,
                RefreshToken.revoked_at.is_not(None),
            )
        )
        await check.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        await check.execute(delete(User).where(User.id == user.id))
        await check.commit()

    # Exactly the one that was presented; the winner's new token is untouched.
    assert spent == 1


PASSWORD = "supersecret1"
WRONG = "not-the-password"


@pytest.fixture
async def lockable() -> AsyncGenerator[User]:
    """An account to guess at, written on its own connection."""
    async with SessionLocal() as setup:
        user = await make_user(setup, email="guessed@voltbox.ge", password=PASSWORD)
        await setup.commit()

    yield user

    async with SessionLocal() as cleanup:
        await cleanup.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
        await cleanup.execute(
            delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        await cleanup.execute(delete(User).where(User.id == user.id))
        await cleanup.commit()


async def _login(email: str, password: str) -> tuple[str, str]:
    """One sign-in on its own connection, committed as the route commits it."""
    async with SessionLocal() as session:
        try:
            await auth_service.login(session, email=email, password=password)
        except UnauthorizedError as exc:
            # The route commits a refusal too: the count has to outlive it.
            await session.commit()
            return "rejected", exc.code
        except Exception as exc:
            # Broad on purpose and hiding nothing: the caller asserts on the
            # outcomes, so anything caught here fails the test by name.
            await session.rollback()
            return "error", type(exc).__name__
        await session.commit()
        return "ok", "signed in"


async def _reset(raw_token: str) -> tuple[str, str]:
    """One password reset on its own connection."""
    async with SessionLocal() as session:
        try:
            await auth_service.reset_password(
                session, raw_token=raw_token, new_password="a-brand-new-one-1"
            )
            await session.commit()
        except Exception as exc:
            # Broad on purpose, as in _login.
            await session.rollback()
            return "error", type(exc).__name__
        return "ok", "reset"


async def _set_failures(user: User, count: int, *, locked_until: datetime | None = None) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(User)
            .where(User.id == user.id)
            .values(failed_login_count=count, locked_until=locked_until)
        )
        await session.commit()


async def _lock_state(user: User) -> Row[tuple[int, datetime | None]]:
    async with SessionLocal() as check:
        return (
            await check.execute(
                select(User.failed_login_count, User.locked_until).where(User.id == user.id)
            )
        ).one()


async def _until_queued_behind(holder: AsyncSession) -> None:
    """Return once another connection waits on a lock `holder`'s transaction holds.

    The interleaving the tests below are about: the other attempt has read the
    row and hashed, and its write is queued behind this one. Committing any
    earlier would let it read the result, and the test would prove nothing.
    """
    pid = await holder.scalar(text("SELECT pg_backend_pid()"))
    async with SessionLocal() as probe:
        for _ in range(500):
            if await probe.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_locks"
                    " WHERE NOT granted AND :holder = ANY(pg_blocking_pids(pid)))"
                ),
                {"holder": pid},
            ):
                return
            await asyncio.sleep(0.01)
    raise AssertionError("nothing ever queued behind the held row")


async def test_a_burst_of_wrong_passwords_locks_the_account(lockable: User) -> None:
    """More guesses than the threshold, all at once, each on its own connection.

    The count was read into Python, raised by one and written back, so every
    guess of a burst read the same count and wrote the same count plus one:
    the burst moved it by one. Parallel guesses from many addresses are what
    the count exists for, and that was the case in which the lock never came.
    """
    burst = settings.max_failed_logins + 5

    results = await asyncio.gather(*(_login(lockable.email, WRONG) for _ in range(burst)))

    state = await _lock_state(lockable)
    assert state.locked_until is not None, f"not locked after {burst} parallel guesses"
    assert state.locked_until > datetime.now(UTC)
    # Exactly the threshold's worth were judged. Every guess that reached its
    # answer after the lock was refused as locked, whatever it guessed, and
    # was not counted towards the next lock.
    assert Counter(results) == {
        ("rejected", "INVALID_CREDENTIALS"): settings.max_failed_logins,
        ("rejected", "TOO_MANY_LOGIN_ATTEMPTS"): burst - settings.max_failed_logins,
    }
    assert state.failed_login_count == 0


async def test_the_right_password_in_flight_does_not_undo_a_lock(lockable: User) -> None:
    """A guess reaches the threshold while the owner's sign-in is hashing.

    The sign-in had read the row before the lock and wiped it from that read,
    so the account came out unlocked and the count that locked it was gone.

    The account was locked once before and the lock has lapsed: the timestamp
    stays until someone signs in, and it is the state in which that wipe
    reached `locked_until` - from None, the ORM would not have written it.
    """
    await _set_failures(
        lockable,
        settings.max_failed_logins - 1,
        locked_until=datetime.now(UTC) - timedelta(minutes=1),
    )

    async with SessionLocal() as guess:
        # The guess that reaches the threshold: its lock written, not committed.
        with pytest.raises(UnauthorizedError):
            await auth_service.login(guess, email=lockable.email, password=WRONG)
        owner = asyncio.create_task(_login(lockable.email, PASSWORD))
        await _until_queued_behind(guess)
        await guess.commit()
    answer = await owner

    state = await _lock_state(lockable)
    assert state.locked_until is not None
    assert state.locked_until > datetime.now(UTC), "the lock was undone"
    # Refused as every attempt landing after the lock is, so the answer says
    # nothing about which password was right.
    assert answer == ("rejected", "TOO_MANY_LOGIN_ATTEMPTS")


async def test_a_guess_in_flight_does_not_lock_out_the_right_password(lockable: User) -> None:
    """The owner signs in while a guess, read one short of the threshold, is hashing.

    The guess added its one to the count it had read, and locked the account
    the owner had just cleared by signing in.
    """
    await _set_failures(lockable, settings.max_failed_logins - 1)

    async with SessionLocal() as owner:
        await auth_service.login(owner, email=lockable.email, password=PASSWORD)
        guess = asyncio.create_task(_login(lockable.email, WRONG))
        await _until_queued_behind(owner)
        await owner.commit()

    assert await guess == ("rejected", "INVALID_CREDENTIALS")
    state = await _lock_state(lockable)
    assert state.locked_until is None
    # Counted, from the zero the sign-in left.
    assert state.failed_login_count == 1


async def test_a_reset_lifts_a_lock_that_lands_while_it_runs(lockable: User) -> None:
    """A guess reaches the threshold while a reset link is being used.

    The reset set `locked_until = None` on the account it had read, and that
    was None already, so the write left the column out and the lock stayed.
    """
    await _set_failures(lockable, settings.max_failed_logins - 1)
    async with SessionLocal() as setup:
        issued = await auth_service.issue_password_reset(setup, email=lockable.email)
        await setup.commit()
    assert issued is not None

    async with SessionLocal() as guess:
        with pytest.raises(UnauthorizedError):
            await auth_service.login(guess, email=lockable.email, password=WRONG)
        reset = asyncio.create_task(_reset(issued.token))
        await _until_queued_behind(guess)
        await guess.commit()

    assert await reset == ("ok", "reset")
    state = await _lock_state(lockable)
    assert state.locked_until is None
    assert state.failed_login_count == 0
