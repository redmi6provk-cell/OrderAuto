# 🛒 Flipkart Automation System

A comprehensive automated ordering system for Flipkart with multi-account management, price monitoring, and seamless order placement.

## 📚 Documentation

All documentation has been organized in the `help_doc/` folder for better management:

### 🚀 Quick Start
- **[📖 Documentation Index](./help_doc/index.md)** - Complete documentation overview
- **[⚡ Quick Start Guide](./help_doc/quick_start_guide.md)** - Get running in 5 minutes
- **[🛠️ Full Setup Guide](./help_doc/full_setup_guide.md)** - End-to-end Linux setup (packages, PostgreSQL, backend, frontend)
- **[🔧 Setup Complete Guide](./help_doc/SETUP_COMPLETE.md)** - Full system details

### 🔄 Workflow Documentation
- **[🤖 Automation Workflow](./help_doc/automation_workflow.md)** - Detailed workflow for each automation segment
- **[🐍 Backend Documentation](./backend/README.md)** - FastAPI backend architecture & API docs
- **[⚛️ Frontend Documentation](./app/README.md)** - Next.js dashboard & UI components

### 🔌 API Reference
- **[📋 API Endpoints](./help_doc/api_endpoints.md)** - Complete API reference
- **[👤 User Creation API](./help_doc/user_creation_api.md)** - curl commands for user management

## ⚡ Quick Commands

### Start System
```bash
chmod +x start.sh && ./start.sh
```

### Create User (Admin Only)
```bash
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && \
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"username": "newuser", "email": "user@example.com", "password": "password123", "is_admin": false}'
```

## 🔗 Access Points

- **Frontend Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Login**: `admin` / `admin123`

## 📁 Project Structure

```
flipkart-automation/
├── help_doc/                # 📚 All documentation files
│   ├── index.md             # Documentation index
│   ├── quick_start_guide.md # 5-minute setup
│   ├── api_endpoints.md     # API reference
│   └── ...                  # More guides
├── backend/                 # Python FastAPI backend
├── app/                     # Next.js frontend
├── automation/              # Playwright scripts
└── start.sh                 # Automated startup
```

## 🆘 Need Help?

1. **Check Documentation**: Start with [help_doc/index.md](./help_doc/index.md)
2. **Permission Issues**: `chmod +x start.sh`
3. **Service Issues**: See [Quick Start Guide](./help_doc/quick_start_guide.md)

---

**📖 For complete documentation, visit the [help_doc/](./help_doc/) folder** 