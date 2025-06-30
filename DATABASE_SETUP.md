# Database Setup Guide

This guide will help you set up PostgreSQL for your DiceBot and migrate from JSON storage.

## Overview

The bot now supports both JSON file storage (default) and PostgreSQL database storage. You can switch between them using the `USE_DATABASE` environment variable.

## Prerequisites

### 1. Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

**Windows:**
Download and install from [PostgreSQL official website](https://www.postgresql.org/download/windows/)

### 2. Create Database and User

```bash
# Connect to PostgreSQL as superuser
sudo -u postgres psql

# Create database
CREATE DATABASE dicebot;

# Create user (replace 'your_password' with a secure password)
CREATE USER dicebot_user WITH PASSWORD 'your_password';

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE dicebot TO dicebot_user;

# Exit PostgreSQL
\q
```

## Configuration

### 1. Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and configure your database settings:

```env
# Enable database usage
USE_DATABASE=true

# Option 1: Use DATABASE_URL (recommended)
DATABASE_URL=postgresql://dicebot_user:your_password@localhost:5432/dicebot

# Option 2: Use individual settings
# DB_HOST=localhost
# DB_PORT=5432
# DB_NAME=dicebot
# DB_USER=dicebot_user
# DB_PASSWORD=your_password
```

### 2. Install Dependencies

The required dependencies should already be in `requirements.txt`. Install them:

```bash
pip install -r requirements.txt
```

## Database Initialization

The database tables will be created automatically when you first run the bot with `USE_DATABASE=true`.

To test the connection manually:

```python
from database.connection import init_database

if init_database():
    print("Database connection successful!")
else:
    print("Database connection failed!")
```

## Data Migration

If you have existing data in JSON format, you can migrate it to PostgreSQL:

### 1. Backup Your Data

Before migration, ensure you have a backup of your JSON data:
```bash
cp data.json data.json.manual_backup
```

### 2. Run Migration

```bash
python migrate_to_db.py
```

The migration script will:
- Check database connectivity
- Create a backup of your JSON file
- Transfer all data to PostgreSQL
- Provide a summary of migrated data

### 3. Verify Migration

After migration:
1. Test your bot functionality
2. Check that all player stats, scores, and history are preserved
3. If everything works correctly, you can delete the backup files

## Database Schema

The database includes the following tables:

- **users**: User information and referral data
- **chats**: Chat information and match counters
- **player_stats**: Player statistics per chat
- **games**: Game/match records
- **bets**: Individual bet records
- **admin_data**: Admin points and permissions

## Switching Between Storage Methods

### From JSON to Database
1. Set `USE_DATABASE=true` in `.env`
2. Run migration: `python migrate_to_db.py`
3. Restart your bot

### From Database to JSON
1. Set `USE_DATABASE=false` in `.env`
2. Restart your bot
3. The bot will continue using your existing JSON files

## Production Deployment (Render)

### 1. Database Setup

On Render:
1. Create a PostgreSQL database service
2. Note the connection details provided

### 2. Environment Variables

In your Render web service, set:
```
USE_DATABASE=true
DATABASE_URL=postgresql://user:password@host:port/database
```

### 3. Migration

For production migration:
1. Deploy your bot with `USE_DATABASE=false` first
2. Upload your JSON data
3. Change `USE_DATABASE=true`
4. Run migration via Render shell or deploy script

## Troubleshooting

### Connection Issues

**Error: "connection refused"**
- Ensure PostgreSQL is running: `brew services start postgresql` (macOS)
- Check if the port is correct (default: 5432)

**Error: "authentication failed"**
- Verify username and password
- Check database name

**Error: "database does not exist"**
- Create the database: `createdb dicebot`

### Migration Issues

**Error: "JSON file not found"**
- Ensure your JSON data file exists
- Check the `DATA_FILE_PATH` in settings

**Error: "Database tables not created"**
- The bot will create tables automatically
- Ensure the user has CREATE privileges

### Performance Issues

**Slow queries**
- The database includes optimized indexes
- For large datasets, consider data archival

**High memory usage**
- Monitor connection pooling
- Adjust query limits if needed

## Maintenance

### Regular Backups

```bash
# Create database backup
pg_dump -h localhost -U dicebot_user dicebot > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -h localhost -U dicebot_user dicebot < backup_20231201.sql
```

### Data Cleanup

To clean old game data (if needed):
```sql
-- Delete games older than 30 days
DELETE FROM games WHERE created_at < NOW() - INTERVAL '30 days';

-- Delete associated bets
DELETE FROM bets WHERE game_id NOT IN (SELECT id FROM games);
```

## Support

If you encounter issues:
1. Check the logs for detailed error messages
2. Verify your database configuration
3. Ensure all dependencies are installed
4. Test database connectivity separately

The bot includes comprehensive logging to help diagnose issues.