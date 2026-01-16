#!/usr/bin/env python3
"""
Simple script to view automation logs from the command line
Usage: python view_logs.py [session_id|job_id] [--type session|job]
"""

import asyncio
import asyncpg
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def view_job_logs(job_id: int):
    """View logs for a specific job"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Get job info
        job = await conn.fetchrow("SELECT * FROM job_queue WHERE id = $1", job_id)
        if not job:
            print(f"❌ Job {job_id} not found")
            return
        
        print(f"📋 Job {job_id} - {job['job_type']} ({job['status']})")
        if job['job_data']:
            job_data = job['job_data']
            if isinstance(job_data, str):
                try:
                    job_data = json.loads(job_data)
                except:
                    job_data = {}
            if isinstance(job_data, dict) and 'email' in job_data:
                print(f"📧 Email: {job_data['email']}")
        print("-" * 80)
        
        # Get logs
        logs = await conn.fetch(
            """
            SELECT log_level, message, created_at, metadata
            FROM job_logs 
            WHERE job_id = $1 
            ORDER BY created_at ASC
            """,
            job_id
        )
        
        if not logs:
            print("📝 No logs found for this job")
            return
        
        for log in logs:
            timestamp = log['created_at'].strftime("%H:%M:%S")
            level_color = {
                'INFO': '🔵', 'info': '🔵',
                'WARNING': '🟡', 'warning': '🟡', 
                'ERROR': '🔴', 'error': '🔴',
                'DEBUG': '⚪', 'debug': '⚪'
            }.get(log['log_level'], '⚫')
            
            print(f"{timestamp} {level_color} [{log['log_level']}] {log['message']}")
            
    finally:
        await conn.close()

async def view_session_logs(session_id: int):
    """View logs for all jobs in a session"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Get session info
        session = await conn.fetchrow(
            "SELECT * FROM automation_sessions WHERE id = $1", session_id
        )
        if not session:
            print(f"❌ Session {session_id} not found")
            return
        
        print(f"🎯 Session {session_id} - {session['automation_type']} ({session['status']})")
        print(f"📊 Progress: {session['completed_batches']}/{session['total_batches']} batches")
        print(f"👥 Accounts: {session['account_range_start']}-{session['account_range_end']}")
        print("-" * 80)
        
        batch_session_id = session['batch_session_id']
        
        # Get all jobs for this session
        jobs = await conn.fetch(
            """
            SELECT jq.id, jq.job_type, jq.status, jq.job_data
            FROM job_queue jq
            WHERE jq.job_data->>'batch_session_id' = $1
            ORDER BY jq.created_at ASC
            """,
            batch_session_id
        )
        
        if not jobs:
            print("📝 No jobs found for this session")
            return
        
        print(f"🔧 Found {len(jobs)} jobs in this session")
        print("-" * 80)
        
        # Get all logs for all jobs in this session
        all_logs = []
        for job in jobs:
            # Parse job_data if it's a string
            job_data = job['job_data']
            if isinstance(job_data, str):
                try:
                    job_data = json.loads(job_data)
                except:
                    job_data = {}
            
            email = job_data.get('email', 'Unknown') if isinstance(job_data, dict) else 'Unknown'
            
            logs = await conn.fetch(
                """
                SELECT log_level, message, created_at, metadata
                FROM job_logs 
                WHERE job_id = $1 
                ORDER BY created_at ASC
                """,
                job['id']
            )
            
            # Add job info to each log
            for log in logs:
                log = dict(log)
                log['job_id'] = job['id']
                log['email'] = email
                all_logs.append(log)
        
        # Sort all logs by timestamp
        all_logs.sort(key=lambda x: x['created_at'])
        
        if not all_logs:
            print("📝 No logs found for this session")
            return
        
        current_email = None
        for log in all_logs:
            timestamp = log['created_at'].strftime("%H:%M:%S")
            level_color = {
                'INFO': '🔵', 'info': '🔵',
                'WARNING': '🟡', 'warning': '🟡', 
                'ERROR': '🔴', 'error': '🔴',
                'DEBUG': '⚪', 'debug': '⚪'
            }.get(log['log_level'], '⚫')
            
            # Show email header when it changes
            if log['email'] != current_email:
                current_email = log['email']
                print(f"\n👤 {current_email}")
                print("-" * 40)
            
            print(f"{timestamp} {level_color} [{log['log_level']}] {log['message']}")
            
    finally:
        await conn.close()

async def list_recent_sessions():
    """List recent automation sessions"""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        sessions = await conn.fetch(
            """
            SELECT id, batch_session_id, automation_type, status, 
                   completed_batches, total_batches, started_at
            FROM automation_sessions 
            ORDER BY started_at DESC 
            LIMIT 10
            """)
        
        if not sessions:
            print("📝 No recent sessions found")
            return
        
        print("🕒 Recent Automation Sessions:")
        print("-" * 80)
        for session in sessions:
            started = session['started_at'].strftime("%Y-%m-%d %H:%M:%S")
            progress = f"{session['completed_batches']}/{session['total_batches']}"
            print(f"ID: {session['id']:2d} | {session['automation_type']:12s} | {session['status']:8s} | {progress:5s} | {started}")
            
    finally:
        await conn.close()

def print_usage():
    print("🔍 Flipkart Automation Log Viewer")
    print("=" * 50)
    print("Usage:")
    print("  python view_logs.py                    # List recent sessions")
    print("  python view_logs.py 123 --type job    # View logs for job ID 123")
    print("  python view_logs.py 456 --type session # View logs for session ID 456")
    print("")
    print("Examples:")
    print("  python view_logs.py                    # Show recent sessions")
    print("  python view_logs.py 1 --type session  # Show all logs for session 1")
    print("  python view_logs.py 5 --type job      # Show logs for job 5")

async def main():
    if len(sys.argv) == 1:
        # No arguments - show recent sessions
        await list_recent_sessions()
    elif len(sys.argv) == 3 and sys.argv[2] == '--type':
        print_usage()
    elif len(sys.argv) == 4 and sys.argv[2] == '--type':
        try:
            id_value = int(sys.argv[1])
            log_type = sys.argv[3]
            
            if log_type == 'job':
                await view_job_logs(id_value)
            elif log_type == 'session':
                await view_session_logs(id_value)
            else:
                print("❌ Invalid type. Use 'job' or 'session'")
                print_usage()
        except ValueError:
            print("❌ Invalid ID. Please provide a numeric ID")
            print_usage()
    else:
        print_usage()

if __name__ == "__main__":
    asyncio.run(main())
