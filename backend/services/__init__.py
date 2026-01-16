"""
Services package for Flipkart Automation System
Contains job queue and automation worker services
"""

from .job_queue import job_queue, add_job, get_job_status, get_job_logs, register_worker, LogLevel
from .automation_worker import automation_worker

__all__ = [
    'job_queue',
    'add_job',
    'get_job_status', 
    'get_job_logs',
    'register_worker',
    'LogLevel',
    'automation_worker'
]
