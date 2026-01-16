from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List
from models import ProductCreate, ProductUpdate, ProductResponse, ProductCSVImport
from database import get_db_connection
from routers.auth import get_current_user
import re
import pandas as pd
import io
from decimal import Decimal
from datetime import datetime

router = APIRouter()

def validate_flipkart_url(url: str) -> bool:
    """Validate if URL is a valid Flipkart product URL"""
    flipkart_pattern = r'https?://(www\.)?flipkart\.com/.*'
    return bool(re.match(flipkart_pattern, url))

@router.get("/", response_model=List[ProductResponse])
async def get_products(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get all products"""
    where_clause = "WHERE is_active = TRUE" if active_only else ""
    
    products = await conn.fetch(
        f"""
        SELECT id, product_link, product_name, quantity, price_cap, 
               is_active, check_interval, created_at
        FROM flipkart_products
        {where_clause}
        ORDER BY created_at DESC
        OFFSET $1 LIMIT $2
        """,
        skip, limit
    )
    
    return [ProductResponse(**dict(product)) for product in products]

@router.post("/", response_model=ProductResponse)
async def create_product(
    product_data: ProductCreate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Create new product configuration"""
    # Validate Flipkart URL
    if not validate_flipkart_url(product_data.product_link):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Flipkart product URL"
        )
    
    # Check if product already exists
    existing_product = await conn.fetchrow(
        "SELECT id FROM flipkart_products WHERE product_link = $1",
        product_data.product_link
    )
    
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product with this URL already exists"
        )
    
    # Create product
    product = await conn.fetchrow(
        """
        INSERT INTO flipkart_products 
        (product_link, product_name, quantity, price_cap, check_interval, created_by)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, product_link, product_name, quantity, price_cap, 
                  is_active, check_interval, created_at
        """,
        product_data.product_link, product_data.product_name, product_data.quantity, 
        product_data.price_cap, product_data.check_interval, current_user["id"]
    )
    
    return ProductResponse(**dict(product))

