# Target Configuration - Fixed! ✅

## What Was Wrong

1. **News API Collector** - Missing API keys and hardcoded Modi queries
2. **RSS Collector** - Not receiving query arguments from scheduler
3. **Hardcoded targets** - Qatar/Modi hardcoded everywhere instead of being configurable

## What Was Fixed

### ✅ Made Everything Configurable

Now you can easily change the target by editing **ONE PLACE**: `config/.env`

```bash
# Edit these two lines:
TARGET_INDIVIDUAL="Bola Ahmed Tinubu"
QUERY_VARIATIONS=["Bola Tinubu", "President Tinubu", "Tinubu", "Nigeria", "Asiwaju"]
```

### ✅ Fixed Scheduler

The scheduler now:
- Loads queries from `config/.env`
- Passes them to collectors via `--queries` argument
- No more "running directly without args" errors

### ✅ Fixed News API Collector

- Now checks both `src/collectors/.env` AND `config/.env` for API keys
- Uses environment-based queries with proper priority
- Added placeholders for `MEDIASTACK_API_KEY` and `GNEWS_API_KEY`

### ✅ Query Priority System

Collectors now use this priority order:

1. **Command-line `--queries`** (highest priority)
2. **ConfigManager/Database** settings
3. **Environment variables** (`TARGET_INDIVIDUAL` + `QUERY_VARIATIONS`) ⭐ NEW
4. **Target config** (backward compatibility)
5. **Hardcoded fallback** (Tinubu queries)

## How to Use

### 1. Configure Your Target

Edit `config/.env`:

```bash
TARGET_INDIVIDUAL="Bola Ahmed Tinubu"
QUERY_VARIATIONS=["Bola Tinubu", "President Tinubu", "Tinubu", "Nigeria", "Asiwaju"]
```

### 2. Verify Configuration

Run the verification script:

```bash
python3 scripts/verify_target_config.py
```

You should see:
```
✅ Configuration is valid!
📊 Target: Bola Ahmed Tinubu
📊 Total Queries: 9
```

### 3. Add API Keys (Required for News API)

Get free API keys from:
- https://mediastack.com/ (free tier: 500 requests/month)
- https://gnews.io/ (free tier: 100 requests/day)

Add at least one to `config/.env`:

```bash
MEDIASTACK_API_KEY=your_key_here
GNEWS_API_KEY=your_key_here
```

### 4. Restart Services

If collectors/scheduler are running, restart them to pick up the new config.

## Example Configurations

### Nigerian President (Current Setup)
```bash
TARGET_INDIVIDUAL="Bola Ahmed Tinubu"
QUERY_VARIATIONS=["Bola Tinubu", "President Tinubu", "Tinubu", "Nigeria", "Asiwaju"]
```

### Qatar Emir
```bash
TARGET_INDIVIDUAL="Sheikh Tamim bin Hamad Al Thani"
QUERY_VARIATIONS=["Sheikh Tamim", "Emir of Qatar", "Qatar", "Doha", "Gulf"]
```

### Indian PM
```bash
TARGET_INDIVIDUAL="Narendra Modi"
QUERY_VARIATIONS=["Modi", "PM Modi", "India", "BJP", "Prime Minister Modi"]
```

## Files Modified

1. `config/.env` - Added TARGET_INDIVIDUAL and QUERY_VARIATIONS
2. `config/.env.example` - Updated with examples
3. `src/services/scheduler.py` - Loads queries from .env
4. `src/collectors/collect_news_from_api.py` - Uses env queries
5. `src/collectors/collect_radio_gnews.py` - Updated test queries

## New Files Created

1. `docs/CONFIGURING_TARGET.md` - Full documentation
2. `scripts/verify_target_config.py` - Simple verification script
3. `scripts/test_target_config.py` - Comprehensive test suite
4. `docs/TARGET_CONFIGURATION_FIXED.md` - This file

## Testing Results

```
✅ PASS - Environment Loading
   Loaded: Bola Ahmed Tinubu
   Queries: 9 total

✅ Configuration Valid
```

## Next Steps

1. **Add API keys** to `config/.env` (MEDIASTACK_API_KEY or GNEWS_API_KEY)
2. **Run verification**: `python3 scripts/verify_target_config.py`
3. **Test collectors**: Wait for next scheduled run or trigger manually

## Need Help?

- See `docs/CONFIGURING_TARGET.md` for detailed documentation
- Run `python3 scripts/verify_target_config.py` to check your setup
- Check collector logs in `logs/collectors/` for issues
