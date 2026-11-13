from datetime import date, datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    login: str = Field(unique=True, index=True, max_length=50)
    password_hash: str
    full_name: str = Field(max_length=150)
    role: str = Field(max_length=20)  # Администратор, Менеджер, Кассир, Руководитель

class Store(SQLModel, table=True):
    __tablename__ = "stores"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    address: str = Field(max_length=200)

class Product(SQLModel, table=True):
    __tablename__ = "product"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=200)
    author: str = Field(max_length=150)
    category: str = Field(max_length=100)
    price: float = Field(gt=0)
    isbn: str = Field(unique=True, max_length=20)

class Stock(SQLModel, table=True):
    __tablename__ = "stock"
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    store_id: int = Field(foreign_key="stores.id")
    quantity: int = Field(default=0, ge=0)

class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=150)
    contact_name: str = Field(default="", max_length=100)
    phone: str = Field(max_length=20)
    email: str = Field(default="", max_length=100)
    address: str = Field(default="", max_length=200)

class Supply(SQLModel, table=True):
    __tablename__ = "supplies"
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: int = Field(foreign_key="suppliers.id")
    store_id: int = Field(foreign_key="stores.id")
    supply_date: date = Field(default_factory=date.today)
    invoice_number: str = Field(max_length=30)
    total_amount: float = Field(default=0.0)

class SupplyItem(SQLModel, table=True):
    __tablename__ = "supply_items"
    id: Optional[int] = Field(default=None, primary_key=True)
    supply_id: int = Field(foreign_key="supplies.id")
    product_id: int = Field(foreign_key="product.id")
    quantity: int = Field(gt=0)
    purchase_price: float = Field(gt=0)

class Customer(SQLModel, table=True):
    __tablename__ = "customers"
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(max_length=150)
    phone: str = Field(max_length=20)
    email: str = Field(unique=True, max_length=100)

class DiscountCard(SQLModel, table=True):
    __tablename__ = "discount_cards"
    id: Optional[int] = Field(default=None, primary_key=True)
    customer_id: int = Field(foreign_key="customers.id")
    card_number: str = Field(unique=True, max_length=20)
    discount_percent: int = Field(ge=0, le=50)
    issue_date: date = Field(default_factory=date.today)
    valid_until: Optional[date] = None

class Sale(SQLModel, table=True):
    __tablename__ = "sales"
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: int = Field(foreign_key="users.id")
    store_id: int = Field(foreign_key="stores.id")
    customer_id: Optional[int] = Field(default=None, foreign_key="customers.id")
    payment_method: str = Field(default="Карта", max_length=20)
    status: str = Field(default="Проведено", max_length=20)
    total: float = Field(ge=0)

class SaleItem(SQLModel, table=True):
    __tablename__ = "sales_items"
    id: Optional[int] = Field(default=None, primary_key=True)
    sale_id: int = Field(foreign_key="sales.id")
    product_id: int = Field(foreign_key="product.id")
    quantity: int = Field(gt=0)
    price_at_sale: float = Field(gt=0)
    discount_percent: int = Field(default=0)
