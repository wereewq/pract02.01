import re
from datetime import date
from typing import List, Optional
from pydantic import BaseModel, field_validator

class LoginRequest(BaseModel):
    login: str
    password: str

class UserCreate(BaseModel):
    login: str
    password: str
    full_name: str
    role: str

    @field_validator("login")
    @classmethod
    def validate_login(cls, v: str):
        if not re.match(r"^[a-zA-Z0-9_@.-]{4,50}$", v):
            raise ValueError("Логин должен содержать латинские буквы и цифры")
        return v

class ProductCreate(BaseModel):
    title: str
    author: str
    category: str
    price: float
    isbn: str
    initial_stock_store_1: int = 0
    initial_stock_store_2: int = 0
    initial_stock_store_3: int = 0

    @field_validator("price")
    @classmethod
    def check_price(cls, v: float):
        if v <= 0 or v > 99999.99:
            raise ValueError("Цена должна быть больше 0 и до 99999.99")
        return round(v, 2)

    @field_validator("isbn")
    @classmethod
    def check_isbn(cls, v: str):
        cleaned = v.replace("-", "").strip()
        if not re.match(r"^\d{10}(\d{3})?$", cleaned):
            raise ValueError("ISBN должен состоять из 10 или 13 цифр")
        return cleaned

class ProductUpdate(BaseModel):
    title: str
    author: str
    category: str
    price: float
    isbn: str

class SupplyItemIn(BaseModel):
    product_id: int
    quantity: int
    purchase_price: float

class SupplyCreate(BaseModel):
    supplier_id: int
    store_id: int
    supply_date: date
    invoice_number: str
    items: List[SupplyItemIn]

class SaleItemIn(BaseModel):
    product_id: int
    quantity: int

class SaleCreate(BaseModel):
    store_id: int
    payment_method: str = "Карта"
    card_number: Optional[str] = None
    items: List[SaleItemIn]

class CustomerCreate(BaseModel):
    full_name: str
    phone: str
    email: str
    card_number: Optional[str] = None
    discount_percent: int = 5
    valid_until: Optional[date] = None

class ReportRequest(BaseModel):
    report_type: str  # sales_period, low_stock, customer_activity
    date_from: date
    date_to: date
    store_id: Optional[int] = None
    stock_threshold: int = 5
