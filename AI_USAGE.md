# AI Usage Disclosure

This file covers Part 14 of the assignment: which AI tools I used, what I used them for, a few
of the prompts I gave, how I checked the output, and what I had to correct.

In short, I used an AI coding assistant like a fast pair programmer. I decided what to build, how
the application is structured and how the important flows work (orders, stock, permissions, CSV
import). The assistant wrote much of the code for those decisions. I read it, tested it, and
changed or rejected it where it was wrong or did not match what I wanted. I can explain every part
of the code, and I am ready to modify it in the interview.

## Tools used

| Tool | What I used it for |
|---|---|
| Claude Code (Anthropic), inside VS Code | Turning my plan into code, writing tests and repetitive code, reviewing my changes, drafting documentation and commit messages |

I did not use any other AI tool for this assignment.

## How I worked with the AI

### What I decided myself

Before any code was written, I went through the PDF part by part and made these decisions. The
assistant then worked inside them.

- **Stack.** FastAPI with Python 3.12, MySQL 8.4 (the LTS release, because 8.0 is end of life),
  SQLAlchemy with Alembic migrations, and plain HTML/CSS/JavaScript with `fetch()` and no frontend
  framework. The PDF says a simple interface is enough, so I spent the time on the backend logic.
- **Code structure.** Each business area (customers, products, orders, imports, reports, users)
  is its own module with the same layers: `router` → `service` → `repository`. Routers handle only
  HTTP, services hold the business rules and transactions, and repositories hold only SQL. Shared
  code lives in `app/core`. I wanted this so that any rule lives in exactly one place, which the
  PDF asks for under "avoid duplicated calculation and validation logic".
- **The server owns the money.** The browser sends only the customer, date, discount and
  `(product, quantity)` pairs. Rates come from the database, totals are calculated in one file
  (`orders/calculations.py`) using `Decimal` and `ROUND_HALF_UP`, and any extra field such as
  `rate`, `grand_total` or `status` in a request is rejected with a 422. The JavaScript totals are
  only a preview.
- **Stock flow and concurrency.** Draft orders never touch stock. Confirm and cancel lock the order
  row first, then lock the product rows in ascending id order (to avoid deadlocks), check every
  line before changing anything, and save status, stock and stock movements in one transaction. A
  database `CHECK` constraint is the last line of defence against negative stock. I chose
  pessimistic row locks over optimistic versioning because a confirm touches several products at
  once, and locks make that easy to reason about and explain.
- **Every stock change leaves a record.** Stock changes in only four places (opening stock, Admin
  adjustment, confirm and cancel) and each one writes a stock movement. The product edit form
  deliberately cannot change stock.
- **Access rules.** A Sales User who opens another user's order gets a 404 rather than a 403, so
  they cannot even find out that the order exists. Sales Users see only active customers and
  products, including on direct `GET /{id}` requests.
- **Deactivate instead of delete** for customers and products that are referenced by orders or
  stock movements.
- **CSV import rules.** Row numbers match the line numbers in the file (the header is line 1), the
  whole file is validated before anything is written, and product codes are compared without
  regard to case.
- **Business limits in one file** (`app/core/constants.py`), such as the 20% maximum discount, so a
  live change in the interview ("make the maximum discount 25%") is a one-line edit.
- **Scope.** I added a Dockerfile so the reviewer can run everything with one command. I chose not
  to add CI or a Postman collection, and wrote `docs/API.md` with real request and response
  examples instead.
- **Git workflow.** One feature branch per phase (`feature/core-db`, `feature/auth`,
  `feature/master-data`, `feature/orders`, `feature/reports`, `feature/debugging`), merged into
  `main` through pull requests. Nothing was committed or pushed without my approval, and I
  reviewed every diff before committing it.

### What the AI helped with

- **Breaking the PDF into a plan.** I asked it to turn the assignment into phases and a requirement
  checklist. I then went through that checklist myself and settled the open questions (listed
  above) before starting.
- **Writing code from my design.** Models and migrations, CRUD endpoints, Pydantic schemas, the
  order form JavaScript, report queries and the HTML templates. This is where it saved the most
  time, because a lot of this code is repetitive once the structure is fixed.
- **Tests.** Writing the test cases for the nine Part 12 scenarios and the extra edge cases I asked
  for. I set the expected values myself, for example the 4,500.00 / 450.00 / 4,050.00 example from
  the PDF.
- **Finding edge cases.** Generating malformed and extreme inputs to throw at the API (huge page
  numbers, far-future dates, scientific notation in money fields).
- **Documentation and commit messages.** Drafting the README sections, `docs/API.md`,
  `docs/CONCURRENCY.md` and `docs/TESTING.md`, which I then edited and checked against the code.

