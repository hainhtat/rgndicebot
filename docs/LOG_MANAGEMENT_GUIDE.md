# Log Management Guide

This guide explains how the bot handles logging to prevent server crashes from large log files.

## Problem

Without proper log management, log files can grow indefinitely and cause:
- **Disk space exhaustion** leading to server crashes
- **Performance degradation** from large file operations
- **Memory issues** when processing huge log files
- **Backup failures** due to oversized files

## Solution

The bot now implements a comprehensive log management system with:

### 1. File Log Rotation

**Automatic Rotation**: Log files are automatically rotated when they reach a configurable size limit.

**Configuration** (in `config/config_manager.py`):
```python
"logging": {
    "level": "INFO",
    "file": "logs/bot.log",
    "max_file_size_mb": 10,        # Rotate when file reaches 10MB
    "backup_count": 5,             # Keep 5 backup files
    "json_format": False
}
```

**How it works**:
- When `bot.log` reaches 10MB, it's renamed to `bot.log.1`
- Previous backups are shifted: `bot.log.1` → `bot.log.2`, etc.
- A new empty `bot.log` is created
- Only the 5 most recent backup files are kept
- Total disk usage is limited to ~60MB (6 files × 10MB)

### 2. Database Log Cleanup

**Automatic Cleanup**: Old database log entries are automatically deleted to prevent database bloat.

**Configuration**:
```python
"logging": {
    "database_log_retention_days": 30  # Keep logs for 30 days
}
```

**Schedule**: Cleanup runs daily at 2:00 AM, removing logs older than 30 days.

### 3. Environment Variables

You can override log settings using environment variables:

```bash
# Log rotation settings
DICEBOT_LOGGING_MAX_FILE_SIZE_MB=20
DICEBOT_LOGGING_BACKUP_COUNT=10
DICEBOT_LOGGING_DATABASE_LOG_RETENTION_DAYS=60

# Log level
DICEBOT_LOGGING_LEVEL=DEBUG
```

## Log Management Utility

A utility script is provided for manual log management:

```bash
# Show help and available options
python utils/log_management.py --help

# Check version
python utils/log_management.py --version

# Show current log status
python utils/log_management.py --status

# Force log rotation
python utils/log_management.py --rotate

# Clean up old database logs
python utils/log_management.py --cleanup --days 30

# Run all operations
python utils/log_management.py --all
```

### Example Status Output

```
📊 Log Status Report
==================================================

📁 File Logging:
   Log file: logs/bot.log
   Max size: 10 MB
   Backup count: 5
   Current size: 2.5 MB (2621440 bytes)
   Last modified: 2024-07-18 22:30:15
   ✅ Log file size OK (2.5/10 MB)

   📦 Backup files (2 found):
      bot.log.1: 10.0 MB
      bot.log.2: 10.0 MB

🗄️  Database Logging:
   Retention period: 30 days
   Cleanup scheduled: Daily at 02:00 AM
   Recent entries: 1000 (last 1000)
   Date range: 2024-06-18 to 2024-07-18
```

## Monitoring

### File System Monitoring

```bash
# Check log directory size
du -sh logs/

# List all log files with sizes
ls -lh logs/

# Monitor log file growth in real-time
tail -f logs/bot.log
```

### Database Monitoring

```sql
-- Check log entry count
SELECT COUNT(*) FROM log_entries;

-- Check oldest log entry
SELECT MIN(timestamp) FROM log_entries;

-- Check log entries by level
SELECT level, COUNT(*) FROM log_entries GROUP BY level;

-- Check database size (PostgreSQL)
SELECT pg_size_pretty(pg_database_size('dicebot_db'));
```

## Version Management

The log management utility includes version tracking for better maintenance:

- **Current Version**: 1.0.0
- **Version Command**: `python utils/log_management.py --version`
- **Changelog**: Track updates and improvements in utility functionality

### Version History
- **v1.0.0**: Initial release with file rotation, database cleanup, and status reporting

## Production Recommendations

### 1. Disk Space Monitoring

Set up alerts when disk usage exceeds 80%:

```bash
# Add to crontab for monitoring
0 */6 * * * df -h | awk '$5 > 80 {print $0}' | mail -s "Disk Space Alert" admin@example.com
```

### 2. Log Level Optimization

For production, use appropriate log levels:
- **INFO**: Normal production logging
- **WARNING**: For important events that need attention
- **ERROR**: For errors that need immediate attention
- **DEBUG**: Only for troubleshooting (generates many logs)

### 3. External Log Management

For high-traffic bots, consider:
- **Centralized logging** (ELK stack, Splunk)
- **Log streaming** to external services
- **Compressed log storage**
- **Log analysis tools**

### 4. Backup Strategy

```bash
# Compress and archive old logs
find logs/ -name "*.log.*" -mtime +7 -exec gzip {} \;

# Move old compressed logs to archive
find logs/ -name "*.gz" -mtime +30 -exec mv {} /archive/logs/ \;
```

## Troubleshooting

### Log Rotation Not Working

1. Check file permissions:
   ```bash
   ls -la logs/
   chmod 755 logs/
   chmod 644 logs/bot.log
   ```

2. Check disk space:
   ```bash
   df -h
   ```

3. Check log configuration:
   ```bash
   python utils/log_management.py --status
   ```

### Database Cleanup Failing

1. Check database connection
2. Verify `USE_DATABASE=true` in environment
3. Check database permissions
4. Review error logs for specific issues

### High Log Volume

If logs are growing too quickly:

1. **Reduce log level** from DEBUG to INFO
2. **Increase rotation size** (e.g., 50MB instead of 10MB)
3. **Reduce retention period** (e.g., 7 days instead of 30)
4. **Filter noisy log sources**

## Configuration Examples

### High-Traffic Bot
```python
"logging": {
    "level": "WARNING",                    # Reduce log volume
    "max_file_size_mb": 50,               # Larger files
    "backup_count": 3,                    # Fewer backups
    "database_log_retention_days": 7      # Shorter retention
}
```

### Development Environment
```python
"logging": {
    "level": "DEBUG",                     # Detailed logging
    "max_file_size_mb": 5,                # Smaller files
    "backup_count": 10,                   # More backups
    "database_log_retention_days": 3      # Short retention
}
```

### Production Environment
```python
"logging": {
    "level": "INFO",                      # Balanced logging
    "max_file_size_mb": 20,               # Reasonable size
    "backup_count": 5,                    # Standard backups
    "database_log_retention_days": 30     # Monthly retention
}
```

This log management system ensures your bot will never crash due to large log files while maintaining useful logging for debugging and monitoring.