"""
Address Management API Router
Handles CRUD operations for multi-address system
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator
from typing import List, Optional
import asyncpg
from datetime import datetime

from database import DATABASE_URL
from routers.auth import get_current_user

router = APIRouter(tags=["addresses"])


class AddressCreate(BaseModel):
    name: str
    description: Optional[str] = None
    address_template: str
    office_no_min: int = 100
    office_no_max: int = 999
    name_postfix: str
    phone_prefix: str
    pincode: str
    is_default: bool = False

    @validator('office_no_min', 'office_no_max')
    def validate_office_numbers(cls, v):
        if v <= 0:
            raise ValueError('Office numbers must be positive')
        return v

    @validator('office_no_max')
    def validate_office_range(cls, v, values):
        if 'office_no_min' in values and v < values['office_no_min']:
            raise ValueError('office_no_max must be greater than or equal to office_no_min')
        return v

    @validator('name', 'name_postfix', 'phone_prefix', 'pincode')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()

    @validator('address_template')
    def validate_address_template(cls, v):
        if not v or not v.strip():
            raise ValueError('Address template cannot be empty')
        if '{office_no}' not in v:
            raise ValueError('Address template must contain {office_no} placeholder')
        return v.strip()


class AddressUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address_template: Optional[str] = None
    office_no_min: Optional[int] = None
    office_no_max: Optional[int] = None
    name_postfix: Optional[str] = None
    phone_prefix: Optional[str] = None
    pincode: Optional[str] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class AddressResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    address_template: str
    office_no_min: int
    office_no_max: int
    name_postfix: str
    phone_prefix: str
    pincode: str
    is_active: bool
    is_default: bool
    created_by: int
    created_at: datetime
    updated_at: datetime


@router.get("/", response_model=List[AddressResponse])
async def get_addresses(current_user: dict = Depends(get_current_user)):
    """Get all addresses"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        addresses = await conn.fetch('''
            SELECT * FROM addresses 
            WHERE is_active = TRUE 
            ORDER BY is_default DESC, name ASC
        ''')
        
        await conn.close()
        
        return [dict(address) for address in addresses]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch addresses: {str(e)}")


@router.get("/{address_id}", response_model=AddressResponse)
async def get_address(address_id: int, current_user: dict = Depends(get_current_user)):
    """Get specific address by ID"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        address = await conn.fetchrow('''
            SELECT * FROM addresses WHERE id = $1 AND is_active = TRUE
        ''', address_id)
        
        await conn.close()
        
        if not address:
            raise HTTPException(status_code=404, detail="Address not found")
        
        return dict(address)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch address: {str(e)}")


@router.post("/", response_model=AddressResponse)
async def create_address(address: AddressCreate, current_user: dict = Depends(get_current_user)):
    """Create new address"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # If this address is set as default, unset other defaults
        if address.is_default:
            await conn.execute('UPDATE addresses SET is_default = FALSE WHERE is_default = TRUE')
        
        # Insert new address
        new_address = await conn.fetchrow('''
            INSERT INTO addresses (name, description, address_template, office_no_min, office_no_max,
                                 name_postfix, phone_prefix, pincode, is_default, created_by)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
        ''', address.name, address.description, address.address_template, address.office_no_min,
             address.office_no_max, address.name_postfix, address.phone_prefix, address.pincode,
             address.is_default, current_user['id'])
        
        await conn.close()
        
        return dict(new_address)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create address: {str(e)}")


@router.put("/{address_id}", response_model=AddressResponse)
async def update_address(address_id: int, address: AddressUpdate, current_user: dict = Depends(get_current_user)):
    """Update existing address"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Check if address exists
        existing = await conn.fetchrow('SELECT * FROM addresses WHERE id = $1', address_id)
        if not existing:
            await conn.close()
            raise HTTPException(status_code=404, detail="Address not found")
        
        # If setting as default, unset other defaults
        if address.is_default:
            await conn.execute('UPDATE addresses SET is_default = FALSE WHERE is_default = TRUE')
        
        # Build update query dynamically
        update_fields = []
        params = [address_id]
        param_count = 1
        
        for field, value in address.dict(exclude_unset=True).items():
            if value is not None:
                param_count += 1
                update_fields.append(f"{field} = ${param_count}")
                params.append(value)
        
        if not update_fields:
            await conn.close()
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Add updated_at
        param_count += 1
        update_fields.append(f"updated_at = ${param_count}")
        params.append(datetime.now())
        
        query = f'''
            UPDATE addresses 
            SET {', '.join(update_fields)}
            WHERE id = $1
            RETURNING *
        '''
        
        updated_address = await conn.fetchrow(query, *params)
        
        await conn.close()
        
        return dict(updated_address)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update address: {str(e)}")


@router.delete("/{address_id}")
async def delete_address(address_id: int, current_user: dict = Depends(get_current_user)):
    """Soft delete address (set is_active = false)"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Check if address exists and is not the last active address
        active_count = await conn.fetchval('SELECT COUNT(*) FROM addresses WHERE is_active = TRUE')
        if active_count <= 1:
            await conn.close()
            raise HTTPException(status_code=400, detail="Cannot delete the last active address")
        
        # Check if address is default
        is_default = await conn.fetchval('SELECT is_default FROM addresses WHERE id = $1', address_id)
        if is_default:
            # Set another address as default
            await conn.execute('''
                UPDATE addresses 
                SET is_default = TRUE 
                WHERE id = (
                    SELECT id FROM addresses 
                    WHERE is_active = TRUE AND id != $1 
                    ORDER BY created_at ASC 
                    LIMIT 1
                )
            ''', address_id)
        
        # Soft delete
        result = await conn.execute('''
            UPDATE addresses 
            SET is_active = FALSE, updated_at = $2 
            WHERE id = $1
        ''', address_id, datetime.now())
        
        await conn.close()
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Address not found")
        
        return {"message": "Address deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete address: {str(e)}")


@router.post("/{address_id}/set-default")
async def set_default_address(address_id: int, current_user: dict = Depends(get_current_user)):
    """Set address as default"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Check if address exists
        exists = await conn.fetchval('SELECT EXISTS(SELECT 1 FROM addresses WHERE id = $1 AND is_active = TRUE)', address_id)
        if not exists:
            await conn.close()
            raise HTTPException(status_code=404, detail="Address not found")
        
        # Unset all defaults
        await conn.execute('UPDATE addresses SET is_default = FALSE WHERE is_default = TRUE')
        
        # Set new default
        await conn.execute('UPDATE addresses SET is_default = TRUE WHERE id = $1', address_id)
        
        await conn.close()
        
        return {"message": "Default address updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set default address: {str(e)}")


@router.get("/default/current", response_model=AddressResponse)
async def get_default_address(current_user: dict = Depends(get_current_user)):
    """Get current default address"""
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        address = await conn.fetchrow('''
            SELECT * FROM addresses 
            WHERE is_default = TRUE AND is_active = TRUE
            LIMIT 1
        ''')
        
        if not address:
            # Fallback to first active address
            address = await conn.fetchrow('''
                SELECT * FROM addresses 
                WHERE is_active = TRUE
                ORDER BY created_at ASC
                LIMIT 1
            ''')
        
        await conn.close()
        
        if not address:
            raise HTTPException(status_code=404, detail="No active addresses found")
        
        return dict(address)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch default address: {str(e)}")
