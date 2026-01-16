# Full Setup Guide (Linux) - Flipkart Automation System

This guide walks you through a complete end-to-end setup on Linux, from installing dependencies and PostgreSQL to running the application. Commands are tailored for Debian/Ubuntu. For other distros, adapt package manager commands accordingly.

## 1) System Requirements

- Node.js 18+
- Python 3.11+
- PostgreSQL 12+ (recommended 15+)
- Git
- Modern web browser (Chrome/Chromium recommended)

Optional but recommended:
- Redis (for background tasks if you enable Celery)

## 2) Install System Packages

Debian/Ubuntu:
```bash
sudo apt update
sudo apt install -y curl git build-essential python3 python3-venv python3-pip \
  postgresql postgresql-contrib \
  libjpeg-dev zlib1g-dev \
  libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
  libxcomposite1 libxdamage1 libxrandr2 libgbm1 libpango-1.0-0 libpangocairo-1.0-0 \
  libxfixes3 libasound2t64 libatspi2.0-0 libnss3 libxshmfence1
```

Notes:
- The additional libraries above are commonly required for Playwright browsers. If you prefer, you can install them via Playwright directly using `playwright install --with-deps` (see step 6).

## 3) Install Node.js 18+ (via nvm, recommended)

```bash
# Install nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# Restart your shell then:
source "$HOME/.nvm/nvm.sh"
# Install and use Node.js 18 LTS
nvm install 18
nvm use 18
node -v
npm -v
```

Alternatively, install Node.js via your distro’s package manager or from nodejs.org.

## 4) PostgreSQL Setup

Start PostgreSQL and create database/user. You can use the defaults below or customize. If you customize, remember to update `backend/.env` accordingly.

```bash
# Ensure PostgreSQL is running
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Switch to the postgres user and create role + db
sudo -u postgres psql <<'SQL'
-- Change the password if desired
CREATE USER flipkart_admin WITH PASSWORD 'flipkart_secure_2024' LOGIN;
ALTER ROLE flipkart_admin CREATEDB;

-- Create the application database owned by the dedicated user
CREATE DATABASE flipkart_automation OWNER flipkart_admin;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE flipkart_automation TO flipkart_admin;
SQL
```

Quick connection test:
```bash
psql -h localhost -U flipkart_admin -d flipkart_automation -c "SELECT 1;"
```

## 5) Clone the Repository

```bash
git clone <your-repository-url> Auto_Flipkart
cd Auto_Flipkart/Order_Auto
```

## 6) Backend Setup (FastAPI)

```bash
cd backend
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install backend dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers (with system deps if needed)
python -m playwright install  # or: python -m playwright install --with-deps
```

Create your environment file from the example (or edit existing):
```bash
cp .env.example .env
```

Edit `backend/.env` and set values as appropriate. Example:
```env
# Database
DATABASE_URL=postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation

# JWT
SECRET_KEY=change_this_to_a_strong_random_value
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Admin user (created automatically if missing)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_EMAIL=admin@flipkart-automation.com

# Optional services
REDIS_URL=redis://localhost:6379
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Browser/automation
HEADLESS_MODE=true
PROXY_ROTATION_ENABLED=false
```

Initialize the database schema:
```bash
# From backend directory with venv active
python database_schema.py
```

Start backend (choose one):
```bash
# Simple
python main.py

# Or with uvicorn (hot reload)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

API docs: http://localhost:8000/docs

## 7) Frontend Setup (Next.js)

In a new terminal, from the project root `Order_Auto/`:
```bash
npm install
```

Optional: configure frontend environment in `app/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME="Flipkart Automation"
```

Start the development server:
```bash
npm run dev
```

Dashboard: http://localhost:3000

## 8) One-Command Startup (Optional)

You can also use the provided script to install dependencies and start both services:
```bash
chmod +x start.sh
./start.sh
```
The script expects PostgreSQL to be running. If you see an error about PostgreSQL, start it with `sudo systemctl start postgresql`.

## 9) Log In and First Steps

- Go to http://localhost:3000/login
- Default admin: `admin` / `admin123` (change these for security)
- Navigate to Dashboard → Flipkart Accounts to add accounts
- Navigate to Dashboard → Products to add product URLs and quantities
- Navigate to Dashboard → Automation to start sessions

Tip: The Automation page supports Test Login for both account selection modes:
- Range mode: run across a numeric range of saved accounts
- Custom mode: specify exact account emails

## 10) Verifications

Quick checks:
```bash
# Backend health
curl -s http://localhost:8000/health

# API docs
curl -s http://localhost:8000/docs | head -c 100

# Database check
psql -h localhost -U flipkart_admin -d flipkart_automation -c "SELECT 1;"
```

## 11) Optional: Redis + Celery

If you plan to use background tasks:
```bash
# Install Redis (Ubuntu/Debian)
sudo apt install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Environment (backend/.env)
REDIS_URL=redis://localhost:6379

# Example Celery run command (from backend with venv)
celery -A services.automation_worker.celery_app worker --loglevel=INFO
```

## 12) Troubleshooting

- Playwright browsers missing or failing to launch:
  ```bash
  # Inside backend venv
  python -m playwright install --with-deps
  ```
- PostgreSQL not running:
  ```bash
  sudo systemctl status postgresql
  sudo systemctl start postgresql
  ```
- Ports already in use:
  ```bash
  lsof -ti:8000 | xargs -r kill -9
  lsof -ti:3000 | xargs -r kill -9
  ```
- Recreate backend venv:
  ```bash
  cd backend
  rm -rf venv
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```

## 13) Security Checklist (Before Production)

- Change `SECRET_KEY` and all default credentials
- Use a strong password for the PostgreSQL user
- Restrict database network access (firewall)
- Enable HTTPS via a reverse proxy (nginx/caddy)
- Set `HEADLESS_MODE=true` in production
- Rotate credentials regularly

## 14) Reference

- Backend requirements: `backend/requirements.txt`
- Backend docs: `backend/README.md`
- Frontend docs: `app/README.md`
- API docs (live): `http://localhost:8000/docs`

---

If you get stuck, check the Quick Start guide (`help_doc/quick_start_guide.md`) for sanity checks, or review `help_doc/SETUP_COMPLETE.md` for a system overview after setup.
