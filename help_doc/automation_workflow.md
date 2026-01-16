# 🔄 Automation Workflow Documentation

## Overview

This document provides comprehensive documentation for each workflow segment of the Flipkart Automation System. Each workflow is designed to handle specific aspects of the automated ordering process with robust error handling and retry mechanisms.

---

## 🔐 1. Authentication Workflow

### Purpose
Handles secure login to Flipkart accounts with multi-account support and session management.

### Components
- **Location**: `backend/services/automation_tasks/core_worker.py`
- **Database**: `flipkart_accounts` table
- **API Endpoints**: `/api/accounts/`

### Workflow Steps

#### 1.1 Account Validation
```python
# Validates account credentials and status
def validate_account(account_data):
    - Check account is_active status
    - Verify credentials format
    - Ensure account is not currently in use
    - Return validation result
```

#### 1.2 Browser Session Initialization
```python
# Creates new browser session
def initialize_browser_session():
    - Launch Playwright browser instance
    - Set user agent and viewport
    - Configure proxy if enabled
    - Navigate to Flipkart login page
```

#### 1.3 Login Process
```python
# Performs actual login with retry mechanism
def perform_login(account_credentials):
    - Navigate to login page
    - Enter username/email
    - Enter password
    - Handle OTP if required
    - Verify successful login
    - Store session cookies
```

#### 1.4 Session Management
- **Session Duration**: Configurable timeout
- **Concurrent Sessions**: Controlled by `max_concurrent_sessions`
- **Session Recovery**: Automatic retry on failure
- **Security**: Secure cookie storage and JWT tokens

### Error Handling
- **Invalid Credentials**: Marks account as inactive
- **OTP Timeout**: Retries with exponential backoff
- **Rate Limiting**: Implements proxy rotation
- **Network Issues**: Auto-retry with different proxy

---

## 🏠 2. Address Management Workflow

### Purpose
Manages multiple delivery addresses with dynamic validation and selection for automated orders.

### Components
- **Frontend**: `app/dashboard/addresses/`
- **Backend**: `backend/routers/addresses.py`
- **Database**: `addresses` table
- **Integration**: `checkout_handler.py`

### Workflow Steps

#### 2.1 Address Configuration
```python
# Address data structure
class Address:
    - name: string              # Display name
    - description: string       # Internal description
    - address_template: string  # Address keywords for validation
    - office_no_min: int       # Office number range start
    - office_no_max: int       # Office number range end
    - name_postfix: string     # Name validation keyword
    - phone_prefix: string     # Phone number prefix
    - pincode: string          # PIN code for validation
    - is_active: boolean       # Active status
    - is_default: boolean      # Default selection
```

#### 2.2 Address Selection Process
```python
# During automation startup
def select_address_for_automation():
    - Load user's active addresses
    - Check for specified address_id in request
    - Fallback to default address if none specified
    - Validate address configuration completeness
    - Return selected address or error
```

#### 2.3 Dynamic Address Validation
```python
# During checkout process
def validate_address_on_checkout():
    - Extract current address from Flipkart page
    - Check name_postfix match
    - Verify pincode match
    - Validate address_template keywords
    - Generate office number within range
    - Format phone number with prefix
```

