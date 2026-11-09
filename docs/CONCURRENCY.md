# Stock consistency and concurrency

Part 6 asks how the application prevents conflicting stock updates. This document explains the
approach, the reasons behind each decision, and how it is tested.

## The problem

Stock is a shared number that several requests can change at the same moment:

- two Sales Users confirm different orders for the same limited product;
- the same order is confirmed twice (a double click, or a retried request);
- an order is confirmed while someone cancels it;
- an Admin adjusts stock while an order using that product is being confirmed.

A naive "read stock → check → write stock" sequence breaks in all of these cases. Two requests
can both read `stock = 3`, both decide that 3 units are available, and both deduct, leaving
`-3`. This is a classic *lost update* race.

## The approach: pessimistic row locking inside one transaction

Every operation that changes stock runs as **one database transaction** that **locks the rows
it is about to change before it reads them**. A second request that needs the same rows waits
until the first one commits or rolls back, then reads the up-to-date values.

MySQL InnoDB provides this with `SELECT ... FOR UPDATE` (exclusive row lock) and
`SELECT ... FOR SHARE` (shared row lock). The application uses the `REPEATABLE READ` isolation
level, InnoDB's default, set explicitly in [app/core/database.py](../app/core/database.py).

### Confirming an order

[`orders.service.confirm_order`](../app/modules/orders/service.py) runs these steps in a single
transaction:

| Step | What happens | Why |
|---|---|---|
| 1 | Lock the **order** row: `SELECT ... FOR UPDATE OF sales_orders` | Confirms, cancels and edits of the same order queue up here, one at a time |
| 2 | Re-check the status **after** the lock is held; anything except `DRAFT` → `409 invalid_order_status` | A second confirm that waited in step 1 now sees `CONFIRMED` and stops. Repeated requests cannot deduct twice |
| 3 | Lock the **customer** row: `FOR SHARE` | Nobody can deactivate or delete the customer while the order is confirmed |
| 4 | Lock **every product** row on the order: `FOR UPDATE`, **in ascending id order** | Other confirmations, cancellations and stock adjustments touching these products wait. The fixed order prevents deadlocks (see below) |
| 5 | Check **everything before changing anything**: customer active, products active, `stock >= quantity` for every line | If any item is short, raise `409 insufficient_stock` listing every short item. The transaction rolls back, so no stock, status or movement changes |
| 6 | For each line: `stock_quantity -= quantity`, and write one `ORDER_CONFIRM` stock movement | The stock change and its audit record are saved together or not at all |
| 7 | Set status `CONFIRMED`, `confirmed_at`, `confirmed_by` | |
| 8 | Commit, which releases all locks | |

### Cancelling an order

[`cancel_order`](../app/modules/orders/service.py) locks the order row and re-checks the status
in the same way. Then:

- a `CANCELLED` order → `409`, so stock is never restored twice;
- a `CONFIRMED` order → products are locked (ascending id), the confirmed quantities are added
  back, and one `ORDER_CANCEL` movement is written per line;
- a `DRAFT` order → only the status changes; Drafts never touched stock.

### Admin stock adjustments

[`products.service.adjust_stock`](../app/modules/products/service.py) locks the product row with
`FOR UPDATE`, checks that the new quantity is between 0 and the maximum, updates the stock and
writes an `ADJUSTMENT_IN` or `ADJUSTMENT_OUT` movement, then commits. Because it takes the same
product lock as a confirmation, the two can never interleave.

### Drafts do not lock stock

Creating and editing a Draft never changes stock, so it does not lock products. Stock is only
checked at confirmation time, under the lock. A Draft can therefore be saved for more units than
are in stock; the order form warns about this, and the confirmation is rejected until stock is
available.

## Why these decisions

**Pessimistic locking rather than optimistic versioning.** Optimistic concurrency (a `version`
column and "update only if the version is unchanged") is a good fit when conflicts are rare and
a retry is cheap. Here, conflicts are expected on popular, low-stock products, and a confirmation
touches several rows at once. Row locks make the second request simply wait a few milliseconds
and then see the correct stock, with no retry loop in the application.

