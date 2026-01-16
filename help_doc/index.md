# 📚 Flipkart Automation System - Documentation Index

Welcome to the comprehensive documentation for the Flipkart Automation System. This folder contains all the documentation you need to understand, setup, and use the system effectively.

## 📖 Documentation Files

### 🚀 Getting Started
- **[Quick Start Guide](./quick_start_guide.md)** - Get up and running in 5 minutes
- **[Full Setup Guide](./full_setup_guide.md)** - End-to-end Linux setup (packages, PostgreSQL, backend, frontend)
- **[Setup Complete Guide](./SETUP_COMPLETE.md)** - Complete system overview and setup details

### 🔧 Technical Documentation
- **[API Endpoints](./api_endpoints.md)** - Complete API reference with curl examples
- **[User Creation API](./user_creation_api.md)** - Detailed curl commands for user management
- **[Automation Workflow](./automation_workflow.md)** - Detailed workflow documentation for each segment
- **[Full README](./README.md)** - Comprehensive project documentation

## 🎯 Quick Navigation

### For New Users
1. Start with **[Quick Start Guide](./quick_start_guide.md)**
2. Review **[Setup Complete Guide](./SETUP_COMPLETE.md)** for full details
3. Use **[API Endpoints](./api_endpoints.md)** for integration

### For Developers
1. **[README.md](./README.md)** - Architecture and development setup
2. **[Automation Workflow](./automation_workflow.md)** - Detailed workflow documentation
3. **[API Endpoints](./api_endpoints.md)** - All available endpoints
4. **[User Creation API](./user_creation_api.md)** - User management via curl

### For Administrators
1. **[Setup Complete Guide](./SETUP_COMPLETE.md)** - System administration
2. **[User Creation API](./user_creation_api.md)** - Creating users via API
3. **[Quick Start Guide](./quick_start_guide.md)** - Troubleshooting

## 🔗 External Links

- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Health Check**: http://localhost:8000/health

## 🆘 Need Help?

### Quick Solutions
- **Permission Denied**: `chmod +x start.sh`
- **Services Not Starting**: Check [Quick Start Guide](./quick_start_guide.md) troubleshooting
- **API Issues**: Refer to [API Endpoints](./api_endpoints.md) error responses

### Common Commands
```bash
# Start system
./start.sh

# Check services
curl -s http://localhost:8000/health

# Create user (admin only)
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && \
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"username": "newuser", "email": "user@example.com", "password": "password123", "is_admin": false}'
```

## 📋 System Requirements

- **PostgreSQL**: Database server
- **Node.js 18+**: Frontend development
- **Python 3.11+**: Backend services
- **Modern Browser**: For web interface

## 🔐 Default Credentials

- **Username**: `admin`
- **Password**: `admin123`
- **Database**: `flipkart_automation`
- **DB User**: `flipkart_admin`
- **DB Password**: `flipkart_secure_2024`

## 📊 System Status

### Services
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Database**: localhost:5432

### Features
- ✅ User Authentication (JWT)
- ✅ Product Management
- ✅ Order Tracking
- ✅ Flipkart Account Management
- ✅ Automation Sessions
- ✅ Admin User Management
- ✅ Price Monitoring
- ✅ Dashboard Analytics

## 🗂️ File Organization

```
help_doc/
├── index.md                 # This file - documentation index
├── quick_start_guide.md     # 5-minute setup guide
├── SETUP_COMPLETE.md        # Complete system overview
├── README.md                # Full project documentation
├── api_endpoints.md         # Complete API reference
└── user_creation_api.md     # User management via curl
```

---

**📝 Documentation maintained by the development team**  
**🔄 Last updated: January 2024**  
**📧 For support: Check troubleshooting sections in respective guides** 