#### 2.4 Address Management API
- **GET /api/addresses/**: List all addresses
- **POST /api/addresses/**: Create new address
- **PUT /api/addresses/{id}**: Update address
- **DELETE /api/addresses/{id}**: Soft delete address
- **POST /api/addresses/{id}/set-default**: Set as default

### Migration from System Settings
The system has been migrated from storing address data in `system_settings` to dedicated `addresses` table:
- **Old**: Single address in system_settings
- **New**: Multiple addresses with CRUD operations
- **Benefits**: Multi-address support, better organization, user-specific addresses

---

## 🛒 3. Cart Management Workflow

### Purpose
Handles product addition, quantity verification, and cart management with robust retry mechanisms.

### Components
- **Location**: `backend/services/automation_tasks/cart_manager.py`
- **Integration**: `core_worker.py`, `batch_manager.py`
- **Database**: `products`, `automation_sessions`

### Workflow Steps

#### 3.1 Product Navigation
```python
# Navigate to product page with retry
def navigate_to_product(product_url):
    - Validate product URL format
    - Navigate with retry mechanism (3 attempts)
    - Wait for page load completion
    - Verify product page elements
    - Return navigation status
```

#### 3.2 Product Addition Process
```python
# Add product to cart with verification
def add_product_to_cart():
    - Locate "Add to Cart" button with multiple selectors
    - Click add button with retry mechanism
    - Wait for cart update (2-3 seconds)
    - Verify product was added successfully
    - Handle "Buy Now" vs "Add to Cart" variations
```

#### 3.3 Enhanced Quantity Verification
```python
# Robust quantity checking with 5 retry attempts
def _verify_actual_quantity():
    attempts = 5
    selectors = [
        'input[title="Quantity"]',           # Primary selector
        'input[data-testid="quantity"]',     # Alternative
        '.quantity-input input',             # Fallback
        'input[type="number"]'               # Generic
    ]
    
    for attempt in range(attempts):
        - Check element visibility
        - Extract quantity value
        - Validate range (1-99)
        - Return if valid, retry if invalid
        - Progressive wait times: 1s, 2s, 3s, 4s, 5s
```

#### 3.4 Quantity Adjustment Process
```python
# Enhanced quantity adjustment with retry
def _adjust_product_quantity(target_quantity):
    max_attempts = 3
    
    for attempt in range(max_attempts):
        - Get current quantity
        - Calculate difference
        - Use plus/minus buttons to adjust
        - Verify after each click
        - Wait 1.0s between operations
        - Triple-verify final quantity
```

#### 3.5 Cart Validation
```python
# Final cart verification
def validate_cart_contents():
    - Navigate to cart page
    - Verify all products present
    - Check quantities match requirements
    - Validate pricing information
    - Ensure cart is ready for checkout
```

### Enhanced Error Handling
- **Navigation Failures**: 3 retry attempts with different wait times
- **Button Click Issues**: Multiple selector strategies with fallbacks
- **Quantity Mismatches**: 5 verification attempts with progressive delays
- **Cart Update Delays**: Increased wait times for UI stability
- **Element Detection**: Enhanced selectors for different page states

---

## 💳 4. Checkout Workflow

### Purpose
Handles the complete checkout process from cart to order confirmation with address validation and payment processing.

### Components
- **Location**: `backend/services/automation_tasks/checkout_handler.py`
- **Integration**: `core_worker.py`, address management
- **Configuration**: `enable_checkout=True` by default

### Workflow Steps

#### 4.1 Checkout Initialization
```python
# Start checkout process
def initiate_checkout():
    - Navigate to cart page
    - Locate "Place Order" or "Proceed to Buy" button
    - Click checkout button with multiple selectors
    - Wait for address selection page
    - Verify checkout page loaded
```

#### 4.2 Address Selection & Validation
```python
# Dynamic address validation from addresses table
def validate_and_select_address(address_config):
    - Extract current address from page
    - Validate using address_config parameters:
        * name_postfix match
        * pincode verification  
        * address_template keywords
    - Generate office number within range
    - Format phone with prefix
    - Select correct address or add new one
```

#### 4.3 Order Summary Processing
```python
# Review and validate order details
def process_order_summary():
    - Verify product quantities and prices
    - Check delivery address details
    - Validate total amount against limits
    - Review delivery options
    - Confirm order summary accuracy
```

#### 4.4 Payment Method Selection
```python
# Select Cash on Delivery payment
def select_payment_method():
    - Navigate to payment options
    - Select "Cash on Delivery" option
    - Verify payment method selection
    - Handle payment confirmation
```

#### 4.5 Order Placement & Confirmation
```python
# Final order placement
def place_order_and_confirm():
    - Click final "Place Order" button
    - Wait for order processing
    - Capture order confirmation details
    - Extract order ID and tracking info
    - Verify successful order placement
```

### Multiple Selector Strategies
```python
# Enhanced selector reliability
checkout_selectors = {
    'place_order': [
        'button[data-testid="place-order"]',
        '.place-order-button',
        'button:contains("Place Order")',
        'input[value="Place Order"]'
    ],
    'address_selection': [
        '.address-item.selected',
        '[data-testid="address-card"]',
        '.delivery-address-item'
    ]
}
```

### Error Handling & Recovery
- **Page Load Failures**: Retry navigation with different approaches
- **Address Validation Errors**: Fallback to manual address entry
- **Payment Processing Issues**: Multiple payment method attempts
- **Order Confirmation Timeout**: Extended wait with verification
- **Redirect Handling**: Automatic detection and recovery

---

## 🤖 5. Automation Worker Workflow

### Purpose
Orchestrates the complete automation process from initialization to completion with comprehensive error handling and session management.

### Components
- **Main Controller**: `backend/services/automation_worker.py`
- **Core Logic**: `backend/services/automation_tasks/core_worker.py`
- **Database Integration**: Session tracking, logging, status updates

### Workflow Steps

#### 5.1 Automation Session Initialization
```python
# Session setup and validation
async def start_automation_session(request_data):
    - Validate user permissions
    - Check concurrent session limits
    - Load account and address configurations
    - Initialize session tracking
    - Set automation parameters
    - Return session_id for tracking
```

#### 5.2 Request Processing & Validation
```python
# Process automation request
def process_automation_request():
    - Validate products list and quantities
    - Check account availability and status
    - Verify address configuration (address_id)
    - Load system settings and limits
    - Prepare automation parameters
```

#### 5.3 Core Automation Execution
```python
# Main automation workflow
async def execute_automation_workflow():
    enable_checkout = True  # Default checkout enabled
    
    try:
        # 1. Authentication Phase
        session = await authenticate_account(account_data)
        
        # 2. Cart Management Phase  
        for product in products_list:
            await add_product_to_cart(product, session)
            await verify_quantities(product, session)
        
        # 3. Checkout Phase (if enabled)
        if enable_checkout:
            await process_checkout(address_config, session)
            await place_order(session)
            
        # 4. Session Cleanup
        await cleanup_session(session)
        
    except Exception as e:
        await handle_automation_error(e, session)
```

#### 5.4 Progress Tracking & Updates
```python
# Real-time status updates
def update_automation_progress():
    - Track current workflow phase
    - Update progress percentage
    - Log detailed step information
    - Notify frontend via WebSocket/polling
    - Store session history for analysis
```

#### 5.5 Error Recovery & Retry Logic
```python
# Comprehensive error handling
def handle_automation_errors():
    - Network connectivity issues: Retry with exponential backoff
    - Authentication failures: Mark account for review
    - Product unavailability: Skip and continue with available items
    - Checkout errors: Attempt recovery or graceful degradation
    - System limits exceeded: Queue for later processing
```

### Session Management
- **Concurrent Limits**: Configured via `max_concurrent_sessions`
- **Session Timeout**: Automatic cleanup after `order_timeout`
- **Resource Management**: Browser instance cleanup
- **State Persistence**: Session data stored for recovery
- **Monitoring**: Real-time session status tracking

### Integration Points
- **Address Management**: Dynamic loading from addresses table
- **Account Management**: Multi-account support with rotation
- **Product Management**: Batch processing with individual verification
- **Notification System**: Status updates and completion notifications
- **Audit Trail**: Comprehensive logging for compliance and debugging

---

## 📊 6. Batch Management Workflow

### Purpose
Handles multiple concurrent automation sessions with resource management and load balancing.

### Components
- **Location**: `backend/services/batch_manager.py`
- **Integration**: Queue management, resource allocation
- **Monitoring**: Performance metrics and session analytics

### Key Features
- **Queue Management**: FIFO processing with priority support
- **Resource Allocation**: Dynamic browser instance management
- **Load Balancing**: Distributed processing across available resources
- **Failure Recovery**: Automatic retry and error escalation
- **Performance Monitoring**: Real-time metrics and analytics

---

## 🔧 Configuration & Settings

### System Settings
Managed via `system_settings` table (general automation settings only):
- `max_concurrent_sessions`: Maximum parallel automation sessions
- `default_check_interval`: Polling interval for status updates
- `max_login_attempts`: Login retry limit before marking account inactive
- `order_timeout`: Maximum time to wait for order completion
- `proxy_rotation_enabled`: Enable/disable proxy rotation for requests

### Address-Specific Settings
Managed via `addresses` table (per-address configuration):
- Address validation parameters
- Office number generation ranges
- Phone number formatting rules
- Default address selection

---

## 📈 Monitoring & Analytics

### Session Tracking
- Real-time session status monitoring
- Performance metrics collection
- Error rate analysis
- Success rate tracking
- Resource utilization monitoring

### Logging & Audit Trail
- Comprehensive operation logging
- Error tracking and categorization
- Performance benchmarking
- User activity audit trail
- Compliance and security logging

---

## 🚀 Performance Optimizations

### Retry Mechanisms
- **Progressive Delays**: Exponential backoff for retry attempts
- **Smart Fallbacks**: Multiple selector strategies for reliability
- **Circuit Breakers**: Automatic failure isolation and recovery
- **Resource Pooling**: Efficient browser instance management

### Reliability Improvements
- **Enhanced Wait Times**: Proper delays for UI stability
- **Multiple Verification**: Triple-check critical operations
- **Fallback Selectors**: Comprehensive element detection strategies
- **Error Context**: Detailed error information for debugging

---

**📝 Last Updated**: 12 Sept, 2025  
**🔄 Version**: 2.0 with multi-address support and enhanced error handling  
**👨‍💻 Maintained by**: Vulncure
