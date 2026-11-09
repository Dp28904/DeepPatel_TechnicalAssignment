"""Imports every model so ``Base.metadata`` knows all tables.

Used by Alembic (migrations/env.py) and anywhere the full schema is needed.
"""

from app.core.database import Base
from app.modules.customers.models import Customer
from app.modules.inventory.models import StockMovement
from app.modules.orders.models import SalesOrder, SalesOrderItem
from app.modules.products.models import Product
from app.modules.users.models import User

__all__ = ["Base", "Customer", "Product", "SalesOrder", "SalesOrderItem", "StockMovement", "User"]
