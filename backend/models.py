from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal

# User Models
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    is_admin: bool = False

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# Flipkart User Models
class FlipkartUserCreate(BaseModel):
    email: EmailStr
    password: Optional[str] = None
    proxy_config: Optional[Dict[str, Any]] = None

class FlipkartUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    cookies: Optional[str] = None
    proxy_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class FlipkartUserResponse(BaseModel):
    id: int
    email: str
    cookies: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime]
    login_attempts: int
    created_at: datetime

# CSV Import Models
class ProductCSVImport(BaseModel):
    products: List[Dict[str, Any]]  # List of product data from CSV

class FlipkartAccountCSVImport(BaseModel):
    accounts: List[Dict[str, Any]]  # List of account data from CSV

# Product Models
class ProductCreate(BaseModel):
    product_link: str
    product_name: Optional[str] = None
    quantity: int = 1
    price_cap: Optional[Decimal] = None
    check_interval: int = 300

    @validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Quantity must be positive')
        return v

    @validator('price_cap')
    def price_cap_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Price cap must be positive')
        return v

class ProductUpdate(BaseModel):
    product_link: Optional[str] = None
    product_name: Optional[str] = None
    quantity: Optional[int] = None
    price_cap: Optional[Decimal] = None
    check_interval: Optional[int] = None
    is_active: Optional[bool] = None

class ProductResponse(BaseModel):
    id: int
    product_link: str
    product_name: Optional[str]
    quantity: int
    price_cap: Optional[Decimal]
    is_active: bool
    check_interval: int
    created_at: datetime

# Order Models
class OrderCreate(BaseModel):
    product_id: int
    flipkart_user_id: int
    product_name: str
    actual_price: Decimal
    quantity: int
    delivery_address: Optional[str] = None

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    order_id: Optional[str] = None
    expected_delivery: Optional[date] = None
    tracking_id: Optional[str] = None
    notes: Optional[str] = None

class OrderResponse(BaseModel):
    id: int
    product_id: int
    flipkart_user_id: int
    product_name: str
    order_id: Optional[str]
    actual_price: Decimal
    quantity: int
    status: str
    payment_method: str
    delivery_address: Optional[str]
    order_date: datetime
    expected_delivery: Optional[date]
    tracking_id: Optional[str]
    notes: Optional[str]

# Automation Models
class AutomationSessionCreate(BaseModel):
    session_name: str
    config: Optional[Dict[str, Any]] = None
    max_cart_value: Optional[Decimal] = None

class AutomationSessionUpdate(BaseModel):
    status: Optional[str] = None
    products_monitored: Optional[int] = None
    accounts_used: Optional[int] = None
    orders_placed: Optional[int] = None
    errors_count: Optional[int] = None
    logs: Optional[str] = None
    max_cart_value: Optional[Decimal] = None

class AutomationSessionResponse(BaseModel):
    id: int
    batch_session_id: str
    automation_type: str
    status: str
    batch_size: int
    total_accounts: int
    total_batches: int
    completed_batches: int
    account_range_start: Optional[int]
    account_range_end: Optional[int]
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    started_at: datetime
    ended_at: Optional[datetime]
    config: Optional[Dict[str, Any]]
    error_message: Optional[str]
    max_cart_value: Optional[Decimal] = None

# System Settings Models
class SystemSettingCreate(BaseModel):
    setting_key: str
    setting_value: str
    setting_type: str = "string"
    description: Optional[str] = None

class SystemSettingUpdate(BaseModel):
    setting_value: str
    description: Optional[str] = None

class SystemSettingResponse(BaseModel):
    id: int
    setting_key: str
    setting_value: str
    setting_type: str
    description: Optional[str]
    updated_at: datetime

# Dashboard Models
class DashboardStats(BaseModel):
    total_products: int
    active_products: int
    total_orders: int
    orders_today: int
    active_sessions: int
    total_flipkart_accounts: int
    success_rate: float

 