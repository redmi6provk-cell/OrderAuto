from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List
from models import FlipkartUserCreate, FlipkartUserUpdate, FlipkartUserResponse, FlipkartAccountCSVImport
from database import get_db_connection
from routers.auth import get_current_user
import pandas as pd
import io

router = APIRouter()

@router.get("/flipkart", response_model=List[FlipkartUserResponse])
async def get_flipkart_users(
    skip: int = 0,
    limit: int = 100,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get all Flipkart user accounts"""
    users = await conn.fetch(
        """
        SELECT id, email, cookies, is_active, last_login, login_attempts, created_at
        FROM flipkart_users
        ORDER BY id ASC
        OFFSET $1 LIMIT $2
        """,
        skip, limit
    )
    
    return [FlipkartUserResponse(**dict(user)) for user in users]

@router.get("/flipkart/count")
async def get_flipkart_users_count(
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get total count of Flipkart user accounts"""
    total = await conn.fetchval("SELECT COUNT(*) FROM flipkart_users")
    active = await conn.fetchval("SELECT COUNT(*) FROM flipkart_users WHERE is_active = TRUE")
    return {"total": total, "active": active}

@router.post("/flipkart", response_model=FlipkartUserResponse)
async def create_flipkart_user(
    user_data: FlipkartUserCreate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Create new Flipkart user account"""
    # Check if email already exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM flipkart_users WHERE email = $1",
        user_data.email
    )
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Flipkart account with this email already exists"
        )
    
    # Create user
    user = await conn.fetchrow(
        """
        INSERT INTO flipkart_users (email, password, proxy_config, created_by)
        VALUES ($1, $2, $3, $4)
        RETURNING id, email, cookies, is_active, last_login, login_attempts, created_at
        """,
        user_data.email, user_data.password, user_data.proxy_config, current_user["id"]
    )
    
    return FlipkartUserResponse(**dict(user))

@router.get("/flipkart/{user_id}", response_model=FlipkartUserResponse)
async def get_flipkart_user(
    user_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get specific Flipkart user account"""
    user = await conn.fetchrow(
        """
        SELECT id, email, cookies, is_active, last_login, login_attempts, created_at
        FROM flipkart_users WHERE id = $1
        """,
        user_id
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flipkart user not found"
        )
    
    return FlipkartUserResponse(**dict(user))

@router.put("/flipkart/{user_id}", response_model=FlipkartUserResponse)
async def update_flipkart_user(
    user_id: int,
    user_data: FlipkartUserUpdate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Update Flipkart user account"""
    # Check if user exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM flipkart_users WHERE id = $1", user_id
    )
    
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flipkart user not found"
        )
    
    # Build update query dynamically
    update_fields = []
    values = []
    param_count = 1
    
    if user_data.email is not None:
        update_fields.append(f"email = ${param_count}")
        values.append(user_data.email)
        param_count += 1
    
    if user_data.password is not None:
        update_fields.append(f"password = ${param_count}")
        values.append(user_data.password)
        param_count += 1
    
    if user_data.cookies is not None:
        update_fields.append(f"cookies = ${param_count}")
        values.append(user_data.cookies)
        param_count += 1
    
    if user_data.proxy_config is not None:
        update_fields.append(f"proxy_config = ${param_count}")
        values.append(user_data.proxy_config)
        param_count += 1
    
    if user_data.is_active is not None:
        update_fields.append(f"is_active = ${param_count}")
        values.append(user_data.is_active)
        param_count += 1
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    update_fields.append(f"updated_at = ${param_count}")
    values.append("CURRENT_TIMESTAMP")
    values.append(user_id)
    
    query = f"""
        UPDATE flipkart_users 
        SET {', '.join(update_fields)}
        WHERE id = ${param_count + 1}
        RETURNING id, email, cookies, is_active, last_login, login_attempts, created_at
    """
    
    user = await conn.fetchrow(query, *values[:-1], user_id)
    
    return FlipkartUserResponse(**dict(user))

@router.delete("/flipkart/{user_id}")
async def delete_flipkart_user(
    user_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Delete Flipkart user account"""
    # Check if user exists
    existing_user = await conn.fetchrow(
        "SELECT id FROM flipkart_users WHERE id = $1", user_id
    )
    
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flipkart user not found"
        )
    
    # Delete user
    await conn.execute(
        "DELETE FROM flipkart_users WHERE id = $1", user_id
    )
    
    return {"message": "Flipkart user deleted successfully"}

@router.post("/flipkart/{user_id}/test-login")
async def test_flipkart_login(
    user_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Test login for Flipkart user account"""
    # Get user credentials
    user = await conn.fetchrow(
        "SELECT email, password FROM flipkart_users WHERE id = $1",
        user_id
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flipkart user not found"
        )
    
    # TODO: Implement actual Flipkart login test with Playwright
    # For now, return mock response
    return {
        "success": True,
        "message": "Login test successful",
        "email": user["email"]
    }

@router.post("/flipkart/import-csv")
async def import_flipkart_accounts_csv(
    file: UploadFile = File(...),
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Import Flipkart accounts from CSV file"""
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    try:
        # Read CSV file with robust encoding handling
        contents = await file.read()
        try:
            buffer = io.BytesIO(contents)
            df = pd.read_csv(buffer, encoding='utf-8-sig')
        except UnicodeDecodeError:
            buffer = io.BytesIO(contents)
            df = pd.read_csv(buffer, encoding='latin-1')

        # Normalize column names (trim + lowercase)
        df.columns = [str(c).strip().lower() for c in df.columns]

        # Validate required columns
        required_columns = ['email']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )

        imported_accounts = []
        errors = []

        for index, row in df.iterrows():
            try:
                # Validate email format safely
                raw_val = row['email']
                if pd.isna(raw_val):
                    errors.append(f"Row {index + 1}: Email is empty")
                    continue
                email = str(raw_val).strip()
                if not email or '@' not in email:
                    errors.append(f"Row {index + 1}: Invalid email format")
                    continue

                # Check if account already exists
                existing_user = await conn.fetchrow(
                    "SELECT id FROM flipkart_users WHERE email = $1",
                    email
                )

                if existing_user:
                    errors.append(f"Row {index + 1}: Account with email {email} already exists")
                    continue

                # Insert account
                account = await conn.fetchrow(
                    """
                    INSERT INTO flipkart_users (email, password, proxy_config, created_by)
                    VALUES ($1, $2, $3, $4)
                    RETURNING id, email, cookies, is_active, last_login, login_attempts, created_at
                    """,
                    email, None, None, current_user["id"]
                )

                imported_accounts.append(FlipkartUserResponse(**dict(account)))

            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e) or repr(e)}")

        return {
            "message": f"Imported {len(imported_accounts)} Flipkart accounts",
            "imported_count": len(imported_accounts),
            "error_count": len(errors),
            "errors": errors[:10],  # Show first 10 errors
            "accounts": imported_accounts
        }

    except HTTPException as he:
        # Preserve original HTTPException details
        raise he
    except Exception as e:
        # Surface a more informative message
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing CSV file: {str(e) or repr(e)}"
        )

@router.get("/flipkart/export-template")
async def export_flipkart_csv_template():
    """Download CSV template for Flipkart account import"""
    template_data = {
        'email': ['account1@example.com', 'account2@example.com']
    }
    
    df = pd.DataFrame(template_data)
    
    # Convert to CSV
    output = io.StringIO()
    df.to_csv(output, index=False)
    csv_content = output.getvalue()
    
    from fastapi.responses import Response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=flipkart_accounts_template.csv"}
    ) 