"""Jinja2 setup shared by all page routes.

Pages are thin HTML shells. The data is loaded by JavaScript from the JSON API, so
validation and permissions live in one place (the API and its services).
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.core import constants

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Business limits exposed to templates, so JavaScript validation uses the same values
# as the backend (rendered as data-* attributes in base.html).
templates.env.globals["limits"] = {
    "maxDiscountPercent": str(constants.MAX_DISCOUNT_PERCENT),
    "minDiscountPercent": str(constants.MIN_DISCOUNT_PERCENT),
    "minQuantity": constants.MIN_ITEM_QUANTITY,
    "maxQuantity": constants.MAX_ITEM_QUANTITY,
    "maxPageSize": constants.MAX_PAGE_SIZE,
}
