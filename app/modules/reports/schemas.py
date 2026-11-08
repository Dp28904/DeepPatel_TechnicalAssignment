from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class DateRange(BaseModel):
    date_from: date | None
    date_to: date | None


class CustomerSalesRow(BaseModel):
    customer_id: int
    customer_name: str
    city: str | None
    is_active: bool
    confirmed_orders: int
    total_sales: Decimal  # after order discount (sum of grand totals)


class CustomerSalesTotals(BaseModel):
    customers: int
    customers_with_sales: int
    confirmed_orders: int
    total_sales: Decimal


class CustomerSalesReport(BaseModel):
    filters: DateRange
    rows: list[CustomerSalesRow]
    totals: CustomerSalesTotals


class ProductSalesRow(BaseModel):
    product_id: int
    code: str
    name: str
    category: str
    is_active: bool
    quantity_sold: int
    order_count: int
    gross_value: Decimal  # before order discount (sum of item amounts)


class ProductSalesTotals(BaseModel):
    quantity_sold: int
    gross_value: Decimal


class ProductSalesReport(BaseModel):
    filters: DateRange
    rows: list[ProductSalesRow]
    totals: ProductSalesTotals


class LowStockRow(BaseModel):
    product_id: int
    code: str
    name: str
    category: str
    price: Decimal
    stock_quantity: int
    is_active: bool
    below_threshold_by: int


class LowStockReport(BaseModel):
    threshold: int
    include_inactive: bool
    rows: list[LowStockRow]
