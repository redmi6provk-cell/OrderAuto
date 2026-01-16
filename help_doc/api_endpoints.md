# API Endpoints Documentation

## Base URL
```
http://localhost:8000/api
```

## Authentication
All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <your_jwt_token>
```

## Authentication Endpoints

### POST /auth/login
Login and get JWT token.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@flipkart-automation.com",
    "is_active": true,
    "is_admin": true,
    "created_at": "2024-01-01T00:00:00"
  }
}
```

### POST /auth/register
Create new user (admin only).

**Request:**
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "username": "newuser",
    "email": "user@example.com",
    "password": "password123",
    "is_admin": false
  }'
```

### GET /auth/me
Get current user information.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/auth/me" \
  -H "Authorization: Bearer <token>"
```

### POST /auth/refresh
Refresh JWT token.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/auth/refresh" \
  -H "Authorization: Bearer <token>"
```

## Products Endpoints

### GET /products
Get all products.

**Parameters:**
- `skip` (optional): Number of items to skip
- `limit` (optional): Number of items to return
- `active_only` (optional): Filter active products only

**Request:**
```bash
curl -X GET "http://localhost:8000/api/products?limit=10&active_only=true" \
  -H "Authorization: Bearer <token>"
```

### POST /products
Create new product.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/products" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "product_link": "https://www.flipkart.com/product/xyz",
    "quantity": 1
  }'
```

### GET /products/{id}
Get specific product.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/products/1" \
  -H "Authorization: Bearer <token>"
```

### PUT /products/{id}
Update product.

**Request:**
```bash
curl -X PUT "http://localhost:8000/api/products/1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "is_active": true
  }'
```

### DELETE /products/{id}
Delete product.

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/products/1" \
  -H "Authorization: Bearer <token>"
```


## Orders Endpoints

### GET /orders
Get all orders.

**Parameters:**
- `skip` (optional): Number of items to skip
- `limit` (optional): Number of items to return
- `status_filter` (optional): Filter by status
- `product_id` (optional): Filter by product ID

**Request:**
```bash
curl -X GET "http://localhost:8000/api/orders?status=placed&limit=10" \
  -H "Authorization: Bearer <token>"
```

### POST /orders
Create new order.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/orders" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "product_id": 1,
    "flipkart_user_id": 1,
    "product_name": "Sample Product",
    "actual_price": 899.99,
    "quantity": 1,
    "delivery_address": "123 Main St, City"
  }'
```

### GET /orders/{id}
Get specific order.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/orders/1" \
  -H "Authorization: Bearer <token>"
```

### PUT /orders/{id}
Update order.

**Request:**
```bash
curl -X PUT "http://localhost:8000/api/orders/1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "status": "shipped",
    "tracking_id": "TRK123456789",
    "notes": "Package dispatched"
  }'
```

### DELETE /orders/{id}
Delete order.

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/orders/1" \
  -H "Authorization: Bearer <token>"
```

 

## Flipkart Users Endpoints

### GET /users/flipkart
Get all Flipkart user accounts.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/users/flipkart" \
  -H "Authorization: Bearer <token>"
```

### POST /users/flipkart
Create new Flipkart user account.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/users/flipkart" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "email": "flipkart@example.com",
    "password": "flipkart123",
    "proxy_config": {
      "server": "proxy.example.com",
      "port": 8080,
      "username": "proxyuser",
      "password": "proxypass"
    }
  }'
```

### GET /users/flipkart/{id}
Get specific Flipkart user account.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/users/flipkart/1" \
  -H "Authorization: Bearer <token>"
```

### PUT /users/flipkart/{id}
Update Flipkart user account.

**Request:**
```bash
curl -X PUT "http://localhost:8000/api/users/flipkart/1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "is_active": true,
    "cookies": "session_cookies_here"
  }'
```

### DELETE /users/flipkart/{id}
Delete Flipkart user account.

**Request:**
```bash
curl -X DELETE "http://localhost:8000/api/users/flipkart/1" \
  -H "Authorization: Bearer <token>"
```

### POST /users/flipkart/{id}/test-login
Test login for Flipkart user account.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/users/flipkart/1/test-login" \
  -H "Authorization: Bearer <token>"
```

## Automation Endpoints

### GET /automation/sessions
Get all automation sessions.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/automation/sessions" \
  -H "Authorization: Bearer <token>"
```

### POST /automation/sessions
Create and start new automation session.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/automation/sessions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "session_name": "Daily Automation",
    "config": {
      "max_concurrent": 3,
      "check_interval": 300
    }
  }'
```

### GET /automation/sessions/{id}
Get specific automation session.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/automation/sessions/1" \
  -H "Authorization: Bearer <token>"
```

### PUT /automation/sessions/{id}
Update automation session.

**Request:**
```bash
curl -X PUT "http://localhost:8000/api/automation/sessions/1" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "status": "stopped"
  }'
```

### POST /automation/sessions/{id}/stop
Stop running automation session.

**Request:**
```bash
curl -X POST "http://localhost:8000/api/automation/sessions/1/stop" \
  -H "Authorization: Bearer <token>"
```

### GET /automation/sessions/{id}/logs
Get logs for automation session.

**Request:**
```bash
curl -X GET "http://localhost:8000/api/automation/sessions/1/logs" \
  -H "Authorization: Bearer <token>"
```

 


## Health Check Endpoints

### GET /
Root endpoint.

**Request:**
```bash
curl -X GET "http://localhost:8000/"
```

### GET /health
Health check endpoint.

**Request:**
```bash
curl -X GET "http://localhost:8000/health"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Error Responses

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Only admins can create new users"
}
```

### 404 Not Found
```json
{
  "detail": "Item not found"
}
```

### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

## Interactive API Documentation

Visit http://localhost:8000/docs for Swagger UI documentation with interactive testing capabilities.

---

**Last Updated:** January 2024  
**API Version:** 1.0.0 