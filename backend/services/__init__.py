"""
Services package for Flipkart Automation System
Contains job queue and automation worker services
"""

from .job_queue import job_queue, add_job, get_job_status, get_job_logs, register_worker, LogLevel

# Import automation_worker for registration side-effects
try:
    from . import automation_worker
except ImportError:
    import logging
    logging.error("Failed to import automation_worker for registration")

__all__ = [
    'job_queue',
    'add_job',
    'get_job_status', 
    'get_job_logs',
    'register_worker',
    'LogLevel'
]
