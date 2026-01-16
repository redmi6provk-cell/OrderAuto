# 🛒 Flipkart Automation System

A comprehensive automated ordering system for Flipkart with multi-account management, price monitoring, and seamless order placement using Cash on Delivery.

## 🚀 Features

- **Multi-Account Management**: Handle multiple Flipkart accounts simultaneously
- **Order Automation**: Automated order placement with COD
- **Proxy Support**: Built-in proxy rotation for account safety
- **Real-time Dashboard**: Modern web interface with live updates
- **Email Integration**: Gmail integration for OTP handling
- **Database Tracking**: Complete order and session tracking
- **Scalable Architecture**: Built for high-volume automation

## 🏗️ Architecture

- **Frontend**: Next.js 14 with TypeScript and Tailwind CSS
- **Backend**: FastAPI with asyncio support
- **Database**: PostgreSQL with dedicated user and connection pooling
- **Automation**: Playwright for reliable browser automation
- **Environment**: Python virtual environment for isolation

## 📋 Prerequisites

- **Node.js 18+** for frontend development
- **Python 3.11+** for backend services
- **PostgreSQL 15+** database server
- **Git** for version control

## 🔧 Installation

### Quick Start (Automated)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd flipkart-automation
   ```

2. **Run the automated setup**:
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

### Manual Installation

1. **Set up PostgreSQL**:
   ```bash
   # Start PostgreSQL service
   sudo systemctl start postgresql
   
   # The setup script creates:
   # - User: flipkart_admin
   # - Password: flipkart_secure_2024
   # - Database: flipkart_automation
   ```

2. **Set up the backend**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   
   # Initialize database
   python database_schema.py
   ```

3. **Set up the frontend**:
   ```bash
   npm install
   ```

4. **Start the services**:
   ```bash
   # Terminal 1: Backend (from backend directory)
   source venv/bin/activate
   python main.py
   
   # Terminal 2: Frontend (from root directory)
   npm run dev
   ```

## 🎯 Default Credentials

### Application Login
- **Username**: `admin`
- **Password**: `admin123`
- **Email**: `admin@flipkart-automation.com`

### Database Access
- **Host**: `localhost:5432`
- **Database**: `flipkart_automation`
- **User**: `flipkart_admin`
- **Password**: `flipkart_secure_2024`

## 📊 Database Schema

The system uses the following main tables:

- **users**: Internal application users
- **flipkart_users**: Flipkart account credentials and cookies
- **flipkart_products**: Product configurations with price caps
- **flipkart_orders**: Order tracking and status
- **automation_sessions**: Session management and logging
- **system_settings**: Global configuration

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Get current user
- `POST /api/auth/refresh` - Refresh token

### Products
- `GET /api/products` - List products
- `POST /api/products` - Create product
- `PUT /api/products/{id}` - Update product
- `DELETE /api/products/{id}` - Delete product
- `POST /api/products/{id}/check-price` - Check current price

### Orders
- `GET /api/orders` - List orders
- `POST /api/orders` - Create order
 

### Flipkart Accounts
- `GET /api/users/flipkart` - List accounts
- `POST /api/users/flipkart` - Add account
- `PUT /api/users/flipkart/{id}` - Update account
- `POST /api/users/flipkart/{id}/test-login` - Test login

### Automation
- `GET /api/automation/sessions` - List sessions
- `POST /api/automation/sessions` - Start session
- `POST /api/automation/sessions/{id}/stop` - Stop session

## 🛠️ Configuration

### Environment Variables

The system uses `backend/.env` file:

```env
DATABASE_URL=postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation
SECRET_KEY=flipkart_jwt_secret_key_2024_secure
REDIS_URL=redis://localhost:6379
GMAIL_EMAIL=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
```

### System Settings

Configure via the web interface or directly in the database:

- `max_concurrent_sessions`: Maximum automation sessions
- `default_check_interval`: Price check frequency (seconds)
- `max_login_attempts`: Account lockout threshold
- `order_timeout`: Order placement timeout
- `proxy_rotation_enabled`: Enable/disable proxy rotation

## 🔐 Security Features

- JWT-based authentication
- Password hashing with bcrypt
- Dedicated database user with limited privileges
- Input validation and sanitization
- SQL injection prevention
- CORS protection

