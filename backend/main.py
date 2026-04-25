import sys
import asyncio
import os

# Fix for Playwright on Windows: use ProactorEventLoop
# This MUST be the first thing that happens
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        import uvicorn.loops.asyncio
        uvicorn.loops.asyncio.asyncio_setup = lambda use_subprocess=False, **kwargs: asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except ImportError:
        pass

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uvicorn
from dotenv import load_dotenv

# Load environment variables FIRST before importing routers
load_dotenv()

# Import routers AFTER environment variables are loaded
from routers import auth, users, products, orders, automation, settings, addresses
from services import job_queue
from services.batch_manager import batch_manager
from database import db

# Security
security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Starting Flipkart Automation API...")
    
    # Diagnostic: Check event loop type
    loop = asyncio.get_running_loop()
    print(f"🔄 Current Event Loop: {type(loop).__name__}")
    if sys.platform == 'win32' and 'Selector' in type(loop).__name__:
        print("⚠️ WARNING: SelectorEventLoop detected on Windows! Playwright will fail.")
        print("🔧 Attempting to force ProactorEventLoop...")

    print("📊 Connecting to database pool...")
    await db.connect()

    print("🔧 Starting job queue workers...")
    await job_queue.start()
    print("✅ Job queue started successfully")
    print("🔧 Starting batch coordinator...")
    await batch_manager.start_batch_coordinator()
    print("✅ Batch coordinator started successfully")
    yield
    # Shutdown
    print("🛑 Shutting down batch coordinator...")
    await batch_manager.stop_batch_coordinator()
    print("🛑 Shutting down job queue...")
    await job_queue.stop()
    
    print("📊 Disconnecting database pool...")
    await db.disconnect()
    
    print("🛑 Shutting down Flipkart Automation API...")

# Create FastAPI app
app = FastAPI(
    title="Flipkart Automation API",
    description="Backend API for automated Flipkart ordering system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://147.93.31.160:3000",
        "http://0.0.0.0:3000", 
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:3001",  # In case Next.js runs on 3001
        "http://127.0.0.1:3001",
        "https://fone.vkshivshakti.in",
        "https://apifone.vkshivshakti.in"

    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "X-CSRFToken",
        "User-Agent",
        "Referer"
    ],
    expose_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(automation.router, prefix="/api/automation", tags=["Automation"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(addresses.router, prefix="/api/addresses", tags=["Addresses"])

@app.get("/")
async def root():
    return {
        "message": "Flipkart Automation API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": "2024-01-01T00:00:00Z"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000
    ) 