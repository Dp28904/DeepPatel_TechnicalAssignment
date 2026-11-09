from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.core.enums import OrderStatus
from app.modules.orders.schemas import OrderSummaryOut


class Kpis(BaseModel):
    net_sales: Decimal  # confirmed, after discount
    gross_sales: Decimal  # confirmed, before discount
    discounts: Decimal
    confirmed_orders: int
    average_order_value: Decimal
    draft_orders: int
    draft_value: Decimal
    cancelled_orders: int
    low_stock_products: int


class MonthPoint(BaseModel):
    year: int
    month: int
    label: str  # e.g. "Aug 2026"
    orders: int
    net_sales: Decimal


class StatusSlice(BaseModel):
    status: OrderStatus
    orders: int
    value: Decimal


class CustomerBar(BaseModel):
    customer_id: int
    customer_name: str
    orders: int
    net_sales: Decimal


class ProductBar(BaseModel):
    product_id: int
    code: str
    name: str
    quantity_sold: int
    gross_value: Decimal


class CategoryBar(BaseModel):
    category: str
    quantity_sold: int
    gross_value: Decimal


class UserBar(BaseModel):
    user_id: int
    user_name: str
    orders: int
    net_sales: Decimal


class LowStockItem(BaseModel):
    product_id: int
    code: str
    name: str
    stock_quantity: int


class Dashboard(BaseModel):
    scope: Literal["all", "own"]  # Admin sees every order; Sales User only their own
    date_from: date | None
    date_to: date | None
    low_stock_threshold: int
    kpis: Kpis
    monthly_sales: list[MonthPoint]
    orders_by_status: list[StatusSlice]
    top_customers: list[CustomerBar]
    top_products: list[ProductBar]
    sales_by_category: list[CategoryBar]
    sales_by_user: list[UserBar]  # Admin only; empty for a Sales User
    low_stock: list[LowStockItem]
    recent_orders: list[OrderSummaryOut]