**Not a single `UPDATE ... SET stock = stock - n WHERE stock >= n`.** That atomic statement is
safe for one product, but an order has several lines. If line 3 failed after lines 1 and 2 had
succeeded, the code would have to undo them, and the response could not list every short item.
Locking all products first, checking all lines, and only then writing, keeps "all or nothing"
simple and lets the error explain exactly what is missing.

**Deadlock prevention by lock ordering.** If order A locks product 1 then product 2, while order
B locks product 2 then product 1, each can end up waiting for the other forever. MySQL would
detect this and kill one transaction. Sorting product ids before locking
(`ORDER BY id ... FOR UPDATE` in
[products/repository.py](../app/modules/products/repository.py)) means every transaction takes
locks in the same order, so this cycle cannot form.

**Lock the order first.** Every state change starts with the order row. This serialises all
actions on one order and makes the status check after the lock reliable, which is what makes
repeated confirm and cancel requests harmless.

**A fresh transaction before locking.** Under `REPEATABLE READ`, a transaction reads from a
snapshot taken at its first plain read. If a request had already read data before taking a lock
(for example while loading the logged-in user), later plain reads could see that older snapshot.
The `transaction()` helper in [app/core/database.py](../app/core/database.py) commits any earlier
read-only work first, so the new transaction starts with the locking reads. Locked rows are also
reloaded with `populate_existing`, so the ORM never reuses a stale cached copy.

**The database as a final safety net.** Even if the application had a bug, the
`CHECK (stock_quantity >= 0)` constraint on `products` makes MySQL refuse to store negative
stock, and the transaction would roll back.

**Lock conflicts become a clear, retryable error.** If MySQL ever reports a lock wait timeout
(error 1205) or a deadlock (1213), the transaction has already been rolled back. The error
handler turns this into `409 lock_conflict` ("This record is being updated by another request.
Please try again.") instead of a `500`.

## The stock ledger

Every stock change writes exactly one row in `stock_movements`, in the same transaction:

| Movement type | When | `quantity_change` |
|---|---|---|
| `OPENING` | A product is created or imported with stock | `+stock` |
| `ADJUSTMENT_IN` / `ADJUSTMENT_OUT` | An Admin adjustment (reason required) | `+n` / `-n` |
| `ORDER_CONFIRM` | An order is confirmed | `-quantity` per line |
| `ORDER_CANCEL` | A confirmed order is cancelled | `+quantity` per line |

Because changes and ledger rows are committed together, `SUM(quantity_change)` for a product
always equals its `stock_quantity`. Several tests assert this invariant after concurrent
operations.

## How it is tested

[tests/integration/test_order_concurrency.py](../tests/integration/test_order_concurrency.py)
sends **real simultaneous HTTP requests** from several threads, released at the same instant with
`threading.Barrier`, against the real MySQL test database:

| Test | Scenario | Asserted result |
|---|---|---|
| `test_two_users_confirming_against_limited_stock_never_go_negative` | Two Sales Users confirm orders of 3 units each against stock 5 | Exactly one `200` and one `409 insufficient_stock` (`available: 2`); stock ends at 2; ledger sums to the stock |
| `test_same_order_confirmed_twice_at_once_deducts_once` | The same order confirmed three times at once | One `200`, two `409`; stock deducted once |
| `test_confirm_and_cancel_racing_leave_consistent_stock` | Confirm and cancel race on one order | Final status `CANCELLED`; stock back to its starting value; ledger sums to zero |
| `test_orders_locking_the_same_products_in_different_order_do_not_deadlock` | Order A has products (1, 2), order B has (2, 1), confirmed together | Both `200`; no deadlock |
| `test_admin_adjustment_racing_a_confirmation_never_goes_negative` | An Admin decrease races a confirmation for the same product | One succeeds, the other gets `409`; stock never negative |

To check that these tests really detect the race, the product row lock was **removed
temporarily**. The tests then failed (stock went negative, or was deducted twice) and passed
again once the lock was restored.

## Known limits of this approach

- Locks are held for the duration of a confirmation, which is a few milliseconds. Very large
  orders on very busy products would wait on each other longer; for this application's scale
  this is not a concern.
- The design relies on InnoDB row locks, so it assumes MySQL (or another database with the same
  locking semantics). It is not safe on a database without row-level locking.
