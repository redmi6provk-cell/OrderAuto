# User Creation API Documentation

## Overview
This document provides curl commands for creating users in the Flipkart Automation System. Only administrators can create new users through the secure API endpoint.

## Prerequisites
- Admin credentials: `admin` / `admin123`
- Backend API running on `http://localhost:8000`
- Valid admin JWT token

## Authentication Flow

### Step 1: Admin Login
First, authenticate as an admin to get the JWT token:

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

### Step 2: Extract Token
Copy the `access_token` value from the response for use in the next step.

## User Creation Commands

### Create Regular User
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "password123",
    "is_admin": false
  }'
```

### Create Admin User
```bash
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "username": "newadmin",
    "email": "newadmin@example.com",
    "password": "admin456",
    "is_admin": true
  }'
```

## One-Liner Commands (Automated)

### Create Regular User (One Command)
```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && \
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "test123",
    "is_admin": false
  }'
```

### Create Admin User (One Command)
```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && \
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "newadmin",
    "email": "newadmin@example.com",
    "password": "admin456",
    "is_admin": true
  }'
```

## Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `username` | string | Yes | Unique username (3-50 characters) |
| `email` | string | Yes | Valid email address |
| `password` | string | Yes | Password (minimum 6 characters) |
| `is_admin` | boolean | No | Grant admin privileges (default: false) |

## Response Examples

### Successful User Creation
```json
{
  "id": 2,
  "username": "newuser",
  "email": "newuser@example.com",
  "is_active": true,
  "is_admin": false,
  "created_at": "2024-01-01T12:00:00"
}
```

### Error Responses

#### Unauthorized (No Token)
```json
{
  "detail": "Not authenticated"
}
```

#### Forbidden (Non-Admin User)
```json
{
  "detail": "Only admins can create new users"
}
```

#### User Already Exists
```json
{
  "detail": "Username or email already exists"
}
```

#### Invalid Input
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

## Testing Commands

### Test User Creation
```bash
# Create a test user
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && \
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "testuser_'$(date +%s)'",
    "email": "test'$(date +%s)'@example.com",
    "password": "test123",
    "is_admin": false
  }'
```

### Test User Login
```bash
# Test if the created user can login
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'
```

## Security Notes

- ⚠️ Only authenticated admins can create users
- 🔒 JWT tokens expire after 24 hours
- 🛡️ Passwords are hashed with bcrypt
- 📧 Email addresses must be unique
- 👤 Usernames must be unique
- 🔑 Admin privileges should be granted carefully

## Troubleshooting

### Common Issues

1. **Permission Denied Error**
   ```bash
   chmod +x start.sh
   ```

2. **Token Extraction Fails**
   ```bash
   # Check login response manually
   curl -X POST "http://localhost:8000/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "admin123"}'
   ```

3. **API Not Responding**
   ```bash
   # Check if backend is running
   curl -s http://localhost:8000/health
   ```

4. **Invalid JSON Format**
   - Ensure proper JSON escaping
   - Use single quotes for shell, double quotes for JSON
   - Validate JSON syntax

### Debug Commands

```bash
# Check API status
curl -s http://localhost:8000/health

# Test admin login
curl -v -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Test unauthorized access
curl -v -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test123"}'
```

## Related Documentation

- [Setup Complete Guide](../SETUP_COMPLETE.md)
- [API Documentation](http://localhost:8000/docs)
- [Frontend User Management](../app/dashboard/users/)

---

**Last Updated:** January 2024  
**API Version:** 1.0.0  
**Endpoint:** `/api/auth/register` (Admin Protected) 