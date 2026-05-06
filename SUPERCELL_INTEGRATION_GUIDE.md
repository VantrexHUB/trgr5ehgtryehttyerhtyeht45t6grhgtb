# Supercell Engine Integration Guide

## Overview

This is a complete refactoring of the Supercell checking system into modular, production-ready components:

1. **`supercell_engine.py`** - Core engine for checking accounts
2. **`bot_handlers.py`** - Bot integration with statistics tracking
3. **`supercell_bot_integration.py`** - Command handlers and bot interface

## Features

✅ **Complete Account Verification**
- Microsoft Hotmail authentication
- Profile information extraction
- Game detection (Clash Royale, Brawl Stars, Clash of Clans, Hay Day)

✅ **Full Statistics Tracking**
- Total accounts checked
- Valid accounts found
- Supercell accounts identified
- Per-game statistics
- Bad account tracking
- Error monitoring

✅ **Multi-threaded Processing**
- Concurrent account checking
- Thread-safe statistics
- Clean output management

✅ **Telegram Bot Integration**
- Real-time command handlers
- Statistics reporting
- Single account checking
- Session management

## File Structure

### supercell_engine.py

**Main Classes:**

1. **SupercellStats** - Thread-safe statistics collection
   ```python
   stats = SupercellStats()
   stats.increment_hit()
   stats.increment_supercell()
   report = stats.get_stats()
   ```

2. **HotmailAuthenticator** - Microsoft authentication
   ```python
   tokens = HotmailAuthenticator.get_tokens(email)
   result = HotmailAuthenticator.login(email, password, tokens)
   token = HotmailAuthenticator.get_access_token(code)
   ```

3. **SupercellScanner** - Game detection
   ```python
   profile = SupercellScanner.get_extended_profile_info(token, cid)
   search_data = SupercellScanner.search_supercell_emails(token, cid, email)
   games = SupercellScanner.analyze_games(search_data)
   ```

4. **SupercellEngine** - Main checking engine
   ```python
   engine = SupercellEngine(results_dir="Supercell_Results")
   result = engine.check_account(email, password)
   stats = engine.get_stats()
   ```

### bot_handlers.py Additions

**SupercellManager** - Bot integration layer
```python
manager = SupercellManager()

# Check if available
if manager.is_available():
    # Start checking session
    manager.start_session(session_id, combo_file)
    
    # Check single account
    result = manager.check_account(email, password)
    
    # Get statistics
    stats = manager.get_session_stats(session_id)
    
    # End session
    session = manager.end_session(session_id)
```

## Usage Examples

### Example 1: Simple Account Check

```python
from supercell_engine import SupercellEngine

engine = SupercellEngine()

# Check a single account
result = engine.check_account("user@hotmail.com", "password123")

if result:
    print(f"Email: {result['email']}")
    print(f"Status: {result['status']}")
    if result['has_supercell']:
        print(f"Games found: {', '.join([g for g in ['Clash Royale', 'Brawl Stars', 'Clash of Clans', 'Hay Day'] if result.get(g.lower().replace(' ', '_'))])}")
        print(f"Total messages: {result['total_messages']}")
```

### Example 2: Statistics Tracking

```python
from supercell_engine import SupercellEngine

engine = SupercellEngine()
combos = [
    ("email1@hotmail.com", "pass1"),
    ("email2@hotmail.com", "pass2"),
    ("email3@hotmail.com", "pass3"),
]

for email, password in combos:
    result = engine.check_account(email, password)
    
# Get final statistics
stats = engine.get_stats()
print(f"Total checked: {stats['total_checked']}")
print(f"Total hits: {stats['total_hits']}")
print(f"Supercell accounts: {stats['supercell_hits']}")
print(f"Games breakdown:")
for game, count in stats['games'].items():
    print(f"  {game}: {count}")
```

### Example 3: Bot Command Integration

```python
from telegram.ext import Application, CommandHandler
from supercell_bot_integration import get_supercell_handlers

# Build bot
app = Application.builder().token("YOUR_TOKEN").build()

# Add Supercell handlers
for handler in get_supercell_handlers():
    app.add_handler(handler)

# Run bot
app.run_polling()
```

Then in Telegram:

```
/supercell_check combo.txt 50          # Check combo file with 50 threads
/supercell_stats                       # Get current statistics
/supercell_check_single email:pass     # Check single account
/supercell_results                     # Get results summary
```

### Example 4: Batch Processing

