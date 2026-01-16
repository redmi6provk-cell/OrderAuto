"""
Settings API endpoints for managing automation configuration
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
import asyncpg
import os
from database import get_db_connection
from routers.auth import get_current_user

router = APIRouter(tags=["settings"])

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://flipkart_admin:flipkart_secure_2024@localhost:5432/flipkart_automation")

@router.get("/")
async def get_all_settings(
    current_user: dict = Depends(get_current_user),
    conn = Depends(get_db_connection)
):
    """Get all system settings"""
    try:
        settings = await conn.fetch('''
            SELECT setting_key, setting_value, setting_type, description, updated_at
            FROM system_settings
            ORDER BY setting_key
        ''')
        
        return {
            "success": True,
            "settings": [dict(setting) for setting in settings]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch settings: {str(e)}")

@router.put("/")
async def update_settings(
    settings: Dict[str, str], 
    current_user: dict = Depends(get_current_user),
    conn = Depends(get_db_connection)
):
    """Update multiple settings at once"""
    try:
        # Use UPSERT (INSERT ON CONFLICT) to handle both new and existing settings
        for key, value in settings.items():
            await conn.execute('''
                INSERT INTO system_settings (setting_key, setting_value, updated_by)
                VALUES ($1, $2, $3)
                ON CONFLICT (setting_key) DO UPDATE 
                SET setting_value = EXCLUDED.setting_value, 
                    updated_by = EXCLUDED.updated_by, 
                    updated_at = CURRENT_TIMESTAMP
            ''', key, value, current_user["id"])
        
        return {
            "success": True,
            "message": f"Updated {len(settings)} settings successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {str(e)}")

@router.get("/names")
async def get_names():
    """Get all names from names.txt file"""
    try:
        names_file = "names.txt"
        if not os.path.exists(names_file):
            # Create default names file if it doesn't exist
            default_names = [
                "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
                "Shaurya", "Atharv", "Advait", "Vedant", "Kabir", "Shivansh", "Yash", "Dhruv", "Ravi", "Dev",
                "Ananya", "Aadhya", "Kavya", "Anika", "Diya", "Myra", "Sara", "Pari", "Ira", "Anvi",
                "Navya", "Kiara", "Saanvi", "Priya", "Riya", "Khushi", "Avni", "Shreya", "Tanvi", "Ishika"
            ]
            with open(names_file, "w") as f:
                f.write("\n".join(default_names))
        
        with open(names_file, "r") as f:
            names = [name.strip() for name in f.readlines() if name.strip()]
        
        return {
            "success": True,
            "names": names
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get names: {str(e)}")

@router.put("/names")
async def update_names(
    names: Dict[str, List[str]], 
    current_user: dict = Depends(get_current_user)
):
    """Update names in names.txt file"""
    try:
        names_list = names.get("names", [])
        
        # Write names to file
        names_file = "names.txt"
        with open(names_file, "w") as f:
            f.write("\n".join(names_list))
        
        return {
            "success": True,
            "message": f"Updated {len(names_list)} names successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update names: {str(e)}")

@router.delete("/names")
async def clear_names(current_user: dict = Depends(get_current_user)):
    """Clear all names from names.txt file"""
    try:
        names_file = "names.txt"
        with open(names_file, "w") as f:
            f.write("")
        
        return {
            "success": True,
            "message": "All names cleared successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear names: {str(e)}")
