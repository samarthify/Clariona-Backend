# Configuring Target Individual

This document explains how to configure which individual (political figure, celebrity, etc.) the system should monitor.

## Quick Start

Edit `config/.env` and set these two variables:

```bash
TARGET_INDIVIDUAL="Bola Ahmed Tinubu"
QUERY_VARIATIONS=["Bola Tinubu", "President Tinubu", "Tinubu", "Nigeria", "Asiwaju"]
```

That's it! All collectors will now use these queries.

## Configuration Variables

### `TARGET_INDIVIDUAL`
The primary name of the person to monitor. This becomes the first query in the list.

**Example:**
```bash
TARGET_INDIVIDUAL="Bola Ahmed Tinubu"
```

### `QUERY_VARIATIONS`
A JSON array of additional search terms, variations of the name, related keywords, etc.

**Format:** Must be valid JSON array (use double quotes, not single quotes)

**Example:**
```bash
QUERY_VARIATIONS=["Bola Tinubu", "President Tinubu", "Tinubu", "Nigeria President", "Nigerian President", "Nigeria", "Asiwaju"]
```

## Examples for Different Targets

### Nigerian President (Tinubu)
```bash
TARGET_INDIVIDUAL="Bola Ahmed Tinubu"
QUERY_VARIATIONS=["Bola Tinubu", "President Tinubu", "Tinubu", "Nigeria President", "Nigerian President", "Nigeria", "Asiwaju"]
```

### Qatar Emir
```bash
TARGET_INDIVIDUAL="Sheikh Tamim bin Hamad Al Thani"
QUERY_VARIATIONS=["Sheikh Tamim", "Emir of Qatar", "Qatar Emir", "Tamim Al Thani", "Qatar", "Doha", "Gulf Cooperation Council"]
```

### Indian Prime Minister (Modi)
```bash
TARGET_INDIVIDUAL="Narendra Modi"
QUERY_VARIATIONS=["Modi", "PM Modi", "India", "BJP", "Prime Minister Modi", "Indian PM", "Bharatiya Janata Party"]
```

### US President
```bash
TARGET_INDIVIDUAL="Joe Biden"
QUERY_VARIATIONS=["Biden", "President Biden", "POTUS", "US President", "White House", "United States"]
```

## How It Works

The system uses these queries in the following priority order:

### 1. Command-line Arguments (Highest Priority)
When collectors are run with explicit `--queries` parameter, those queries are used.

### 2. ConfigManager/Database Settings
Target-specific or default keywords stored in the configuration system or database.

### 3. Environment Variables (`.env` file)
The `TARGET_INDIVIDUAL` and `QUERY_VARIATIONS` from your `.env` file.

### 4. Hardcoded Fallbacks (Last Resort)
If nothing else is configured, uses hardcoded Tinubu queries.

## Which Collectors Use These Settings?

These environment variables are used by:
- ✅ **News API Collector** (`collect_news_from_api.py`)
- ✅ **RSS Collector** (`collect_rss_nigerian_qatar_indian.py`)
- ✅ **Scheduler** (when running collectors automatically)
- ✅ **Radio GNews Collector** (test mode)

Other collectors like YouTube, Twitter/X, etc. use their own configuration methods.

## Tips for Good Query Variations

1. **Include full name and common variations**
   - "Bola Ahmed Tinubu", "Bola Tinubu", "Tinubu"

2. **Include titles and positions**
   - "President Tinubu", "Nigeria President"

3. **Include nicknames or traditional names**
   - "Asiwaju", "Jagaban"

4. **Include related geographic terms**
   - "Nigeria", "Lagos", "Federal Capital Territory"

5. **Keep queries specific enough to avoid noise**
   - Too broad: "President" (matches many presidents)
   - Good: "President Tinubu" (specific to your target)

## Troubleshooting

### My queries aren't being used
1. Check that `.env` file exists in `config/` folder
2. Verify JSON syntax is valid (use double quotes)
3. Check logs for "Using keywords from environment variables"
4. Restart any running services after changing `.env`

### Getting irrelevant results
- Make queries more specific
- Add the target's full name
- Remove overly generic terms like "news" or "politics"

### Not getting enough results
- Add more variations of the name
- Include related keywords (location, party, title)
- Check that NEWS API keys are configured

## Related Files

- **Configuration**: `config/.env`
- **Scheduler**: `src/services/scheduler.py`
- **News API Collector**: `src/collectors/collect_news_from_api.py`
- **Example Config**: `config/.env.example`
