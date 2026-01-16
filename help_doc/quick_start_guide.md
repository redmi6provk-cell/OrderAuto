# Quick Start Guide - Flipkart Automation System

## 🚀 Get Started in 5 Minutes

### Prerequisites
- PostgreSQL installed and running
- Node.js 18+
- Python 3.11+

### Step 1: Start the System
```bash
# Fix permissions if needed
chmod +x start.sh

# Start everything
./start.sh
```

### Step 2: Access the Dashboard
- **URL**: http://localhost:3000/login
- **Username**: `admin`
- **Password**: `admin123`

### Step 3: Create Your First User (Optional)
```bash
# One-liner to create a new user
TOKEN=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | \
  grep -o '"access_token":"[^"]*"' | cut -d'"' -f4) && \
curl -X POST "http://localhost:8000/api/auth/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "username": "myuser",
    "email": "myuser@example.com",
    "password": "mypassword",
    "is_admin": false
  }'
```

## ✅ System Status Check

### Check Services
```bash
# Frontend (should return HTML)
curl -s http://localhost:3000 | head -c 100

# Backend API (should return JSON)
curl -s http://localhost:8000/health

# Database (should connect)
psql -h localhost -U flipkart_admin -d flipkart_automation -c "SELECT 1;"
```

### Test Login
```bash
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

## 🎯 Next Steps

1. **Add Flipkart Accounts**: Dashboard → Flipkart Accounts
2. **Configure Products**: Dashboard → Products  
3. **Set Up Automation**: Dashboard → Automation
4. **Create Team Members**: Dashboard → User Management (Admin only)

## 🔧 Troubleshooting

### Permission Denied
```bash
chmod +x start.sh
```

### Services Not Starting
```bash
# Check PostgreSQL
sudo systemctl status postgresql
sudo systemctl start postgresql

# Check ports
lsof -i :3000  # Frontend
lsof -i :8000  # Backend
```

### Database Issues
```bash
# Test connection
pg_isready -h localhost -p 5432

# Reset database
cd backend && source venv/bin/activate && python database_schema.py --drop
cd backend && source venv/bin/activate && python database_schema.py
```

## 📖 Full Documentation

- **[Setup Complete Guide](./SETUP_COMPLETE.md)** - Complete system overview
- **[User Creation API](./user_creation_api.md)** - curl commands for user management
- **[Full README](./README.md)** - Detailed documentation

---

**Need Help?** Check the troubleshooting section or refer to the full documentation files. 