#!/usr/bin/env python3
"""
Log Management Utility for DiceBot

This utility helps manage log files and database log entries to prevent
server crashes due to large log files.

Features:
- Force log rotation
- Clean up old database logs
- Show log status and statistics
- Run all operations at once

Usage:
    python utils/log_management.py --rotate    # Force log rotation
    python utils/log_management.py --cleanup   # Clean up old database logs
    python utils/log_management.py --status    # Show log status
    python utils/log_management.py --all       # Run all operations
"""

__version__ = "1.0.0"

import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config_manager import get_config
from database.adapter import db_adapter
from database.connection import init_database
from utils.logging_utils import setup_logging

def get_log_file_info(log_file_path: str) -> dict:
    """Get information about the log file."""
    if not os.path.exists(log_file_path):
        return {"exists": False}
    
    stat = os.stat(log_file_path)
    size_mb = stat.st_size / (1024 * 1024)
    modified = datetime.fromtimestamp(stat.st_mtime)
    
    return {
        "exists": True,
        "size_mb": round(size_mb, 2),
        "size_bytes": stat.st_size,
        "modified": modified,
        "path": log_file_path
    }

def force_log_rotation(log_file_path: str) -> bool:
    """Force log rotation by creating a large dummy log entry."""
    try:
        # Get current logger and force a rotation by logging a large message
        logger = logging.getLogger("log_management")
        
        # Create a message that will trigger rotation
        large_message = "MANUAL LOG ROTATION TRIGGERED - " + "X" * 1000
        logger.info(large_message)
        
        # Check if rotation occurred by looking for backup files
        backup_file = f"{log_file_path}.1"
        if os.path.exists(backup_file):
            print(f"✅ Log rotation successful - backup created: {backup_file}")
            return True
        else:
            print("ℹ️  Log rotation may not have been triggered (file size threshold not reached)")
            return True
    except Exception as e:
        print(f"❌ Error forcing log rotation: {e}")
        return False

def cleanup_database_logs(days_to_keep: int = 30) -> bool:
    """Clean up old database log entries."""
    try:
        success = db_adapter.cleanup_old_logs(days_to_keep=days_to_keep)
        if success:
            print(f"✅ Database log cleanup completed (keeping {days_to_keep} days)")
        else:
            print("❌ Database log cleanup failed")
        return success
    except Exception as e:
        print(f"❌ Error during database log cleanup: {e}")
        return False

def show_log_status(config) -> None:
    """Show current log status."""
    print("\n📊 Log Status Report")
    print("=" * 50)
    
    # File log status
    log_config = config.get_section("logging")
    log_file = log_config.get("file", "logs/bot.log")
    max_size_mb = log_config.get("max_file_size_mb", 10)
    backup_count = log_config.get("backup_count", 5)
    retention_days = log_config.get("database_log_retention_days", 30)
    
    print(f"\n📁 File Logging:")
    print(f"   Log file: {log_file}")
    print(f"   Max size: {max_size_mb} MB")
    print(f"   Backup count: {backup_count}")
    
    # Check main log file
    info = get_log_file_info(log_file)
    if info["exists"]:
        print(f"   Current size: {info['size_mb']} MB ({info['size_bytes']} bytes)")
        print(f"   Last modified: {info['modified']}")
        
        # Check if close to rotation threshold
        if info["size_mb"] > max_size_mb * 0.8:
            print(f"   ⚠️  Warning: Log file is {info['size_mb']}/{max_size_mb} MB (close to rotation)")
        else:
            print(f"   ✅ Log file size OK ({info['size_mb']}/{max_size_mb} MB)")
    else:
        print(f"   ❌ Log file does not exist: {log_file}")
    
    # Check backup files
    backup_files = []
    for i in range(1, backup_count + 1):
        backup_path = f"{log_file}.{i}"
        if os.path.exists(backup_path):
            backup_info = get_log_file_info(backup_path)
            backup_files.append((backup_path, backup_info))
    
    if backup_files:
        print(f"\n   📦 Backup files ({len(backup_files)} found):")
        for backup_path, backup_info in backup_files:
            print(f"      {os.path.basename(backup_path)}: {backup_info['size_mb']} MB")
    else:
        print(f"\n   📦 No backup files found")
    
    # Database log status
    print(f"\n🗄️  Database Logging:")
    print(f"   Retention period: {retention_days} days")
    print(f"   Cleanup scheduled: Daily at 02:00 AM")
    
    if db_adapter.use_database:
        try:
            # Get recent log count
            recent_logs = db_adapter.get_log_entries(limit=1000)
            print(f"   Recent entries: {len(recent_logs)} (last 1000)")
            
            if recent_logs:
                oldest = min(recent_logs, key=lambda x: x['timestamp'])
                newest = max(recent_logs, key=lambda x: x['timestamp'])
                print(f"   Date range: {oldest['timestamp'][:10]} to {newest['timestamp'][:10]}")
        except Exception as e:
            print(f"   ❌ Error querying database logs: {e}")
    else:
        print(f"   ℹ️  Database logging disabled (USE_DATABASE=False)")
    
    print("\n" + "=" * 50)

def main():
    parser = argparse.ArgumentParser(
        description="Log Management Utility for DiceBot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --status                    Show current log status
  %(prog)s --rotate                   Force log file rotation
  %(prog)s --cleanup --days 14        Clean logs older than 14 days
  %(prog)s --all                      Run all operations"""
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--rotate", action="store_true", 
                       help="Force log rotation by creating a large log entry")
    parser.add_argument("--cleanup", action="store_true", 
                       help="Clean up old database log entries")
    parser.add_argument("--status", action="store_true", 
                       help="Show detailed log status and statistics")
    parser.add_argument("--all", action="store_true", 
                       help="Run all operations (status, rotate, cleanup)")
    parser.add_argument("--days", type=int, default=30, metavar="N",
                       help="Number of days to keep logs during cleanup (default: %(default)s)")
    
    args = parser.parse_args()
    
    # Load configuration
    config = get_config()
    log_config = config.get_section("logging")
    
    # Setup logging
    setup_logging(
        log_level=log_config.get("level", "INFO"),
        log_file=log_config.get("file"),
        json_format=log_config.get("json_format", False),
        max_file_size_mb=log_config.get("max_file_size_mb", 10),
        backup_count=log_config.get("backup_count", 5)
    )
    
    # Initialize database for log operations
    init_database()
    
    if not any([args.rotate, args.cleanup, args.status, args.all]):
        parser.print_help()
        return
    
    print("🔧 Log Management Utility")
    print("=" * 30)
    
    success = True
    
    if args.status or args.all:
        show_log_status(config)
    
    if args.rotate or args.all:
        print("\n🔄 Forcing log rotation...")
        log_file = log_config.get("file", "logs/bot.log")
        if not force_log_rotation(log_file):
            success = False
    
    if args.cleanup or args.all:
        print(f"\n🧹 Cleaning up database logs (keeping {args.days} days)...")
        if not cleanup_database_logs(args.days):
            success = False
    
    if success:
        print("\n✅ All operations completed successfully!")
    else:
        print("\n❌ Some operations failed. Check the logs for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()