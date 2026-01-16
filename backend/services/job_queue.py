"""
Simple Job Queue Service using PostgreSQL and asyncio
Handles background job processing without external dependencies
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
import traceback

from database import DATABASE_URL
import asyncpg
from database import db


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class LogLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class JobQueue:
    def __init__(self):
        self.workers: Dict[str, Callable] = {}
        self.running = False
        self.worker_tasks: List[asyncio.Task] = []
        self.max_workers = 3
        self.poll_interval = 2  # seconds
        
    def register_worker(self, job_type: str, worker_func: Callable):
        """Register a worker function for a specific job type"""
        self.workers[job_type] = worker_func
        logging.info(f"Registered worker for job type: {job_type}")
    
    async def add_job(
        self,
        job_type: str,
        job_data: Dict[str, Any],
        priority: int = 0,
        max_attempts: int = 3,
        created_by: Optional[int] = None
    ) -> int:
        """Add a new job to the queue"""
        async with db.get_connection() as conn:
            job_id = await conn.fetchval(
                """
                INSERT INTO job_queue (job_type, job_data, priority, max_attempts, created_by)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                job_type, json.dumps(job_data), priority, max_attempts, created_by
            )

            await self.log_job(job_id, LogLevel.INFO, f"Job created: {job_type}")
            logging.info(f"Added job {job_id} of type {job_type}")
            return job_id
    
    async def get_next_job(self) -> Optional[Dict[str, Any]]:
        """Get the next pending job from the queue using a single transaction for claim+update."""
        async with db.get_connection() as conn:
            async with conn.transaction():
                # Get highest priority pending job and lock it in the same transaction
                job = await conn.fetchrow(
                    """
                    SELECT * FROM job_queue 
                    WHERE status = $1 AND attempts < max_attempts
                    ORDER BY priority DESC, created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """,
                    JobStatus.PENDING.value
                )

                if job:
                    # Mark job as running within the same transaction
                    await conn.execute(
                        """
                        UPDATE job_queue 
                        SET status = $1, started_at = $2, attempts = attempts + 1, updated_at = $3
                        WHERE id = $4
                        """,
                        JobStatus.RUNNING.value, datetime.utcnow(), datetime.utcnow(), job['id']
                    )
                    return dict(job)

                return None
    
    async def complete_job(self, job_id: int, result: Optional[Dict[str, Any]] = None):
        """Mark a job as completed"""
        async with db.get_connection() as conn:
            await conn.execute(
                """
                UPDATE job_queue 
                SET status = $1, completed_at = $2, updated_at = $3
                WHERE id = $4
                """,
                JobStatus.COMPLETED.value, datetime.utcnow(), datetime.utcnow(), job_id
            )

            result_msg = f"Job completed successfully"
            if result:
                result_msg += f" - Result: {json.dumps(result)}"

            await self.log_job(job_id, LogLevel.INFO, result_msg)
            logging.info(f"Job {job_id} completed successfully")
    
    async def fail_job(self, job_id: int, error_message: str, retry: bool = True):
        """Mark a job as failed"""
        async with db.get_connection() as conn:
            job = await conn.fetchrow("SELECT * FROM job_queue WHERE id = $1", job_id)

            if job and retry and job['attempts'] < job['max_attempts']:
                # Schedule for retry
                await conn.execute(
                    """
                    UPDATE job_queue 
                    SET status = $1, error_message = $2, updated_at = $3
                    WHERE id = $4
                    """,
                    JobStatus.PENDING.value, error_message, datetime.utcnow(), job_id
                )

                await self.log_job(job_id, LogLevel.WARNING, f"Job failed, will retry: {error_message}")
                logging.warning(f"Job {job_id} failed, scheduled for retry: {error_message}")
            else:
                # Mark as permanently failed
                await conn.execute(
                    """
                    UPDATE job_queue 
                    SET status = $1, error_message = $2, completed_at = $3, updated_at = $4
                    WHERE id = $5
                    """,
                    JobStatus.FAILED.value, error_message, datetime.utcnow(), datetime.utcnow(), job_id
                )

                await self.log_job(job_id, LogLevel.ERROR, f"Job permanently failed: {error_message}")
                logging.error(f"Job {job_id} permanently failed: {error_message}")
    
    async def log_job(self, job_id: int, level: LogLevel, message: str, metadata: Optional[Dict] = None):
        """Add a log entry for a job"""
        async with db.get_connection() as conn:
            await conn.execute(
                """
                INSERT INTO job_logs (job_id, log_level, message, metadata)
                VALUES ($1, $2, $3, $4)
                """,
                job_id, level.value, message, json.dumps(metadata) if metadata else None
            )
    
    async def get_job_status(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Get the current status of a job"""
        async with db.get_connection() as conn:
            job = await conn.fetchrow("SELECT * FROM job_queue WHERE id = $1", job_id)
            if job:
                return dict(job)
            return None
    
    async def get_job_logs(self, job_id: int) -> List[Dict[str, Any]]:
        """Get logs for a specific job"""
        async with db.get_connection() as conn:
            logs = await conn.fetch(
                """
                SELECT * FROM job_logs 
                WHERE job_id = $1 
                ORDER BY created_at ASC
                """,
                job_id
            )
            return [dict(log) for log in logs]
    
    async def worker_loop(self):
        """Main worker loop that processes jobs"""
        logging.info("Worker loop started")
        
        while self.running:
            try:
                job = await self.get_next_job()
                
                if job:
                    job_id = job['id']
                    job_type = job['job_type']
                    # Log that we've picked a job and mark start
                    try:
                        await self.log_job(job_id, LogLevel.INFO, f"Job started (attempt {job.get('attempts', 0) + 1})")
                    except Exception as log_err:
                        logging.warning(f"Failed to log job start for {job_id}: {log_err}")

                    # Robustly decode JSONB/text job_data
                    raw_data = job.get('job_data')
                    if isinstance(raw_data, (dict, list)):
                        job_data = raw_data
                    else:
                        try:
                            job_data = json.loads(raw_data) if raw_data is not None else {}
                        except Exception:
                            # Fall back to empty dict if decode fails
                            job_data = {}
                    
                    if job_type in self.workers:
                        try:
                            await self.log_job(job_id, LogLevel.INFO, f"Processing {job_type} job")
                            
                            # Execute the worker function
                            worker_func = self.workers[job_type]
                            result = await worker_func(job_data, job_id)
                            
                            # Mark as completed
                            await self.complete_job(job_id, result)
                            
                        except Exception as e:
                            error_msg = f"Worker error: {str(e)}\n{traceback.format_exc()}"
                            await self.fail_job(job_id, error_msg)
                    else:
                        error_msg = f"No worker registered for job type: {job_type}"
                        await self.fail_job(job_id, error_msg, retry=False)
                else:
                    # No jobs available, wait before checking again
                    await asyncio.sleep(self.poll_interval)
                    
            except Exception as e:
                logging.error(f"Worker loop error: {e}\n{traceback.format_exc()}")
                await asyncio.sleep(self.poll_interval)
    
    async def start(self):
        """Start the job queue workers"""
        if self.running:
            return
            
        self.running = True
        logging.info(f"Starting job queue with {self.max_workers} workers")
        
        # Start worker tasks
        for i in range(self.max_workers):
            task = asyncio.create_task(self.worker_loop())
            self.worker_tasks.append(task)
            
        logging.info("Job queue started successfully")
    
    async def stop(self):
        """Stop the job queue workers"""
        if not self.running:
            return
            
        logging.info("Stopping job queue...")
        self.running = False
        
        # Cancel all worker tasks
        for task in self.worker_tasks:
            task.cancel()
            
        # Wait for tasks to complete
        if self.worker_tasks:
            await asyncio.gather(*self.worker_tasks, return_exceptions=True)
            
        self.worker_tasks.clear()
        logging.info("Job queue stopped")
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get statistics about the job queue"""
        async with db.get_connection() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_jobs,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_jobs,
                    COUNT(*) FILTER (WHERE status = 'running') as running_jobs,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_jobs,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_jobs
                FROM job_queue
                """
            )

            return dict(stats) if stats else {}


# Global job queue instance
job_queue = JobQueue()


# Convenience functions
async def add_job(job_type: str, job_data: Dict[str, Any], priority: int = 0, created_by: Optional[int] = None) -> int:
    """Add a job to the queue"""
    return await job_queue.add_job(job_type, job_data, priority, created_by=created_by)


async def get_job_status(job_id: int) -> Optional[Dict[str, Any]]:
    """Get job status"""
    return await job_queue.get_job_status(job_id)


async def get_job_logs(job_id: int) -> List[Dict[str, Any]]:
    """Get job logs"""
    return await job_queue.get_job_logs(job_id)


def register_worker(job_type: str):
    """Decorator to register a worker function"""
    def decorator(func: Callable):
        job_queue.register_worker(job_type, func)
        return func
    return decorator
