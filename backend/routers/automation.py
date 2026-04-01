from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from models import AutomationSessionCreate, AutomationSessionUpdate, AutomationSessionResponse
from database import get_db_connection
from routers.auth import get_current_user
from services import get_job_status, get_job_logs
from services.batch_manager import batch_manager
import asyncio
import json
 

router = APIRouter()

# Store running sessions (in production, use Redis or similar)
running_sessions = {}

@router.get("/sessions", response_model=List[AutomationSessionResponse])
async def get_automation_sessions(
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[str] = None,
    automation_type: Optional[str] = None,
    success_filter: Optional[str] = None,  # 'success' | 'fail'
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get automation sessions with pagination.
    - Default limit is 20
    - If limit <= 0, return all records (no pagination)
    """
    # Build WHERE clause safely with parameters
    where_parts = []
    params = []
    # Status filter
    if status_filter:
        where_parts.append(f"status = ${len(params)+1}")
        params.append(status_filter)
    # Automation type filter
    if automation_type:
        where_parts.append(f"automation_type = ${len(params)+1}")
        params.append(automation_type)
    # Success filter (based on existence of any successful account/job in session)
    if success_filter in ("success", "fail"):
        exists_clause = (
            "EXISTS ("
            " SELECT 1 FROM job_queue jq"
            " JOIN job_logs jl ON jl.job_id = jq.id"
            " WHERE jq.job_data->>'batch_session_id' = automation_sessions.batch_session_id"
            "   AND jl.message LIKE 'Job completed successfully%'"
            "   AND jl.message LIKE '%\"success\": true%'"
            ")"
        )
        if success_filter == "success":
            where_parts.append(exists_clause)
        else:  # 'fail' means none succeeded
            where_parts.append(f"NOT {exists_clause}")

    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    
    # Base query
    base_query = f"""
        SELECT id, batch_session_id, automation_type, automation_mode, status, batch_size, 
               total_accounts, total_batches, completed_batches, 
               account_range_start, account_range_end, total_jobs, 
               completed_jobs, failed_jobs, started_at, ended_at, 
               config, error_message
        FROM automation_sessions
        {where_clause}
        ORDER BY started_at DESC
    """

    # Apply pagination only if limit > 0
    if limit and limit > 0:
        # OFFSET/LIMIT parameters follow existing WHERE parameters
        base_query += f" OFFSET ${len(params)+1} LIMIT ${len(params)+2}"
        params.extend([skip, limit])
        sessions = await conn.fetch(base_query, *params)
    else:
        # No pagination (all rows)
        sessions = await conn.fetch(base_query, *params)
    
    result = []
    for session in sessions:
        session_dict = dict(session)
        # Parse config JSON if it exists
        if session_dict.get('config') and isinstance(session_dict['config'], str):
            try:
                session_dict['config'] = json.loads(session_dict['config'])
            except (json.JSONDecodeError, TypeError):
                session_dict['config'] = None
        # Ensure max_cart_value field exists (for backward compatibility)
        if 'max_cart_value' not in session_dict:
            session_dict['max_cart_value'] = None
        # Ensure automation_mode field exists (for backward compatibility)
        if 'automation_mode' not in session_dict or session_dict['automation_mode'] is None:
            session_dict['automation_mode'] = 'GROCERY'
        result.append(AutomationSessionResponse(**session_dict))
    return result

@router.get("/session-types")
async def get_distinct_automation_types(
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Return distinct automation types available in automation_sessions"""
    rows = await conn.fetch(
        """
        SELECT DISTINCT automation_type
        FROM automation_sessions
        WHERE automation_type IS NOT NULL AND automation_type <> ''
        ORDER BY automation_type ASC
        """
    )
    return [r["automation_type"] for r in rows]

@router.post("/sessions", response_model=AutomationSessionResponse)
async def create_automation_session(
    session_data: AutomationSessionCreate,
    background_tasks: BackgroundTasks,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Create and start new automation session"""
    # Check if session name already exists
    existing_session = await conn.fetchrow(
        "SELECT id FROM automation_sessions WHERE session_name = $1 AND status = 'running'",
        session_data.session_name
    )
    
    if existing_session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session with this name is already running"
        )
    
    # Create session
    session = await conn.fetchrow(
        """
        INSERT INTO automation_sessions (session_name, started_by, config, automation_type)
        VALUES ($1, $2, $3, $4)
        RETURNING id, session_name, status, products_monitored, accounts_used,
                  orders_placed, errors_count, started_at, ended_at, config, automation_type
        """,
        session_data.session_name, current_user["id"], session_data.config, session_data.automation_type
    )
    
    # Start automation in background
    background_tasks.add_task(run_automation_session, session["id"], session_data.config)
    
    return AutomationSessionResponse(**dict(session))

@router.get("/sessions/{session_id}", response_model=AutomationSessionResponse)
async def get_automation_session(
    session_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get specific automation session"""
    session = await conn.fetchrow(
        """
        SELECT id, batch_session_id, automation_type, automation_mode, status, batch_size, 
               total_accounts, total_batches, completed_batches, 
               account_range_start, account_range_end, total_jobs, 
               completed_jobs, failed_jobs, started_at, ended_at, 
               config, error_message
        FROM automation_sessions WHERE id = $1
        """,
        session_id
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation session not found"
        )
    
    session_dict = dict(session)
    # Parse config JSON if it exists
    if session_dict.get('config') and isinstance(session_dict['config'], str):
        try:
            session_dict['config'] = json.loads(session_dict['config'])
        except (json.JSONDecodeError, TypeError):
            session_dict['config'] = None
    
    # Ensure max_cart_value field exists (for backward compatibility)
    if 'max_cart_value' not in session_dict:
        session_dict['max_cart_value'] = None
    
    # Ensure automation_mode field exists (for backward compatibility)
    if 'automation_mode' not in session_dict or session_dict['automation_mode'] is None:
        session_dict['automation_mode'] = 'GROCERY'
    
    return AutomationSessionResponse(**session_dict)

@router.put("/sessions/{session_id}", response_model=AutomationSessionResponse)
async def update_automation_session(
    session_id: int,
    session_data: AutomationSessionUpdate,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Update automation session (mainly for status updates)"""
    # Check if session exists
    existing_session = await conn.fetchrow(
        "SELECT id FROM automation_sessions WHERE id = $1", session_id
    )
    
    if not existing_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation session not found"
        )
    
    # Build update query dynamically
    update_fields = []
    values = []
    param_count = 1
    
    if session_data.status is not None:
        update_fields.append(f"status = ${param_count}")
        values.append(session_data.status)
        param_count += 1
        
        # If stopping session, set ended_at
        if session_data.status in ['stopped', 'completed', 'failed']:
            update_fields.append(f"ended_at = CURRENT_TIMESTAMP")
    
    if session_data.products_monitored is not None:
        update_fields.append(f"products_monitored = ${param_count}")
        values.append(session_data.products_monitored)
        param_count += 1
    
    if session_data.accounts_used is not None:
        update_fields.append(f"accounts_used = ${param_count}")
        values.append(session_data.accounts_used)
        param_count += 1
    
    if session_data.orders_placed is not None:
        update_fields.append(f"orders_placed = ${param_count}")
        values.append(session_data.orders_placed)
        param_count += 1
    
    if session_data.errors_count is not None:
        update_fields.append(f"errors_count = ${param_count}")
        values.append(session_data.errors_count)
        param_count += 1
    
    if session_data.logs is not None:
        update_fields.append(f"logs = ${param_count}")
        values.append(session_data.logs)
        param_count += 1
    
    if not update_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update"
        )
    
    values.append(session_id)
    
    query = f"""
        UPDATE automation_sessions 
        SET {', '.join(update_fields)}
        WHERE id = ${param_count}
        RETURNING id, session_name, status, products_monitored, accounts_used,
                  orders_placed, errors_count, started_at, ended_at, config
    """
    
    session = await conn.fetchrow(query, *values)
    
    return AutomationSessionResponse(**dict(session))

@router.post("/sessions/{session_id}/stop")
async def stop_automation_session(
    session_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Stop running automation session"""
    # Check if session exists and is running
    session = await conn.fetchrow(
        "SELECT id, status FROM automation_sessions WHERE id = $1", session_id
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation session not found"
        )
    
    if session["status"] != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is not running"
        )
    
    # Update session status
    await conn.execute(
        """
        UPDATE automation_sessions 
        SET status = 'stopped', ended_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """,
        session_id
    )
    
    # Stop the background task if it exists
    if session_id in running_sessions:
        running_sessions[session_id]["stop"] = True
    
    return {"message": "Automation session stopped successfully"}

@router.get("/sessions/{session_id}/logs")
async def get_session_logs(
    session_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get logs for automation session"""
    session = await conn.fetchrow(
        "SELECT logs FROM automation_sessions WHERE id = $1", session_id
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation session not found"
        )
    
    return {
        "logs": session["logs"] or "",
        "session_id": session_id
    }

@router.get("/jobs/{job_id}/status")
async def get_job_status_endpoint(
    job_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get the status of a specific job"""
    job_status = await get_job_status(job_id)
    
    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job_status

@router.get("/jobs/{job_id}/logs")
async def get_job_logs_endpoint(
    job_id: int,
    current_user: dict = Depends(get_current_user)
):
    """Get logs for a specific job"""
    logs = await get_job_logs(job_id)
    
    return {
        "job_id": job_id,
        "logs": logs
    }

@router.get("/sessions/{session_id}/jobs")
async def get_session_jobs(
    session_id: int,
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Get all jobs for a session with their logs"""
    
    # Get session info
    session = await conn.fetchrow(
        "SELECT batch_session_id FROM automation_sessions WHERE id = $1", session_id
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    batch_session_id = session['batch_session_id']
    
    # Get all jobs for this session
    jobs = await conn.fetch(
        """
        SELECT jq.id, jq.job_type, jq.status, jq.created_at, jq.started_at, jq.completed_at, 
               jq.job_data, jq.error_message
        FROM job_queue jq
        WHERE jq.job_data->>'batch_session_id' = $1
        ORDER BY jq.created_at ASC
        """,
        batch_session_id
    )
    
    result = []
    for job in jobs:
        job_dict = dict(job)
        
        # Get logs for this job
        logs = await conn.fetch(
            """
            SELECT log_level, message, created_at, metadata
            FROM job_logs 
            WHERE job_id = $1 
            ORDER BY created_at ASC
            """,
            job['id']
        )
        
        job_dict['logs'] = [dict(log) for log in logs]
        result.append(job_dict)
    
    return {
        "session_id": session_id,
        "batch_session_id": batch_session_id,
        "jobs": result
    }

@router.post("/start-automation")
async def start_bulk_automation(
    request: dict,
    current_user: dict = Depends(get_current_user)
):
    """Start bulk automation with proper batch synchronization"""
    # Log the incoming request details for debugging
    print(f"\n📦 NEW AUTOMATION REQUEST FROM FRONTEND:")
    print(json.dumps(request, indent=2))
    print("-" * 40)

    batch_size = request.get('batch_size', 3)
    automation_type = request.get('automation_type', 'login_test')
    view_mode = request.get('view_mode', 'desktop')
    max_cart_value = request.get('max_cart_value')  # Extract maximum cart value from request
    address_id = request.get('address_id')
    account_selection_mode = request.get('account_selection_mode', 'range')
    keep_browser_open = request.get('keep_browser_open', False)
    # Optional coupon code for add_coupon automation
    coupon_code = request.get('coupon_code')
    # Optional multiple coupon codes (one per custom email) for add_coupon automation
    coupon_codes = request.get('coupon_codes')
    # Optional GST details for full automation
    gstin = request.get('gstin')
    business_name = request.get('business_name')
    # Optional steal deal product for full automation
    steal_deal_product = request.get('steal_deal_product')
    # Optional headless mode
    headless = bool(request.get('headless', False))
    # Marketplace mode (FLIPKART or GROCERY)
    automation_mode = request.get('automation_mode', 'GROCERY')
    
    # Sanitization: Ensure automation_type is an action and automation_mode is a marketplace
    marketplaces = ['FLIPKART', 'GROCERY']
    if automation_type in marketplaces:
        # Move marketplace from type to mode if it was accidentally swapped
        if automation_mode not in marketplaces:
            automation_mode = automation_type
        # Default to full_automation if the type was accidentally a marketplace
        automation_type = 'full_automation'
    
    # Ensure mode is valid even if not swapped
    if automation_mode not in marketplaces:
        automation_mode = 'GROCERY'
    
    # Handle account selection based on mode
    if account_selection_mode == 'range':
        account_range_start = request.get('account_range_start', 1)
        account_range_end = request.get('account_range_end', 50)
        custom_account_emails = None
        
        # Validate range inputs
        if account_range_start < 1 or account_range_end < account_range_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid account range"
            )
            
    elif account_selection_mode == 'custom':
        custom_account_emails = request.get('custom_account_emails', [])
        account_range_start = None
        account_range_end = None
        
        # Validate custom emails
        if not custom_account_emails or len(custom_account_emails) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one email address is required for custom selection"
            )
            
        # Basic email validation
        import re
        email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        invalid_emails = [email for email in custom_account_emails if not re.match(email_regex, email)]
        if invalid_emails:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid email addresses: {', '.join(invalid_emails)}"
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid account selection mode. Must be 'range' or 'custom'"
        )
    
    # Validate batch size
    if batch_size < 1 or batch_size > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch size must be between 1 and 5"
        )
    
    # Use batch manager to create synchronized batches
    result = await batch_manager.create_batch_automation(
        batch_size=batch_size,
        account_range_start=account_range_start,
        account_range_end=account_range_end,
        custom_account_emails=custom_account_emails,
        account_selection_mode=account_selection_mode,
        automation_type=automation_type,
        view_mode=view_mode,
        created_by=current_user["id"],
        max_cart_value=max_cart_value,
        address_id=address_id,
        keep_browser_open=keep_browser_open,
        coupon_code=coupon_code,
        coupon_codes=coupon_codes,
        gstin=gstin,
        business_name=business_name,
        steal_deal_product=steal_deal_product,
        headless=headless,
        automation_mode=automation_mode
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    # Prepare configuration response based on selection mode
    if account_selection_mode == 'range':
        account_info = f"{account_range_start}-{account_range_end}"
    else:
        account_info = f"{len(custom_account_emails)} custom emails"
    
    return {
        "success": True,
        "message": f"Batch automation started: {result['total_accounts']} accounts in {result['total_batches']} synchronized batches",
        "batch_session_id": result["batch_session_id"],
        "configuration": {
            "batch_size": result["batch_size"],
            "account_selection": account_info,
            "account_selection_mode": account_selection_mode,
            "automation_type": result["automation_type"],
            "total_accounts": result["total_accounts"],
            "total_batches": result["total_batches"],
            "address_id": address_id,
            "gstin": gstin,
            "business_name": business_name,
            "headless": headless
        },
        "batches": result["batches"]
    }

@router.get("/batch-status/{session_id}")
async def get_batch_status(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get status of a specific batch session"""
    status = batch_manager.get_batch_status(session_id)
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch session {session_id} not found"
        )
    
    return status

@router.get("/active-batches")
async def get_active_batches(
    current_user: dict = Depends(get_current_user)
):
    """Get all active batch sessions"""
    return batch_manager.get_all_active_sessions()

@router.post("/stop-batch/{batch_session_id}")
async def stop_batch_session(
    batch_session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Stop further processing for a batch session (cancel pending batches). Currently running batch will be allowed to finish."""
    result = await batch_manager.stop_session(batch_session_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to stop batch session"))
    return result

@router.delete("/sessions/all")
async def delete_all_automation_sessions(
    conn=Depends(get_db_connection),
    current_user: dict = Depends(get_current_user)
):
    """Delete all automation sessions and their associated logs from the database"""
    try:
        # Get all batch_session_ids before deletion
        batch_session_ids = await conn.fetch(
            "SELECT batch_session_id FROM automation_sessions"
        )
        batch_ids_list = [row['batch_session_id'] for row in batch_session_ids]
        
        # Delete job logs for all jobs related to these sessions
        deleted_logs = await conn.execute(
            """
            DELETE FROM job_logs 
            WHERE job_id IN (
                SELECT id FROM job_queue 
                WHERE job_data->>'batch_session_id' = ANY($1::text[])
            )
            """,
            batch_ids_list
        )
        
        # Delete jobs from job_queue related to these sessions
        deleted_jobs = await conn.execute(
            """
            DELETE FROM job_queue 
            WHERE job_data->>'batch_session_id' = ANY($1::text[])
            """,
            batch_ids_list
        )
        
        # Delete all automation sessions
        deleted_sessions = await conn.execute("DELETE FROM automation_sessions")
        
        # Extract counts from result strings (format: "DELETE N")
        sessions_count = int(deleted_sessions.split()[-1]) if deleted_sessions else 0
        jobs_count = int(deleted_jobs.split()[-1]) if deleted_jobs else 0
        logs_count = int(deleted_logs.split()[-1]) if deleted_logs else 0
        
        return {
            "success": True,
            "message": "All automation sessions and logs deleted successfully",
            "deleted": {
                "sessions": sessions_count,
                "jobs": jobs_count,
                "logs": logs_count
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete automation sessions: {str(e)}"
        )

# Background task functions
async def run_automation_session(session_id: int, config: dict):
    """Background task to run automation session"""
    # TODO: Implement actual automation logic with Playwright
    # This is a placeholder implementation
    
    import asyncpg
    from database import DATABASE_URL
    
    running_sessions[session_id] = {"stop": False}
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Simulate automation work
        products_checked = 0
        orders_placed = 0
        errors = 0
        
        for i in range(10):  # Simulate 10 iterations
            if running_sessions[session_id].get("stop"):
                break
            
            # Simulate work
            await asyncio.sleep(30)  # 30 seconds per iteration
            products_checked += 1
            
            # Update session progress
            await conn.execute(
                """
                UPDATE automation_sessions 
                SET products_monitored = $1, orders_placed = $2, errors_count = $3
                WHERE id = $4
                """,
                products_checked, orders_placed, errors, session_id
            )
        
        # Mark session as completed
        final_status = "stopped" if running_sessions[session_id].get("stop") else "completed"
        await conn.execute(
            """
            UPDATE automation_sessions 
            SET status = $1, ended_at = CURRENT_TIMESTAMP
            WHERE id = $2
            """,
            final_status, session_id
        )
        
    except Exception as e:
        # Mark session as failed
        await conn.execute(
            """
            UPDATE automation_sessions 
            SET status = 'failed', ended_at = CURRENT_TIMESTAMP, logs = $1
            WHERE id = $2
            """,
            f"Error: {str(e)}", session_id
        )
    finally:
        await conn.close()
        if session_id in running_sessions:
            del running_sessions[session_id]

 