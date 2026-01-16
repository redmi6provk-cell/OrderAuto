"""
Batch Manager Service
Coordinates batch execution to ensure batches complete before starting next ones
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
import json
import random

from database import DATABASE_URL
import asyncpg
from database import db
from services.job_queue import JobStatus, LogLevel

class BatchStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchManager:
    def __init__(self):
        self.active_batches: Dict[str, Dict] = {}
        self.batch_queues: Dict[str, List[Dict]] = {}
        self.running = False
        self.coordinator_task = None
        self.settings_cache = {}
        self.names_cache = []

    async def load_address(self, address_id: Optional[int] = None) -> bool:
        """Load address configuration from addresses table - REQUIRED for proper operation"""
        try:
            async with db.get_connection() as conn:
                # Load address configuration
                if address_id:
                    address = await conn.fetchrow('''
                        SELECT * FROM addresses 
                        WHERE id = $1 AND is_active = TRUE
                    ''', address_id)
                else:
                    # Use default address
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
            
            if not address:
                logging.error("❌ BATCH AUTOMATION CANCELLED: No active address configuration found")
                return False
            
            # Store address configuration in settings_cache format for compatibility
            self.settings_cache = {
                'address_template': address['address_template'],
                'office_no_min': address['office_no_min'],
                'office_no_max': address['office_no_max'],
                'name_postfix': address['name_postfix'],
                'phone_prefix': address['phone_prefix'],
                'pincode': address['pincode']
            }
            
            logging.info(f"✅ Loaded address '{address['name']}': name_postfix='{address['name_postfix']}', pincode='{address['pincode']}'")
            return True
                
        except Exception as e:
            logging.error(f"❌ BATCH AUTOMATION CANCELLED: Failed to load address configuration: {str(e)}")
            return False

    async def load_names(self):
        """Load names from names.txt file"""
        try:
            with open("names.txt", "r") as f:
                self.names_cache = [name.strip() for name in f.readlines() if name.strip()]
        except FileNotFoundError:
            # Fallback list in case the file is missing
            self.names_cache = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan"]
        
        if not self.names_cache:
            self.names_cache = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun"]

    def generate_random_name(self):
        """Generate a random name with postfix"""
        if not self.settings_cache:
            raise ValueError("Settings not loaded - cannot generate name")
            
        if not self.names_cache:
            return f"User {self.settings_cache['name_postfix']}"
        
        random_name = random.choice(self.names_cache)
        postfix = self.settings_cache['name_postfix']
        return f"{random_name} {postfix}"

    def generate_random_phone(self):
        """Generate a random phone number with prefix"""
        if not self.settings_cache:
            raise ValueError("Settings not loaded - cannot generate phone")
            
        prefix = self.settings_cache['phone_prefix']
        # Generate 6 random digits for the remaining part
        remaining_digits = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        return f"{prefix}{remaining_digits}"

    def generate_random_address(self):
        """Generate a random address using template"""
        if not self.settings_cache:
            raise ValueError("Settings not loaded - cannot generate address")
            
        template = self.settings_cache['address_template']
        office_min = self.settings_cache['office_no_min']
        office_max = self.settings_cache['office_no_max']
        office_no = random.randint(office_min, office_max)
        return template.format(office_no=office_no)

    def get_default_pincode(self):
        """Get the default pincode from settings"""
        if not self.settings_cache:
            raise ValueError("Settings not loaded - cannot get pincode")
            
        return self.settings_cache['pincode']
        
    async def create_batch_automation(
        self,
        batch_size: int,
        automation_type: str,
        view_mode: str,
        created_by: int,
        account_range_start: Optional[int] = None,
        account_range_end: Optional[int] = None,
        custom_account_emails: Optional[List[str]] = None,
        account_selection_mode: str = 'range',
        max_cart_value: Optional[float] = None,
        address_id: Optional[int] = None,
        keep_browser_open: bool = False,
        coupon_code: Optional[str] = None,
        coupon_codes: Optional[List[str]] = None,
        gstin: Optional[str] = None,
        business_name: Optional[str] = None,
        steal_deal_product: Optional[str] = None,
        headless: Optional[bool] = False
    ) -> Dict[str, Any]:
        """Create a batch automation with proper sequencing"""
        
        # Load address configuration only for flows that require it
        if automation_type in ['full_automation', 'add_address']:
            address_loaded = await self.load_address(address_id)
            if not address_loaded:
                return {
                    "success": False,
                    "error": "BATCH AUTOMATION CANCELLED: Failed to load address configuration. Cannot proceed without proper address settings."
                }

        await self.load_names()
        
        # Generate unique batch session ID
        batch_session_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{created_by}"
        
        try:
            async with db.get_connection() as conn:
                # Handle account selection based on mode
                if account_selection_mode == 'range':
                    if account_range_start is None or account_range_end is None:
                        return {
                            "success": False,
                            "error": "Account range start and end are required for range-based selection"
                        }
                    
                    # Get accounts within the specified row-number range directly in SQL to avoid loading all rows
                    filtered_accounts = await conn.fetch(
                        """
                        WITH ranked AS (
                            SELECT *, ROW_NUMBER() OVER (ORDER BY id) AS row_num
                            FROM flipkart_users
                            WHERE is_active = TRUE
                        )
                        SELECT * FROM ranked
                        WHERE row_num BETWEEN $1 AND $2
                        ORDER BY id
                        """,
                        account_range_start, account_range_end
                    )
                    
                    if not filtered_accounts:
                        return {
                            "success": False,
                            "error": f"No active accounts found in range {account_range_start}-{account_range_end}"
                        }
                        
                elif account_selection_mode == 'custom':
                    if not custom_account_emails or len(custom_account_emails) == 0:
                        return {
                            "success": False,
                            "error": "Custom account emails are required for custom selection"
                        }
                    
                    # Get accounts by specific email addresses
                    placeholders = ','.join([f'${i+1}' for i in range(len(custom_account_emails))])
                    query = f"""
                        SELECT * FROM flipkart_users 
                        WHERE is_active = TRUE AND email IN ({placeholders})
                    """
                    filtered_accounts = await conn.fetch(query, *custom_account_emails)
                    
                    if not filtered_accounts:
                        return {
                            "success": False,
                            "error": f"No active accounts found for the provided email addresses"
                        }
                    
                    # Check if all requested emails were found
                    found_emails = {account['email'] for account in filtered_accounts}
                    missing_emails = set(custom_account_emails) - found_emails
                    if missing_emails:
                        logging.warning(f"Some emails not found in database: {', '.join(missing_emails)}")

                    # If add_coupon with custom selection and coupon_codes provided, validate mapping lengths
                    if automation_type == 'add_coupon' and coupon_codes is not None:
                        if not isinstance(coupon_codes, list) or len(coupon_codes) == 0:
                            return {
                                "success": False,
                                "error": "coupon_codes must be a non-empty list when using custom selection for add_coupon"
                            }
                        # Normalize inputs (trim and drop empties)
                        normalized_codes = [c.strip() for c in coupon_codes if isinstance(c, str) and c.strip()]
                        if len(normalized_codes) != len(custom_account_emails):
                            return {
                                "success": False,
                                "error": f"coupon_codes count ({len(normalized_codes)}) must equal custom_account_emails count ({len(custom_account_emails)})"
                            }
                        # Build email -> coupon mapping by provided order
                        coupon_map = {email: code for email, code in zip(custom_account_emails, normalized_codes)}
                    else:
                        coupon_map = None
                
                else:
                    return {
                        "success": False,
                        "error": f"Invalid account selection mode: {account_selection_mode}"
                    }
                
                # Get products for full automation (now handled by the unified flipkart_login worker)
                products = []
                include_products = automation_type in ['full_automation', 'full']
                if include_products:
                    products = await conn.fetch(
                        "SELECT * FROM flipkart_products WHERE is_active = TRUE"
                    )
                    
                    if not products:
                        return {
                            "success": False,
                            "error": "No active products found for full automation"
                        }
                
                # Create batches
                total_accounts = len(filtered_accounts)
                batches = []
                
                for i in range(0, total_accounts, batch_size):
                    batch_accounts = filtered_accounts[i:i + batch_size]
                    batch_id = f"{batch_session_id}_batch_{len(batches) + 1}"
                    
                    batch_jobs = []
                    for account in batch_accounts:
                        # Create unified automation job
                        job_data = {
                            "flipkart_user_id": account["id"],
                            "email": account["email"],
                            "batch_id": batch_id,
                            "batch_session_id": batch_session_id,
                            "automation_type": automation_type,
                            "view_mode": view_mode,
                            "keep_browser_open": keep_browser_open,
                            "headless": bool(headless)
                        }
                        
                        # Add maximum cart value if specified
                        if max_cart_value is not None:
                            job_data["max_cart_value"] = max_cart_value
                        
                        # Add address_id to job data for validation during automation
                        if address_id is not None:
                            job_data["address_id"] = address_id
                        
                        # Add products data if this is a full automation
                        if include_products:
                            # Convert products to the format expected by the automation worker
                            products_data = []
                            for product in products:
                                # Fix the float conversion error by handling None values
                                price_cap = product["price_cap"]
                                if price_cap is not None:
                                    try:
                                        price_cap = float(price_cap)
                                    except (ValueError, TypeError):
                                        price_cap = 0.0  # Default fallback
                                else:
                                    price_cap = 0.0  # Default for None values
                                
                                products_data.append({
                                    "id": product["id"],
                                    "product_link": product["product_link"],
                                    "price_cap": price_cap,
                                    "quantity": product.get("quantity", 1),
                                    "name": product.get("product_name", "Unknown Product")
                                })
                            
                            job_data["products"] = products_data
                
                        # If full automation, include optional GST details and steal deal product for order summary
                        if automation_type in ['full_automation', 'full']:
                            if gstin is not None:
                                job_data["gstin"] = gstin
                            if business_name is not None:
                                job_data["business_name"] = business_name
                            if steal_deal_product is not None:
                                job_data["steal_deal_product"] = steal_deal_product
                        
                        # If this is an add_address job, include the address data
                        if automation_type == 'add_address':
                            
                            # Generate random data for each account
                            # Use dynamic randomization from settings
                            random_name = self.generate_random_name()
                            random_phone = self.generate_random_phone()
                            random_address = self.generate_random_address()
                
                            job_data["address_data"] = {
                                "name": random_name,
                                "phone": random_phone,
                                "pincode": "400010", # Static pincode as requested
                                "locality": "Mumbai",
                                "address": random_address,
                                "addressType": "HOME" 
                            }
                
                        # If this is an add_coupon job, include the coupon code
                        if automation_type == 'add_coupon':
                            if account_selection_mode == 'custom' and 'coupon_map' in locals() and coupon_map:
                                # Map coupon by email; safe due to earlier validation
                                mapped_code = coupon_map.get(account["email"])
                                if mapped_code:
                                    job_data["coupon_code"] = mapped_code
                            elif coupon_code:
                                # Fallback: single coupon for all (range mode or no coupon_codes provided)
                                job_data["coupon_code"] = coupon_code
                
                        # Determine the correct job type based on the automation selected
                        if automation_type == 'add_address':
                            job_type = "add_address"
                        elif automation_type == 'add_coupon':
                            job_type = "add_coupon"
                        elif automation_type == 'remove_addresses':
                            job_type = "remove_addresses"
                        elif automation_type == 'clear_cart':
                            job_type = "clear_cart"
                        else:
                            job_type = "flipkart_login"
                
                        batch_jobs.append({
                            "job_type": job_type,
                            "job_data": job_data,
                            "priority": 8
                        })
                    
                    batches.append({
                        "batch_id": batch_id,
                        "accounts": [acc["email"] for acc in batch_accounts],
                        "jobs": batch_jobs,
                        "status": BatchStatus.PENDING.value
                    })
                
                # Calculate total jobs
                total_jobs = sum(len(batch["jobs"]) for batch in batches)
                
                # Prepare config data based on selection mode
                config_data = {
                    "batch_session_id": batch_session_id,
                    "automation_type": automation_type,
                    "view_mode": view_mode,
                    "batch_size": batch_size,
                    "account_selection_mode": account_selection_mode,
                    "batches": len(batches)
                }
                
                if account_selection_mode == 'range':
                    config_data["account_range"] = f"{account_range_start}-{account_range_end}"
                else:
                    config_data["custom_account_emails"] = custom_account_emails
                    config_data["account_count"] = len(custom_account_emails)
                
                # Record automation session in database
                await conn.execute('''
                    INSERT INTO automation_sessions (
                        batch_session_id, automation_type, started_by, status,
                        batch_size, total_accounts, total_batches, account_range_start,
                        account_range_end, total_jobs, config
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ''', batch_session_id, automation_type, created_by, 'pending',
                    batch_size, total_accounts, len(batches), 
                    account_range_start if account_selection_mode == 'range' else None,
                    account_range_end if account_selection_mode == 'range' else None, 
                    total_jobs, json.dumps(config_data))
            
            # Store batch configuration
            self.batch_queues[batch_session_id] = batches
            
            # Start batch coordinator if not running
            if not self.running:
                await self.start_batch_coordinator()
            
            return {
                "success": True,
                "batch_session_id": batch_session_id,
                "total_batches": len(batches),
                "total_accounts": total_accounts,
                "batch_size": batch_size,
                "automation_type": automation_type,
                "total_jobs": total_jobs,
                "batches": [
                    {
                        "batch_id": batch["batch_id"],
                        "accounts": batch["accounts"],
                        "job_count": len(batch["jobs"])
                    }
                    for batch in batches
                ]
            }
            
        except Exception as e:
            logging.error(f"Failed to create batch automation: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def start_batch_coordinator(self):
        """Start the batch coordinator task"""
        if self.coordinator_task is None or self.coordinator_task.done():
            self.running = True
            self.coordinator_task = asyncio.create_task(self._batch_coordinator_loop())
            logging.info("Batch coordinator started")
    
    async def stop_batch_coordinator(self):
        """Stop the batch coordinator"""
        self.running = False
        if self.coordinator_task:
            self.coordinator_task.cancel()
            try:
                await self.coordinator_task
            except asyncio.CancelledError:
                pass
        logging.info("Batch coordinator stopped")
    
    async def _batch_coordinator_loop(self):
        """Main batch coordination loop"""
        from services.job_queue import job_queue
        
        while self.running:
            try:
                # Process each batch session
                for session_id, batches in list(self.batch_queues.items()):
                    await self._process_batch_session(session_id, batches)
                
                # Clean up completed sessions
                self._cleanup_completed_sessions()
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logging.error(f"Error in batch coordinator: {e}")
                await asyncio.sleep(10)
    
    async def _process_batch_session(self, session_id: str, batches: List[Dict]):
        """Process a single batch session"""
        from services.job_queue import job_queue
        
        try:
            for i, batch in enumerate(batches):
                batch_id = batch["batch_id"]
                
                if batch["status"] == BatchStatus.PENDING.value:
                    # Start this batch
                    logging.info(f"Starting batch {i+1}/{len(batches)}: {batch_id}")
                    batch["status"] = BatchStatus.RUNNING.value
                    batch["started_at"] = datetime.now()
                    # Mark session as running in DB for better UI feedback
                    asyncio.create_task(self._update_session_status(session_id, 'running'))
                    
                    # Add all jobs in this batch to the job queue
                    batch_job_ids = []
                    for job in batch["jobs"]:
                        job_id = await job_queue.add_job(
                            job_type=job["job_type"],
                            job_data=job["job_data"],
                            priority=job["priority"],
                            created_by=1  # System user
                        )
                        batch_job_ids.append(job_id)
                    
                    batch["job_ids"] = batch_job_ids
                    logging.info(f"Added {len(batch_job_ids)} jobs for batch {batch_id}")
                    
                    # Store active batch info
                    self.active_batches[batch_id] = batch
                    
                    # Only start one batch at a time - break here
                    break
                
                elif batch["status"] == BatchStatus.RUNNING.value:
                    # Check if this batch is complete
                    if await self._is_batch_complete(batch):
                        batch["status"] = BatchStatus.COMPLETED.value
                        batch["completed_at"] = datetime.now()
                        
                        if batch_id in self.active_batches:
                            del self.active_batches[batch_id]
                        
                        logging.info(f"Batch completed: {batch_id}")
                        
                        # Continue to next batch in next iteration
                    else:
                        # This batch is still running, don't start next batch
                        break
        
        except Exception as e:
            logging.error(f"Error processing batch session {session_id}: {e}")
    
    async def _is_batch_complete(self, batch: Dict) -> bool:
        """Check if all jobs in a batch are complete"""
        if "job_ids" not in batch:
            return False
        
        try:
            async with db.get_connection() as conn:
                # Check status of all jobs in this batch
                job_statuses = await conn.fetch(
                    "SELECT status FROM job_queue WHERE id = ANY($1)",
                    batch["job_ids"]
                )
            
            # All jobs must be completed or failed
            for status_row in job_statuses:
                status = status_row["status"]
                if status not in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                    return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error checking batch completion: {e}")
            return False
    
    async def _update_session_status(self, session_id: str, status: str, completed_batches: int = None, completed_jobs: int = None, failed_jobs: int = None):
        """Update automation session status in database"""
        try:
            async with db.get_connection() as conn:
                update_fields = ["status = $2"]
                params = [session_id, status]
                param_count = 2
                
                if completed_batches is not None:
                    param_count += 1
                    update_fields.append(f"completed_batches = ${param_count}")
                    params.append(completed_batches)
                
                if completed_jobs is not None:
                    param_count += 1
                    update_fields.append(f"completed_jobs = ${param_count}")
                    params.append(completed_jobs)
                
                if failed_jobs is not None:
                    param_count += 1
                    update_fields.append(f"failed_jobs = ${param_count}")
                    params.append(failed_jobs)
                
                if status in ['completed', 'failed', 'stopped']:
                    param_count += 1
                    update_fields.append(f"ended_at = ${param_count}")
                    params.append(datetime.now())
                
                query = f"UPDATE automation_sessions SET {', '.join(update_fields)} WHERE batch_session_id = $1"
                await conn.execute(query, *params)
            
        except Exception as e:
            logging.error(f"Failed to update session status: {e}")

    async def stop_session(self, session_id: str) -> Dict[str, Any]:
        """Stop further processing for a batch session: prevents starting pending batches.
        Allows the currently running batch (if any) to finish. Updates DB status to 'stopped'."""
        try:
            if session_id not in self.batch_queues:
                return {"success": False, "error": f"Batch session {session_id} not found or already finished"}

            batches = self.batch_queues[session_id]
            # Count completed and running
            completed_count = len([b for b in batches if b.get("status") == BatchStatus.COMPLETED.value])
            running_exists = any(b.get("status") == BatchStatus.RUNNING.value for b in batches)

            # Remove the session from further coordination to avoid starting new pending batches
            # Keep currently running batch (jobs already enqueued) unaffected
            del self.batch_queues[session_id]

            # Immediately mark session as completed (for UI), even if current batch is still finishing.
            # We still prevent any new pending batches from starting.
            await self._update_session_status(
                session_id,
                'completed',
                completed_batches=completed_count + (1 if running_exists else 0)
            )
            logging.info(f"Session {session_id} marked as completed after stop. Pending batches cancelled; running batch (if any) may still finish in background.")

            return {"success": True, "message": "Stopped. Marked as completed; pending batches cancelled."}
        except Exception as e:
            logging.error(f"Failed to stop session {session_id}: {e}")
            return {"success": False, "error": str(e)}

    async def _monitor_session_completion(self, session_id: str, poll_interval: float = 5.0):
        """Poll job_queue until all jobs for this session_id are terminal, then mark session as completed.
        This is used after a stop request to transition status from 'stopped' to 'completed' when the last running batch finishes."""
        try:
            while True:
                async with db.get_connection() as conn:
                    # Count non-terminal jobs for this session
                    row = await conn.fetchrow(
                        """
                        SELECT COUNT(*) AS cnt
                        FROM job_queue
                        WHERE job_data->>'batch_session_id' = $1
                          AND status NOT IN ('completed','failed')
                        """,
                        session_id
                    )
                    remaining = int(row['cnt']) if row and 'cnt' in row else 0

                if remaining == 0:
                    # All done, flip to completed
                    await self._update_session_status(session_id, 'completed')
                    logging.info(f"Session {session_id} marked as completed after stop (all jobs finished).")
                    break

                await asyncio.sleep(poll_interval)
        except Exception as e:
            logging.error(f"Monitor error for session {session_id}: {e}")

    def _cleanup_completed_sessions(self):
        """Remove completed batch sessions"""
        sessions_to_remove = []
        
        for session_id, batches in self.batch_queues.items():
            all_complete = all(
                batch["status"] == BatchStatus.COMPLETED.value 
                for batch in batches
            )
            
            if all_complete:
                sessions_to_remove.append(session_id)
                # Update database status to completed
                asyncio.create_task(self._update_session_status(
                    session_id, 'completed',
                    completed_batches=len(batches)
                ))
        
        for session_id in sessions_to_remove:
            del self.batch_queues[session_id]
            logging.info(f"Cleaned up completed batch session: {session_id}")
    
    def get_batch_status(self, session_id: str) -> Optional[Dict]:
        """Get status of a batch session"""
        if session_id not in self.batch_queues:
            return None
        
        batches = self.batch_queues[session_id]
        
        return {
            "session_id": session_id,
            "total_batches": len(batches),
            "completed_batches": len([b for b in batches if b["status"] == BatchStatus.COMPLETED.value]),
            "current_batch": next(
                (i+1 for i, b in enumerate(batches) if b["status"] == BatchStatus.RUNNING.value),
                None
            ),
            "batches": [
                {
                    "batch_id": batch["batch_id"],
                    "status": batch["status"],
                    "accounts": batch["accounts"],
                    "job_count": len(batch["jobs"]),
                    "started_at": batch.get("started_at"),
                    "completed_at": batch.get("completed_at")
                }
                for batch in batches
            ]
        }
    
    def get_all_active_sessions(self) -> Dict[str, Dict]:
        """Get all active batch sessions"""
        return {
            session_id: self.get_batch_status(session_id)
            for session_id in self.batch_queues.keys()
        }


# Global batch manager instance
batch_manager = BatchManager()
