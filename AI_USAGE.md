# AI Usage Disclosure

Part 14 of the assignment asks how AI tools were used. This file lists the tools, the tasks they
helped with, representative prompts, how the output was reviewed, and issues that were found and
corrected.

> ✍️ **DRAFT.** Sections marked **✍️ YOUR INPUT** must be completed by the author before
> submission. Everything else describes work that can be verified in the repository.

## Tools used

| Tool | How it was used |
|---|---|
| Claude Code (Anthropic, Claude Opus model), in VS Code | Planning, code generation and review, tests, documentation, commit messages |
| ✍️ YOUR INPUT: any other tools (ChatGPT, Copilot, …) or remove this row | |

## Usage

Tasks where AI provided assistance:

- **Planning.** Turning the assignment PDF into a phased plan with a requirement checklist, so
  every part (1–14) was tracked to completion.
- **Scaffolding and features.** Project skeleton, data model and migrations, authentication,
  customers and products, orders with the confirm/cancel stock flow, CSV import, reports, the
  dashboard and user management.
- **Tests.** Unit and integration tests, including the nine Part 12 scenarios and the concurrency
  tests that send simultaneous requests.
- **Exploratory testing.** A probe script that sent 351 hostile or edge-case requests to the API;
  the bugs it found are listed in [docs/TESTING.md](docs/TESTING.md#bugs-found-and-fixed).
- **Documentation.** README, [docs/API.md](docs/API.md) (examples captured from the running app),
  [docs/CONCURRENCY.md](docs/CONCURRENCY.md), [docs/TESTING.md](docs/TESTING.md) and the
  debugging write-up.
- **Git.** Drafting commit messages from the staged changes.
- **Requirement audit.** Cross-checking the finished project against the assignment PDF to find
  anything missing.

✍️ YOUR INPUT: adjust this list. Remove anything you wrote yourself without AI help, and add
anything missing, so it reflects how you actually worked.

## Example prompts

✍️ YOUR INPUT: replace these with up to three prompts you actually used (copy them from your chat
history, lightly edited is fine).

1. *(example of the kind of prompt to include)* "Here is the assignment PDF. Make a phased plan
   that covers every requirement in Parts 1–14, with a checklist I can tick off."
2. *(example)* "Implement order confirmation so two users confirming orders for the same limited
   stock can never make stock negative. Explain the locking approach."
3. *(example)* "Go through this assignment in detail and cross-check it against what I have
   built. Is anything missing?"

## Review

How generated code was checked:

- **Automated tests against a real MySQL database.** 517 tests, 98% line coverage. Row locks,
  transactions and CHECK constraints are tested on MySQL rather than mocked, because those are
  exactly the parts that are easy to get subtly wrong.
- **Testing the tests.** The product row lock was removed temporarily to confirm the concurrency
  tests fail without it, then restored
  ([docs/CONCURRENCY.md](docs/CONCURRENCY.md#how-it-is-tested)).
- **Hand-calculated expectations.** Order totals (the assignment's 4,500.00 / 450.00 / 4,050.00
  example) and report figures are asserted against values worked out by hand.
- **Exploratory probing** of every endpoint with malformed and hostile input (see Usage).
- **Lint and formatting** with ruff on every change.
- ✍️ YOUR INPUT: describe your own review in a sentence or two. For example: manual testing in
  the browser as Admin and both Sales Users (including CSV uploads of the files in `samples/`),
  which files you read line by line, what you changed after reading them, and how you made sure
  you can explain each part (Part 14 says you must be able to explain, debug and modify the code).

## Corrections

Issues found in AI-generated work and corrected:

| # | Issue | How it was found | Fix |
|---|---|---|---|
| 1 | Large page numbers (`?page=10^20`), the date `9999-12-31`, very large stock and very large order totals each caused a **500** error | Exploratory probe | Inputs are bounded and checked; each case now returns 409 or 422 and has a regression test ([docs/TESTING.md](docs/TESTING.md#bugs-found-and-fixed)) |
| 2 | Money fields accepted `"1e2"` and `"1_000"`, because Python's `Decimal` parses those forms | Exploratory probe | Money and discount text must be a plain number such as `1500.50` |
| 3 | The order service's docstring pointed to `docs/CONCURRENCY.md`, which did not exist; `docs/TESTING.md` referred to `AI_USAGE.md` before it was written | Requirement audit against the PDF | Both documents were written |
| 4 | `docs/TESTING.md` reported 516 tests, and three per-file counts were out of date | Re-ran the suite and counted tests per file | Counts corrected to 517 |
| 5 | A draft README sentence said order items are deleted by `ON DELETE CASCADE` when a Draft line is removed; in fact orders are never deleted, and removed lines are deleted by the application | Checking each README claim against the code | Sentence corrected before commit |

✍️ YOUR INPUT: add any issue **you** noticed and corrected yourself, for example something that did
not work when you tried it in the browser, or code you rewrote because you did not agree with it.
One concrete example of your own is worth more than a long list.