```python
from supercell_bot_integration import supercell_integration

# Define callback for progress updates
def on_result(result):
    if result['status'] == 'supercell':
        print(f"✅ SUPERCELL HIT: {result['email']}")

# Process entire combo file
results = supercell_integration.process_combo_file(
    combo_file="combo.txt",
    threads=50,
    callback=on_result
)

print(f"Total processed: {results['total_processed']}")
print(f"Supercell hits: {results['statistics']['supercell_hits']}")
```

## Results Output

### File Structure

Results are saved in `Supercell_Results/` directory:

```
Supercell_Results/
├── Supercell_Hits.txt          # All Supercell accounts with full details
├── Valid_Accounts.txt          # Valid accounts without Supercell games
├── Clash_Royale.txt            # Email:Password of Clash Royale accounts
├── Brawl_Stars.txt             # Email:Password of Brawl Stars accounts
├── Clash_of_Clans.txt          # Email:Password of Clash of Clans accounts
└── Hay_Day.txt                 # Email:Password of Hay Day accounts
```

### Statistics Report Format

```
📊 SUPERCELL CHECKING STATISTICS

👥 Total Checked: 1500
✅ Total Hits: 450
🎮 Supercell Accounts: 85
📝 Valid (No Games): 365
❌ Bad Accounts: 1000
⚠️  Errors: 50

🎯 Games Found:
   • Clash Royale: 45
   • Brawl Stars: 38
   • Clash of Clans: 32
   • Hay Day: 28
```

## API Reference

### SupercellEngine

```python
engine = SupercellEngine(results_dir="Supercell_Results")

# Check single account
result = engine.check_account(email, password)
# Returns: Dict with account details and game information

# Get statistics
stats = engine.get_stats()
# Returns: Dict with checking statistics

# Save results
engine.save_result(result)
engine.save_valid_result(result)
```

### SupercellManager (Bot Integration)

```python
manager = SupercellManager()

# Session management
manager.start_session(session_id, combo_file)
manager.end_session(session_id)
manager.get_session_stats(session_id)

# Account checking
manager.check_account(email, password)

# Statistics
manager.get_global_stats()
manager.format_stats_report(stats)
```

## Result Object Format

```python
{
    "email": "user@hotmail.com",
    "password": "password123",
    "status": "supercell",  # or "valid", "valid_no_games", "invalid"
    "country": "USA",
    "name": "John Doe",
    "birthdate": "01-15-1990",
    "total_messages": 450,
    "clash_royale": True,
    "brawl_stars": True,
    "clash_of_clans": False,
    "hay_day": True,
    "last_message": "2024-01-15",
    "has_supercell": True
}
```

## Statistics Object Format

```python
{
    "total_checked": 1500,
    "total_hits": 450,
    "supercell_hits": 85,
    "valid_accounts": 365,
    "bad_accounts": 1000,
    "errors": 50,
    "games": {
        "clash_royale": 45,
        "brawl_stars": 38,
        "clash_of_clans": 32,
        "hay_day": 28
    }
}
```

## Integration Checklist

- ✅ `supercell_engine.py` created with complete functionality
- ✅ `SupercellManager` added to `bot_handlers.py`
- ✅ `supercell_bot_integration.py` created with command handlers
- ✅ Full statistics tracking implemented
- ✅ Thread-safe operations
- ✅ Result file saving
- ✅ Error handling

## Performance Optimization

- **Threading**: Configurable thread count (default: 50)
- **Timeout**: 10 seconds per operation
- **Retry**: Automatic retry on token errors
- **Lock Management**: Thread-safe statistics collection
- **File I/O**: Batch writes to reduce file operations

## Error Handling

All operations include proper exception handling:

- Network timeouts
- Authentication failures
- Invalid credentials
- File access errors
- JSON parsing errors
- Thread errors

## Next Steps

1. **Add to main bot**:
   ```python
   from supercell_bot_integration import get_supercell_handlers
   # Add handlers to your Application
   ```

2. **Configure settings** in your bot config:
   - Results directory
   - Thread count
   - Timeout values
   - Telegram notifications

3. **Test integration**:
   ```bash
   python supercell_engine.py  # Test engine
   # Or add test combo file and run through bot
   ```

4. **Monitor statistics** using bot commands in production

## Troubleshooting

**Engine not available:**
- Check if `supercell_engine.py` is in the same directory
- Verify `user_agent` module is installed

**Statistics not tracking:**
- Ensure `SupercellManager` is initialized before checking
- Check thread safety with `lock` objects

**Results not saving:**
- Verify `Supercell_Results/` directory has write permissions
- Check file path construction

## Version History

- **v1.0** - Initial engine refactoring
- **v1.1** - Added bot integration
- **v1.2** - Full statistics tracking
- **v2.0** - Production-ready with command handlers