## 📱 Frontend Features

- **Responsive Design**: Mobile-first approach
- **Real-time Updates**: Live dashboard with auto-refresh
- **Modern UI**: Clean, intuitive interface with Tailwind CSS
- **Form Validation**: Client-side and server-side validation
- **Error Handling**: User-friendly error messages
- **Loading States**: Smooth user experience

## 🤖 Automation Features

- **Price Monitoring**: Continuous price checking with Playwright
- **Account Rotation**: Automatic account switching
- **Proxy Support**: IP rotation for anonymity
- **Session Management**: Concurrent session handling
- **Error Recovery**: Automatic retry mechanisms
- **Logging**: Comprehensive activity tracking

## 📈 Monitoring & Analytics

- Dashboard with key metrics
- Order success rates
- Account health monitoring
- Price trend analysis
- Session performance tracking
- Error rate monitoring

## 🔄 Development Workflow

1. **Local Development**:
   ```bash
   # Backend development
   cd backend
   source venv/bin/activate
   python main.py
   
   # Frontend development
   npm run dev
   ```

2. **Database Management**:
   ```bash
   cd backend
   source venv/bin/activate
   
   # Create schema
   python database_schema.py
   
   # Drop all tables (development only)
   python database_schema.py --drop
   ```

3. **Virtual Environment**:
   ```bash
   # Activate backend environment
   cd backend
   source venv/bin/activate
   
   # Install new dependencies
   pip install package_name
   pip freeze > requirements.txt
   ```

## 🚀 Quick Commands

```bash
# Start everything
./start.sh

# Start backend only
cd backend && source venv/bin/activate && python main.py

# Start frontend only
npm run dev

# Database shell
psql -h localhost -U flipkart_admin -d flipkart_automation

# Check PostgreSQL status
pg_isready -h localhost -p 5432
```

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Error**:
   ```bash
   # Check PostgreSQL is running
   sudo systemctl status postgresql
   sudo systemctl start postgresql
   
   # Test database connection
   psql -h localhost -U flipkart_admin -d flipkart_automation
   ```

2. **Virtual Environment Issues**:
   ```bash
   # Recreate virtual environment
   cd backend
   rm -rf venv
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Frontend Build Errors**:
   ```bash
   # Clear cache and reinstall
   rm -rf node_modules package-lock.json
   npm install
   ```

4. **Port Already in Use**:
   ```bash
   # Find and kill process on port 8000
   lsof -ti:8000 | xargs kill -9
   
   # Find and kill process on port 3000
   lsof -ti:3000 | xargs kill -9
   ```

### Logs

- **Backend logs**: Check terminal output where `python main.py` is running
- **Frontend logs**: Check terminal output where `npm run dev` is running
- **Database logs**: `sudo journalctl -u postgresql`

## 🛡️ Production Deployment

1. **Environment Variables**:
   - Change `SECRET_KEY` to a secure random string
   - Update database password
   - Configure Gmail app password for OTP

2. **Database Security**:
   - Use strong passwords
   - Configure firewall rules
   - Enable SSL connections

3. **Application Security**:
   - Set `ENVIRONMENT=production` in `.env`
   - Configure reverse proxy (nginx)
   - Enable HTTPS

## 📝 Project Structure

```
flipkart-automation/
├── backend/
│   ├── venv/                 # Python virtual environment
│   ├── routers/             # FastAPI route modules
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database connection
│   ├── models.py            # Pydantic models
│   ├── database_schema.py   # Database schema script
│   ├── requirements.txt     # Python dependencies
│   └── .env                 # Environment variables
├── app/                     # Next.js application
├── components/              # React components
├── lib/                     # Utility libraries
├── automation/              # Playwright automation scripts
├── start.sh                 # Automated startup script
└── README.md               # This file
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## ⚠️ Disclaimer

This tool is for educational purposes only. Users are responsible for complying with Flipkart's terms of service and applicable laws. Use responsibly and at your own risk.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔗 Support

For support, questions, or feature requests:
- Create an issue on GitHub
- Check the documentation
- Review the troubleshooting guide

---

**Built with ❤️ for automation enthusiasts** 