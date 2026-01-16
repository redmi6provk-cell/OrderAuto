from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime, date
from models import OrderCreate, OrderUpdate, OrderResponse
from database import get_db_connection
from routers.auth import get_current_user

router = APIRouter()

@router.get("/", response_model=List[OrderResponse])
async def get_orders(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    product_id: Optional[int] = None,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get all orders with optional filters"""
    where_conditions = []
    params = [skip, limit]
    param_count = 3
    
    if status_filter:
        where_conditions.append(f"status = ${param_count}")
        params.insert(-2, status_filter)
        param_count += 1
    
    if product_id:
        where_conditions.append(f"product_id = ${param_count}")
        params.insert(-2, product_id)
        param_count += 1
    
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    
    orders = await conn.fetch(
        f"""
        SELECT id, product_id, flipkart_user_id, product_name, order_id, 
               actual_price, quantity, status, payment_method, delivery_address,
               order_date, expected_delivery, tracking_id, notes
        FROM flipkart_orders
        {where_clause}
        ORDER BY order_date DESC
        OFFSET ${len(params)-1} LIMIT ${len(params)}
        """,
        *params
    )
    
    return [OrderResponse(**dict(order)) for order in orders]

@router.post("/", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Create new order record"""
    # Verify product exists
    product = await conn.fetchrow(
        "SELECT id FROM flipkart_products WHERE id = $1", 
        order_data.product_id
    )
    
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    # Verify Flipkart user exists
    flipkart_user = await conn.fetchrow(
        "SELECT id FROM flipkart_users WHERE id = $1", 
        order_data.flipkart_user_id
    )
    
    if not flipkart_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flipkart user not found"
        )
    
    # Create order
    order = await conn.fetchrow(
        """
        INSERT INTO flipkart_orders 
        (product_id, flipkart_user_id, product_name, actual_price, quantity, delivery_address)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, product_id, flipkart_user_id, product_name, order_id, 
                  actual_price, quantity, status, payment_method, delivery_address,
                  order_date, expected_delivery, tracking_id, notes
        """,
        order_data.product_id, order_data.flipkart_user_id, order_data.product_name,
        order_data.actual_price, order_data.quantity, order_data.delivery_address
    )
    
    return OrderResponse(**dict(order))

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get specific order"""
    order = await conn.fetchrow(
        """
        SELECT id, product_id, flipkart_user_id, product_name, order_id, 
               actual_price, quantity, status, payment_method, delivery_address,
               order_date, expected_delivery, tracking_id, notes
        FROM flipkart_orders WHERE id = $1
        """,
        order_id
    )
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    return OrderResponse(**dict(order))

@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    order_data: OrderUpdate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Update order details"""
    # Check if order exists
    existing_order = await conn.fetchrow(
        "SELECT id FROM flipkart_orders WHERE id = $1", order_id
    )
    
    if not existing_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Build update query dynamically
    update_fields = []
    values = []
    param_count = 1
    
    if order_data.status is not None:
        update_fields.append(f"status = ${param_count}")
        values.append(order_data.status)
        param_count += 1
    
    if order_data.order_id is not None:
        update_fields.append(f"order_id = ${param_count}")
        values.append(order_data.order_id)
        param_count += 1
    
    if order_data.expected_delivery is not None:
        update_fields.append(f"expected_delivery = ${param_count}")
        values.append(order_data.expected_delivery)
        param_count += 1
    
    if order_data.tracking_id is not None:
        update_fields.append(f"tracking_id = ${param_count}")
        values.append(order_data.tracking_id)
        param_count += 1
    
    if order_data.notes is not None:
        update_fields.append(f"notes = ${param_count}")
        values.append(order_data.notes)
        param_count += 1
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    update_fields.append(f"updated_at = CURRENT_TIMESTAMP")
    values.append(order_id)
    
    query = f"""
        UPDATE flipkart_orders 
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING id, product_id, flipkart_user_id, product_name, order_id, 
                  actual_price, quantity, status, payment_method, delivery_address,
                  order_date, expected_delivery, tracking_id, notes
    """
    
    order = await conn.fetchrow(query, *values)
    
    return OrderResponse(**dict(order))

@router.delete("/{order_id}")
async def delete_order(
    order_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Delete order record"""
    # Check if order exists
    existing_order = await conn.fetchrow(
        "SELECT id FROM flipkart_orders WHERE id = $1", order_id
    )
    
    if not existing_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Delete order
    await conn.execute(
        "DELETE FROM flipkart_orders WHERE id = $1", order_id
    )
    
    return {"message": "Order deleted successfully"}
 
 