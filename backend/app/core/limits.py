"""The owner's size cap on one order, for every order, guest or signed in.

At most 20 different products, at most 10 units of each (2026-10-10). One place
because three things must agree on it: the order schema, the cart schema (a
saved cart past it would fail at checkout, so it is refused where it is saved)
and the storefront, whose copy is `MAX_CART_LINES` / `MAX_LINE_QTY` in
`frontend/src/constants/index.js`. The cap is also what keeps one script from
taking a whole catalogue in a single request.
"""

MAX_ORDER_LINES = 20
MAX_LINE_QUANTITY = 10