## Example prompts

These are three prompts that show how I used the assistant: I gave the design and the
constraints, and asked it to implement or check against them.

**1. Planning: I set the stack and structure, and asked for a plan that covers every requirement**

> I've attached the assignment PDF. I'm building it with FastAPI, MySQL 8.4 and plain JavaScript,
> no frontend framework. Each module should be split into router, service and repository, with
> shared code in app/core. Make me a phase-by-phase plan where every phase is its own feature
> branch, and list any requirement in the PDF that is unclear so I can decide how to handle it
> before we start. Don't write code yet.

**2. Implementation: I described the locking approach and asked for it to be built and tested**

> Implement confirm and cancel for orders. Lock the order row with SELECT ... FOR UPDATE and
> re-check that it is still Draft after the lock. Then lock all its products in ascending id order,
> collect every shortfall before changing anything, and do the stock update, the movements and the
> status change in one transaction. Cancel restores stock only if the order was Confirmed. Write a
> test with two threads confirming two orders for the same limited stock, and check that exactly
> one succeeds and stock never goes negative.

**3. Review: I asked it to check the finished work against the PDF, not to add features**

> Go through the assignment PDF part by part and compare it with what's in the repo. For each
> requirement, tell me where it's implemented and which test covers it. List anything that is
> missing or only partly done. Don't change any code, I'll decide what to fix.

## How I reviewed the generated code

- **I read the diffs before every commit.** I checked that code was in the right layer (no SQL in
  routers, no business rules in repositories), that names were readable, and that there was no
  duplicated validation. Where I could not follow a piece of code, I asked for it to be simplified
  or explained until I could explain it myself.
- **Tests against a real MySQL database, not mocks.** Row locks, transactions and `CHECK`
  constraints behave differently on a real database, and those are exactly the parts that are easy
  to get subtly wrong. The suite has 519 tests with 98% line coverage.
- **Testing the tests.** To prove the concurrency tests actually guard something, I temporarily
  removed the product row lock. The tests failed every time (stock went negative, or was deducted
  twice), then passed again once the lock was back
  ([docs/CONCURRENCY.md](docs/CONCURRENCY.md#how-it-is-tested)).
- **Expected values worked out by hand.** Order totals and report figures in the tests are checked
  against numbers I calculated myself, not numbers copied from the code's output.
- **Manual testing in the browser** as an Admin and as both Sales Users: creating and editing
  orders, confirming and cancelling, trying to open another user's order by changing the id in the
  URL, and uploading CSV files.
- **My own CSV test files.** I wrote the files in [samples/test_uploads](samples/test_uploads)
  (empty file, header only, semicolon-separated, the same code in different case, values over the
  limits, a 50-product bulk file) to check the import from a user's point of view.
- **Lint and formatting** with `ruff` on every change.

## Corrections

Problems I found in AI-generated work and had fixed:

| # | Problem | How I found it | Fix |
|---|---|---|---|
| 1 | A very large page number (`?page=10^20`), the date `9999-12-31`, very large stock values and very large order totals each caused a **500** error | Sending extreme inputs to every endpoint | Inputs are now bounded and validated, each case returns a clear 409 or 422, and each has a regression test ([docs/TESTING.md](docs/TESTING.md#bugs-found-and-fixed)) |
| 2 | Money fields accepted `"1e2"` and `"1_000"`, because Python's `Decimal` parses those forms | Same edge-case testing | Money and discount values must now be a plain number such as `1500.50` |
| 3 | When I uploaded my out-of-range CSV, the error said `Price is too large (maximum Decimal('9999999.99')).`, which shows Python internals to the user | Uploading my own test file (`samples/test_uploads/10_invalid_limits_and_formats.csv`) | The CSV validator now uses the same number formatter as the API (`maximum 9,999,999.99`), with two regression tests |
| 4 | A draft of the README said order items are removed by `ON DELETE CASCADE` when a Draft line is removed. That is wrong: orders are never deleted, and the application deletes the removed lines | Checking each README claim against the code | Corrected before committing |
| 5 | The order service's docstring pointed to `docs/CONCURRENCY.md`, which did not exist yet, and the test counts in `docs/TESTING.md` were out of date | My final check of the docs against the PDF and the repo | Wrote the missing document and corrected the counts after re-running the suite |

The main limitation I saw was that the assistant writes confident documentation that is not always
true for the actual code (row 4 above), and it does not try unusual inputs unless asked (rows 1
to 3). For that reason I checked every documented claim against the code and wrote my own edge-case
test files instead of relying only on the generated tests.
