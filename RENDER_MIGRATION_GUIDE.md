# Render Database Migration Guide

## Problem
The production database on Render is missing the `bonus_points` and `welcome_bonuses_received` columns in the `users` table, causing the following error:

```
(psycopg2.errors.UndefinedColumn) column users.bonus_points does not exist
LINE 1: ..., users.referral_points AS users_referral_points, users.bonu...
```

This causes:
- ❌ Bot crashes when users try to place bets
- ❌ User scores disappear (showing 0 balance)
- ❌ "Insufficient funds" errors even for users with points
- ❌ Welcome bonus system fails

## Solution
Run the migration script to add the missing columns to the production database.

## Quick Fix Options

### 🚀 Option 1: Automatic Migration (Recommended)

**Use the deployment script that automatically runs migration:**

1. **Change your Render start command** to:
   ```bash
   python3 deploy.py
   ```

2. **Deploy and check logs** for:
   ```
   ✅ Migration completed successfully
   🤖 Starting Telegram bot...
   ```

### 🔧 Option 2: Manual Migration

**Run migration manually via Render Shell:**

1. **Open Render Shell** for your service
2. **Run the migration:**
   ```bash
   python3 render_migration.py
   ```
3. **Restart your service**

### 🔍 Option 3: Environment Check First

**Diagnose issues before fixing:**

1. **Check environment setup:**
   ```bash
   python3 check_env.py
   ```
2. **Fix any missing environment variables**
3. **Then run Option 1 or 2**

### 🤖 Option 4: Built-in Auto Migration

**The bot now automatically checks and runs migration on startup:**

- Migration runs automatically when `main.py` starts
- No manual intervention needed
- Safe to run multiple times
- Check logs for migration status

## Detailed Steps

### Option 1: Run Migration Script (Recommended)

1. **Upload the migration script** to your Render service:
   - Ensure `render_migration.py` is in your repository
   - Deploy the updated code to Render

2. **Run the migration** via Render Shell:
   ```bash
   python3 render_migration.py
   ```

3. **Verify the migration** was successful by checking the logs for:
   ```
   ✅ bonus_points column added successfully
   ✅ welcome_bonuses_received column added successfully
   🎉 Migration completed successfully!
   ```

### Option 2: Manual SQL Commands

If you have direct database access, run these SQL commands:

```sql
-- Add bonus_points column
ALTER TABLE users ADD COLUMN bonus_points INTEGER DEFAULT 0;

-- Add welcome_bonuses_received column
ALTER TABLE users ADD COLUMN welcome_bonuses_received JSON DEFAULT '{}';

-- Verify columns were added
SELECT column_name, data_type, column_default
FROM information_schema.columns 
WHERE table_name = 'users' 
AND column_name IN ('bonus_points', 'welcome_bonuses_received')
ORDER BY column_name;
```

### Option 3: Environment Variable Method

Add this to your Render environment variables and restart:
```
RUN_MIGRATION=true
```

Then modify your `main.py` to check for this variable and run the migration on startup.

## Verification

After running the migration, verify it worked by:

1. **Check the logs** for successful migration messages
2. **Test user registration** - new users should be able to join without errors
3. **Test betting** - users should be able to place bets without score disappearing
4. **Check welcome bonus** - new group members should receive welcome bonuses

## Files Created

- `render_migration.py` - Standalone migration script
- `RENDER_MIGRATION_GUIDE.md` - This guide

## Important Notes

- The migration script is **safe to run multiple times** - it checks if columns exist before adding them
- The script includes **proper error handling** and **logging**
- **No data will be lost** - this only adds new columns with default values
- The migration is **backwards compatible** - existing functionality will continue to work

## Troubleshooting

If the migration fails:

1. **Check database permissions** - ensure the database user has ALTER TABLE privileges
2. **Check database connection** - verify DATABASE_URL environment variable is correct
3. **Check logs** for specific error messages
4. **Contact support** if database access issues persist

## After Migration

Once the migration is complete:

1. **Restart your Render service** to ensure all processes use the updated schema
2. **Monitor logs** for any remaining database errors
3. **Test all functionality** including betting, welcome bonuses, and score adjustments

The bot should now work correctly without the "column does not exist" errors.