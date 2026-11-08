"""Business limits in one place.

Change a rule here and every layer that uses it (Pydantic schemas, services, the
initial migration's CHECK constraints and the JavaScript, via template data
attributes) picks up the new value. If a limit is also enforced by a database
CHECK constraint, changing it also needs a new Alembic migration.
"""

from datetime import date
from decimal import Decimal

# --- Orders ---------------------------------------------------------------
MIN_DISCOUNT_PERCENT = Decimal("0")
MAX_DISCOUNT_PERCENT = Decimal("20")
MIN_ITEM_QUANTITY = 1
MAX_ITEM_QUANTITY = 1_000_000
ORDER_NUMBER_PREFIX = "SO"
MIN_ORDER_DATE = date(2000, 1, 1)

# --- Products / money -----------------------------------------------------
MAX_PRICE = Decimal("9999999.99")
# Largest value a DECIMAL(12,2) column can hold. Order line amounts and totals are
# checked against it, because quantity x price can exceed it (1,000,000 x 9,999,999.99).
MAX_MONEY_AMOUNT = Decimal("9999999999.99")
MONEY_PRECISION = 12
MONEY_SCALE = 2
PRODUCT_CODE_PATTERN = r"^[A-Za-z0-9-]{1,30}$"
MAX_STOCK_QUANTITY = 1_000_000_000  # stock may never exceed this (MySQL INT max is ~2.1 billion)
MIN_ADJUSTMENT_REASON_LENGTH = 3

# --- Field lengths (shared by models and schemas) -------------------------
NAME_MAX_LENGTH = 150
EMAIL_MAX_LENGTH = 255
MOBILE_MAX_LENGTH = 20
CITY_MAX_LENGTH = 100
CATEGORY_MAX_LENGTH = 80
PRODUCT_CODE_MAX_LENGTH = 30
REASON_MAX_LENGTH = 255

# --- Pagination -----------------------------------------------------------
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_PAGE_NUMBER = 100_000  # keeps the SQL OFFSET within range

# --- CSV import -----------------------------------------------------------
CSV_MAX_BYTES = 1_048_576  # 1 MB
CSV_MAX_ROWS = 5_000
