# 🐍 Backend API Documentation

## Overview

This is the FastAPI backend service for the Flipkart Automation System. It provides REST APIs for user management, automation control, product management, and system configuration.

## 📁 Project Structure

```
backend/
├── routers/                    # API route definitions
│   ├── __init__.py
│   ├── addresses.py           # Address management CRUD
│   ├── auth.py               # Authentication & authorization
│   ├── accounts.py           # Flipkart account management
│   ├── products.py           # Product management
│   ├── automation.py         # Automation session control
│   ├── orders.py            # Order tracking & history
│   ├── settings.py          # System settings
│   └── users.py             # User management (admin)
├── services/                  # Business logic & automation
│   ├── automation_tasks/     # Core automation modules
│   │   ├── core_worker.py   # Main automation controller
│   │   ├── cart_manager.py  # Cart operations & quantity management
│   │   ├── checkout_handler.py # Checkout & payment processing
│   │   └── batch_manager.py # Multi-session management
│   ├── automation_worker.py  # Automation orchestration
│   ├── auth_service.py      # Authentication logic
│   ├── database.py          # Database connection & models
│   └── email_service.py     # Email notifications
├── venv/                     # Python virtual environment
├── .env.example             # Environment variables template
├── database_schema.py       # Database models & schema
├── main.py                  # FastAPI application entry point
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 12+
- Virtual environment (recommended)

### Installation

1. **Create Virtual Environment**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Setup Environment Variables**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Initialize Database**
```bash
# Ensure PostgreSQL is running
python database_schema.py
```

5. **Start Server**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 🔧 Configuration

### Environment Variables (.env)
```env
# Database Configuration
DATABASE_URL=postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation

# JWT Authentication
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Admin User (Created automatically)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_EMAIL=admin@flipkart-automation.com

# Automation Settings
MAX_CONCURRENT_SESSIONS=3
DEFAULT_CHECK_INTERVAL=30
ORDER_TIMEOUT=1800

# Email Configuration (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Browser Settings
HEADLESS_MODE=true
PROXY_ROTATION_ENABLED=false
```

## 📊 Database Schema

### Core Tables

#### users
- `id`: Primary key
- `username`: Unique username
- `email`: User email address
- `password_hash`: Bcrypt hashed password
- `is_admin`: Admin privileges flag
- `is_active`: Account status
- `created_at`: Account creation timestamp

#### addresses
- `id`: Primary key
- `user_id`: Foreign key to users
- `name`: Display name for address
- `description`: Internal description
- `address_template`: Keywords for address validation
- `office_no_min/max`: Office number range
- `name_postfix`: Name validation keyword
- `phone_prefix`: Phone number prefix
- `pincode`: PIN code for validation
- `is_active`: Address status
- `is_default`: Default selection flag

#### flipkart_accounts
- `id`: Primary key
- `user_id`: Foreign key to users
- `email/phone`: Login credentials
- `password`: Encrypted account password
- `account_name`: Display name
- `is_active`: Account status
- `last_used`: Last automation timestamp

#### products
- `id`: Primary key
- `user_id`: Foreign key to users
- `product_url`: Flipkart product URL
- `product_name`: Product title
- `target_price`: Price monitoring threshold
- `quantity`: Desired quantity
- `is_active`: Product status

#### automation_sessions
- `id`: Primary key
- `user_id`: Foreign key to users
- `session_status`: Current status
- `products_data`: JSON product configuration
- `account_id`: Flipkart account used
- `address_id`: Delivery address used
- `started_at`: Session start time
- `completed_at`: Session completion time
- `error_message`: Error details if failed

#### system_settings
- `setting_name`: Setting identifier (Primary key)
- `setting_value`: Configuration value
- `description`: Setting description
- `updated_at`: Last modification time

### Database Operations

#### Connection Management
```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## 🔐 Authentication & Security

### JWT Token Authentication
- **Algorithm**: HS256
- **Expiration**: 30 minutes (configurable)
- **Refresh**: Automatic token refresh on valid requests
- **Scope**: User-specific data access

### Password Security
- **Hashing**: Bcrypt with salt rounds
- **Validation**: Minimum 8 characters
- **Storage**: Never store plaintext passwords

### API Security
```python
# Protected endpoint example
from fastapi import Depends, HTTPException, status
from .auth_service import get_current_user

@app.get("/api/protected-endpoint")
async def protected_route(current_user: User = Depends(get_current_user)):
    return {"message": f"Hello {current_user.username}"}
```

## 🛡️ API Endpoints

### Authentication (`/api/auth/`)
- `POST /login`: User authentication
- `POST /register`: User registration (admin only)
- `POST /refresh`: Token refresh
- `GET /me`: Current user profile

### Address Management (`/api/addresses/`)
- `GET /`: List user addresses
- `POST /`: Create new address
- `GET /{id}`: Get specific address
- `PUT /{id}`: Update address
- `DELETE /{id}`: Delete address
- `POST /{id}/set-default`: Set as default