@router.post("/bulk", response_model=List[ProductResponse])
async def create_bulk_products(
    products_data: List[ProductCreate],
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Create multiple new product configurations"""
    created_products = []
    for product_data in products_data:
        # Validate Flipkart URL
        if not validate_flipkart_url(product_data.product_link):
            # Skip invalid URLs for bulk upload
            continue
        
        # Check if product already exists
        existing_product = await conn.fetchrow(
            "SELECT id FROM flipkart_products WHERE product_link = $1",
            product_data.product_link
        )
        
        if existing_product:
            # Skip existing products
            continue

        # Create product
        product = await conn.fetchrow(
            """
            INSERT INTO flipkart_products 
            (product_link, product_name, quantity, price_cap, check_interval, created_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, product_link, product_name, quantity, price_cap, 
                      is_active, check_interval, created_at
            """,
            product_data.product_link, product_data.product_name, product_data.quantity, 
            product_data.price_cap, product_data.check_interval, current_user["id"]
        )
        created_products.append(ProductResponse(**dict(product)))
    
    return created_products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get specific product"""
    product = await conn.fetchrow(
        """
        SELECT id, product_link, product_name, quantity, price_cap, 
               is_active, check_interval, created_at
        FROM flipkart_products WHERE id = $1
        """,
        product_id
    )
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    return ProductResponse(**dict(product))

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductUpdate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Update product configuration"""
    # Check if product exists
    existing_product = await conn.fetchrow(
        "SELECT id FROM flipkart_products WHERE id = $1", product_id
    )
    
    if not existing_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Validate URL if provided
    if product_data.product_link and not validate_flipkart_url(product_data.product_link):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Flipkart product URL"
        )
    
    # Build update query dynamically
    update_fields = []
    values = []
    param_count = 1
    
    if product_data.product_link is not None:
        update_fields.append(f"product_link = ${param_count}")
        values.append(product_data.product_link)
        param_count += 1
    
    if product_data.product_name is not None:
        update_fields.append(f"product_name = ${param_count}")
        values.append(product_data.product_name)
        param_count += 1
    
    if product_data.quantity is not None:
        update_fields.append(f"quantity = ${param_count}")
        values.append(product_data.quantity)
        param_count += 1
    
    if product_data.price_cap is not None:
        update_fields.append(f"price_cap = ${param_count}")
        values.append(product_data.price_cap)
        param_count += 1
    
    if product_data.check_interval is not None:
        update_fields.append(f"check_interval = ${param_count}")
        values.append(product_data.check_interval)
        param_count += 1
    
    if product_data.is_active is not None:
        update_fields.append(f"is_active = ${param_count}")
        values.append(product_data.is_active)
        param_count += 1
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    update_fields.append(f"updated_at = CURRENT_TIMESTAMP")
    values.append(product_id)
    
    query = f"""
        UPDATE flipkart_products 
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING id, product_link, product_name, quantity, price_cap, 
                  is_active, check_interval, created_at
    """
    
    product = await conn.fetchrow(query, *values)
    
    return ProductResponse(**dict(product))

@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Delete product configuration"""
    # Check if product exists
    existing_product = await conn.fetchrow(
        "SELECT id FROM flipkart_products WHERE id = $1", product_id
    )
    
    if not existing_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Check if product has orders
    orders_count = await conn.fetchval(
        "SELECT COUNT(*) FROM flipkart_orders WHERE product_id = $1", product_id
    )
    
    if orders_count > 0:
        # Don't delete, just deactivate
        await conn.execute(
            "UPDATE flipkart_products SET is_active = FALSE WHERE id = $1", 
            product_id
        )
        return {"message": "Product deactivated (has existing orders)"}
    else:
        # Safe to delete
        await conn.execute(
            "DELETE FROM flipkart_products WHERE id = $1", product_id
        )
        return {"message": "Product deleted successfully"}



@router.post("/import-csv")
async def import_products_csv(
    file: UploadFile = File(...),
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Import products from CSV file"""
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    try:
        # Read CSV file
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Validate required columns
        required_columns = ['product_link', 'quantity']
        optional_columns = ['product_name', 'price_cap', 'check_interval']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns: {', '.join(missing_columns)}"
            )
        
        # Set default values for optional columns
        if 'price_cap' not in df.columns:
            df['price_cap'] = 50000.00  # Default price cap
        if 'check_interval' not in df.columns:
            df['check_interval'] = 300  # Default 5 minutes
        if 'product_name' not in df.columns:
            df['product_name'] = None
        
        imported_products = []
        errors = []
        
        for index, row in df.iterrows():
            try:
                # Validate Flipkart URL
                if not validate_flipkart_url(row['product_link']):
                    errors.append(f"Row {index + 1}: Invalid Flipkart URL")
                    continue
                
                # Validate quantity
                if row['quantity'] <= 0:
                    errors.append(f"Row {index + 1}: Quantity must be positive")
                    continue
                
                # Validate price cap (optional, but if provided must be positive)
                price_cap_value = None
                if pd.notna(row['price_cap']):
                    if row['price_cap'] <= 0:
                        errors.append(f"Row {index + 1}: Price cap must be positive")
                        continue
                    price_cap_value = float(row['price_cap'])
                
                # Handle check_interval with default
                check_interval_value = 300  # Default value
                if 'check_interval' in row and pd.notna(row['check_interval']):
                    check_interval_value = int(row['check_interval'])
                
                # Insert product
                product = await conn.fetchrow(
                    """
                    INSERT INTO flipkart_products (product_link, product_name, quantity, price_cap, check_interval, created_by)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id, product_link, product_name, quantity, price_cap, is_active, check_interval, created_at
                    """,
                    row['product_link'], 
                    row['product_name'] if pd.notna(row['product_name']) else None,
                    int(row['quantity']), 
                    price_cap_value, 
                    check_interval_value,
                    current_user["id"]
                )
                
                imported_products.append(ProductResponse(**dict(product)))
                
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        return {
            "message": f"Imported {len(imported_products)} products",
            "imported_count": len(imported_products),
            "error_count": len(errors),
            "errors": errors[:10],  # Show first 10 errors
            "products": imported_products
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing CSV file: {str(e)}"
        )

@router.get("/export-template")
async def export_csv_template():
    """Download CSV template for product import"""
    template_data = {
        'product_link': ['https://www.flipkart.com/product-example-1', 'https://www.flipkart.com/product-example-2'],
        'product_name': ['Example Product 1', 'Example Product 2'],
        'quantity': [1, 2],
        'price_cap': [25000.00, 15000.00],
        'check_interval': [300, 600]
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
        headers={"Content-Disposition": "attachment; filename=products_template.csv"}
    ) 