# Payout Double Deduction Fix

## Problem Identified

The wallet was being deducted twice during the betting process:

1. **First deduction**: In `place_bet()` function, the wallet was deducted locally:
   ```python
   current_player["score"] -= main_score_used  # Line 236
   ```

2. **Second deduction**: In the same function, when `USE_DATABASE=True`, the wallet was deducted again via database update:
   ```python
   db_adapter.update_player_stats(user_id, chat_id, -main_score_used, False, 0)  # Line 277
   ```

This resulted in users losing twice the bet amount from their wallet balance.

## Solution Implemented

### 1. Conditional Local Deduction

Modified the local deduction to only occur when database is not being used:

```python
# Before (always deducted locally):
current_player["score"] -= main_score_used

# After (conditional deduction):
if not USE_DATABASE:
    current_player["score"] -= main_score_used
```

### 2. Database Synchronization

When using database mode, after the database update, we now synchronize the local player data:

```python
if USE_DATABASE:
    try:
        # Update database first
        db_adapter.update_player_stats(user_id, chat_id, -main_score_used, False, 0)
        
        # Get fresh player data from database to sync local data
        updated_stats = db_adapter.get_or_create_player_stats(user_id, chat_id, username)
        current_player.update({
            "score": updated_stats["score"],
            "total_wins": updated_stats["total_wins"],
            "total_losses": updated_stats["total_losses"],
            "total_bets": updated_stats["total_bets"]
        })
```

### 3. Fallback Error Handling

Improved error handling to ensure proper deduction even if database operations fail:

```python
except Exception as db_error:
    logger.error(f"Database error during bet placement for user {user_id}: {db_error}")
    # Fallback: deduct from local data if database update failed
    current_player["score"] -= main_score_used
    logger.info(f"Fallback to local deduction: {main_score_used} for user {user_id}")
```

## Files Modified

- **`game/game_logic.py`**: Fixed double deduction in `place_bet()` function (lines 236, 277-302)

## Testing Results

### Non-Database Mode
✅ **PASSED**: Wallet correctly deducted once locally
- Initial balance: 1000
- Bet amount: 100
- Final balance: 900 (correct)

### Database Mode
✅ **LOGIC FIXED**: Double deduction eliminated
- Database handles the deduction
- Local data synchronized from database
- No duplicate deductions

## Impact

- **User Experience**: Players' wallets are now correctly deducted only once per bet
- **Data Integrity**: Local and database player stats remain synchronized
- **System Reliability**: Proper fallback handling ensures consistent behavior
- **Backward Compatibility**: Non-database mode continues to work correctly

## Verification

The fix ensures that:
1. In non-database mode: Only local deduction occurs
2. In database mode: Only database deduction occurs, with local sync
3. Error scenarios: Fallback deduction prevents data loss
4. Payout logic: Remains unchanged and working correctly

This resolves the reported issue where "wallet is deducted again at the payout" - the issue was actually in the betting phase, not the payout phase.