### Flipkart Accounts (`/api/accounts/`)
- `GET /`: List user accounts
- `POST /`: Add new account
- `PUT /{id}`: Update account
- `DELETE /{id}`: Remove account
- `POST /{id}/test`: Test account credentials

### Automation Control (`/api/automation/`)
- `POST /start`: Start automation session
- `GET /status/{session_id}`: Check session status
- `POST /stop/{session_id}`: Stop running session
- `GET /history`: Automation history

### Product Management (`/api/products/`)
- `GET /`: List user products
- `POST /`: Add new product
- `PUT /{id}`: Update product
- `DELETE /{id}`: Remove product
- `POST /bulk-import`: Import products from CSV

### System Settings (`/api/settings/`)
- `GET /`: Get all settings
- `PUT /`: Update settings
- `GET /{setting_name}`: Get specific setting

## 🤖 Automation Services

### Core Worker (`services/automation_tasks/core_worker.py`)
Main automation controller that orchestrates the entire process:
```python
async def run_automation(products, account, address_config):
    """
    Main automation workflow:
    1. Initialize browser session
    2. Authenticate with Flipkart account
    3. Process each product (add to cart, verify quantity)
    4. Proceed to checkout (if enabled)
    5. Complete order placement
    6. Clean up resources
    """
```

### Cart Manager (`services/automation_tasks/cart_manager.py`)
Handles product addition and quantity management:
- Enhanced retry mechanisms (5 attempts for quantity verification)
- Multiple selector strategies for reliability
- Progressive wait times for UI stability
- Comprehensive error logging

### Checkout Handler (`services/automation_tasks/checkout_handler.py`)
Manages the complete checkout process:
- Dynamic address validation from addresses table
- Multiple payment method support
- Order confirmation verification
- Error recovery and retry logic

### Automation Worker (`services/automation_worker.py`)
High-level orchestration service:
- Session management and tracking
- Resource allocation and cleanup
- Progress monitoring and updates
- Error handling and recovery

## 🔄 Background Tasks & Queues

### Celery Integration
```python
# Background task processing
from celery import Celery

celery_app = Celery(
    "automation_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task
def process_automation_session(session_data):
    # Long-running automation task
    return automation_result
```

### Task Types
- **Automation Sessions**: Product ordering workflows
- **Price Monitoring**: Periodic price checks
- **Account Validation**: Credential verification
- **Cleanup Tasks**: Resource management

## 📧 Email Notifications

### Service Configuration
```python
# email_service.py
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailService:
    def send_automation_complete(user_email, session_details):
        # Send completion notification
        
    def send_error_alert(admin_email, error_details):
        # Send error notifications
```

### Notification Types
- **Automation Completion**: Success/failure notifications
- **Price Alerts**: Target price reached notifications
- **System Alerts**: Error and maintenance notifications
- **Account Status**: Account validation results

## 🐛 Error Handling & Logging

### Logging Configuration
```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('automation.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### Error Categories
- **Authentication Errors**: Login failures, token expiry
- **Automation Errors**: Product unavailability, cart issues
- **System Errors**: Database connectivity, service failures
- **User Errors**: Invalid input, permission denied

## 🧪 Testing

### Unit Tests
```bash
# Run unit tests
pytest tests/unit/

# Run with coverage
pytest --cov=./ tests/
```

### Integration Tests
```bash
# Test API endpoints
pytest tests/integration/

# Test automation workflows
pytest tests/automation/
```

### Test Structure
```
tests/
├── unit/
│   ├── test_auth.py
│   ├── test_automation.py
│   └── test_database.py
├── integration/
│   ├── test_api_endpoints.py
│   └── test_workflows.py
└── fixtures/
    ├── sample_data.py
    └── mock_responses.py
```

## 🚀 Deployment

### Production Setup
```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Docker Setup
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables
- Set `DATABASE_URL` for production database
- Configure `SECRET_KEY` for JWT security
- Set `SMTP_*` variables for email notifications
- Configure `REDIS_URL` for Celery tasks

## 📈 Performance & Monitoring

### Performance Optimizations
- **Database Connection Pooling**: SQLAlchemy connection management
- **Async Operations**: FastAPI async/await for non-blocking I/O
- **Caching**: Redis caching for frequently accessed data
- **Background Processing**: Celery for long-running tasks

### Monitoring
- **Health Checks**: `/health` endpoint for service monitoring
- **Metrics Collection**: Request/response time tracking
- **Error Tracking**: Comprehensive error logging
- **Resource Usage**: Memory and CPU monitoring

## 🔧 Maintenance

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

### Backup & Recovery
- **Database Backups**: Automated PostgreSQL dumps
- **Configuration Backups**: Environment and settings backup
- **Log Rotation**: Automated log file management
- **Disaster Recovery**: Complete system restoration procedures

---

**📝 Last Updated**: January 2024  
**🔄 API Version**: v1.0  
**👨‍💻 Maintained by**: Backend Development Team

For API testing and interactive documentation, visit: http://localhost:8000/docs
