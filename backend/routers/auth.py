from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from typing import Optional

from models import LoginRequest, Token, UserResponse, UserCreate
from database import get_db_connection

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    conn=Depends(get_db_connection)
) -> dict:
    """Get current authenticated user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)  # Convert back to integer
    except (JWTError, ValueError) as e:  # Also catch ValueError for int conversion
        raise credentials_exception
    
    # Get user from database
    user = await conn.fetchrow(
        "SELECT * FROM users WHERE id = $1 AND is_active = TRUE", user_id
    )
    if user is None:
        raise credentials_exception
    
    return dict(user)

@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    conn=Depends(get_db_connection)
):
    """Login user and return JWT token"""
    # Get user from database
    user = await conn.fetchrow(
        "SELECT * FROM users WHERE username = $1 AND is_active = TRUE",
        login_data.username
    )
    
    if not user or not verify_password(login_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["id"])}, expires_delta=access_token_expires  # Convert to string
    )
    
    user_response = UserResponse(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        is_active=user["is_active"],
        is_admin=user["is_admin"],
        created_at=user["created_at"]
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )

@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Register new user (admin only)"""
    if not current_user["is_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create new users"
        )
    
    # Check if user exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM users WHERE username = $1 OR email = $2",
        user_data.username, user_data.email
    )
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
    
    # Hash password and create user
    hashed_password = get_password_hash(user_data.password)
    
    user = await conn.fetchrow(
        """
        INSERT INTO users (username, password_hash, email, is_admin)
        VALUES ($1, $2, $3, $4)
        RETURNING id, username, email, is_active, is_admin, created_at
        """,
        user_data.username, hashed_password, user_data.email, user_data.is_admin
    )
    
    return UserResponse(**dict(user))

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        is_active=current_user["is_active"],
        is_admin=current_user["is_admin"],
        created_at=current_user["created_at"]
    )

@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh JWT token"""
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(current_user["id"])}, expires_delta=access_token_expires  # Convert to string
    )
    
    return {"access_token": access_token, "token_type": "bearer"} 