# Config API Parity - Implementation Documentation

## Summary

This document describes the implementation of YAML-backed configuration storage with full API parity between the frontend and backend.

## Changes Made

### 1. YAML-Backed Config Persistence Layer

**File:** `persistence/config_store.py`

- Created a new `ConfigStore` class that reads/writes configuration to `/data/config.yml`
- Uses PyYAML for serialization (added `pyyaml==6.0.1` to requirements.txt)
- Matches the `AppConfig` schema from the frontend (`types.ts`)
- Automatically migrates existing configuration from `appdata.json` to YAML on first startup
- Admin credentials and 2FA secrets remain in JSON for security separation

**Key Features:**
- Thread-safe operations with locks
- Deep merge of default config with user config for backwards compatibility
- Handles missing directories gracefully
- Automatic fallback to temp directory if `/data` is not accessible (useful for tests)

### 2. Updated DataStore Integration

**File:** `persistence/store.py`

- Integrated `ConfigStore` into the existing `DataStore` class
- `get_config()` now retrieves configuration from YAML
- `update_config()` now writes configuration to YAML
- Admin credential management remains in JSON (`appdata.json`)
- 2FA secrets are managed separately in JSON and merged into config only when needed

### 3. Removed Masking Logic

**File:** `blueprints/config.py`

- **REMOVED:** All masking functions (`_mask_sensitive_value`, `_apply_masked_config`, `_extract_sensitive_fields`)
- **REMOVED:** Secret store integration for config fields
- Config is now returned exactly as stored - no masking
- Supports both `PUT` and `POST` methods for `/api/config`
- Returns consistent response format: `{'success': true, 'data': <AppConfig>}`
- All sensitive fields now round-trip through the API without modification

### 4. Optional Authentication

**File:** `middleware/auth.py`

- Added new `optional_auth` decorator
- Supports `ALLOW_UNAUTHENTICATED_CONFIG` environment variable for dev mode
- When set to `'true'`, allows `/api/config` endpoints to work without JWT token
- Default is `'false'` (requires authentication)
- Useful for development and testing while keeping production secure

### 5. Comprehensive Tests

**File:** `tests/test_config_store.py`

Added 15 new tests covering:

1. **ConfigStore Tests:**
   - YAML file creation with defaults
   - Config round-trip (save and load)
   - Sensitive fields NOT masked
   - Complex nested structures (movieRules, tvRules)
   - Migration from JSON to YAML

2. **DataStore Integration Tests:**
   - Config retrieval from YAML
   - 2FA secret stays in JSON, not YAML
   - Config includes 2FA secret when enabled

3. **API Endpoint Tests:**
   - GET returns unmasked data
   - PUT works correctly
   - POST works correctly (frontend compatibility)
   - Response shape matches frontend expectations
   - Config keys match frontend schema
   - Dev mode allows unauthenticated access
   - All sensitive fields round-trip without masking

### 6. Updated Existing Tests

**File:** `tests/test_app.py`

- Updated tests to work with new YAML-backed storage
- Removed expectations of masking
- Added database path configuration for test isolation

## Configuration Files

### New File Structure

```
/data/
├── config.yml          # Application configuration (YAML)
├── appdata.json        # Admin credentials and 2FA secrets (JSON)
└── secrets.db          # Encrypted secrets (SQLite)
```

### Example config.yml

```yaml
telegram:
  botToken: '1234567890:ABCdefGHI...'
  adminUserId: '12345678'
  whitelistMode: true
  notificationChannelId: ''

cloud115:
  loginMethod: cookie
  loginApp: web
  cookies: 'UID=123456_A1B2C3; CID=ABCD1234; SEID=xyz789'
  appId: ''
  userAgent: 'Mozilla/5.0...'
  downloadPath: '0'
  downloadDirName: '根目录'
  autoDeleteMsg: true
  qps: 0.8

organize:
  enabled: true
  sourceCid: '0'
  sourceDirName: '根目录'
  targetCid: '0'
  targetDirName: '根目录'
  ai:
    enabled: false
    provider: openai
    baseUrl: 'https://api.openai.com/v1'
    apiKey: 'sk-...'
    model: gpt-3.5-turbo
  rename:
    enabled: true
    movieTemplate: '{title} ({year})'
    seriesTemplate: '{title} - S{season}E{episode}'
    addTmdbIdToFolder: true
  movieRules:
    - id: m_anim
      name: '动画电影'
      targetCid: '123'
      conditions:
        genre_ids: '16'
  tvRules:
    - id: t_cn
      name: '华语剧集'
      targetCid: '456'
      conditions:
        origin_country: 'CN,TW,HK'
```

## API Changes

### GET /api/config

**Before:**
- Returned config with masked sensitive fields (e.g., `'to***23'`)
- Required JWT authentication

**After:**
- Returns full unmasked config
- Requires JWT authentication (unless `ALLOW_UNAUTHENTICATED_CONFIG=true`)
- Response format unchanged: `{'success': true, 'data': <AppConfig>}`

### PUT /api/config

**Before:**
- Only supported PUT method
- Required JWT authentication
- Accepted full config but masked values in response

**After:**
- Supports both PUT and POST methods
- Requires JWT authentication (unless `ALLOW_UNAUTHENTICATED_CONFIG=true`)
- Full round-trip - exact values returned as sent
- Response format: `{'success': true, 'data': <AppConfig>}`

### POST /api/config

**New endpoint** (same handler as PUT):
- Supports frontend's existing `saveConfig` implementation
- Identical behavior to PUT method

## Environment Variables

### New Variables

- `CONFIG_YAML_PATH`: Path to YAML config file (default: `/data/config.yml`)
- `ALLOW_UNAUTHENTICATED_CONFIG`: Allow config access without JWT (default: `false`)

### Existing Variables

- `DATA_PATH`: Path to JSON data file for admin credentials (default: `/data/appdata.json`)
- `DATABASE_URL`: Database URL for secrets storage
- `DATA_DIR`: Data directory (default: `/data`)

## Migration Guide

### Automatic Migration

On first startup with the new code:
1. If `/data/config.yml` doesn't exist but `/data/appdata.json` exists
2. The config section from JSON is automatically migrated to YAML
3. Admin credentials remain in JSON
4. Original JSON file is preserved

### Manual Migration

If you need to manually migrate:

```bash
# Backup existing data
cp /data/appdata.json /data/appdata.json.backup

# Start the application - migration happens automatically
# Check logs for: "Migrated config from /data/appdata.json to /data/config.yml"
```

## Development Mode

For local development without authentication:

```bash
export ALLOW_UNAUTHENTICATED_CONFIG=true
python main.py
```

**Warning:** Never use this in production!

## Testing

Run all tests:

```bash
cd backend
python3 -m unittest tests.test_config_store -v
python3 -m unittest tests.test_app -v
```

Run specific test suites:

```bash
# YAML store tests
python3 -m unittest tests.test_config_store.TestConfigStore -v

# API endpoint tests
python3 -m unittest tests.test_config_store.TestConfigAPIEndpoints -v

# DataStore integration tests
python3 -m unittest tests.test_config_store.TestDataStoreWithConfigStore -v
```

## Breaking Changes

### For Backend

1. **No more masking**: Sensitive fields are no longer masked in API responses
2. **YAML storage**: Configuration is now stored in YAML instead of JSON
3. **New dependency**: Requires `pyyaml==6.0.1`

### For Frontend

None! The API remains fully compatible:
- `POST /api/config` still works
- Response format unchanged: `{'success': true, 'data': <AppConfig>}`
- All config keys match frontend schema

## Security Considerations

1. **Sensitive data in YAML**: All sensitive fields (API keys, tokens, passwords) are now stored in plaintext YAML
2. **File permissions**: Ensure `/data/config.yml` has appropriate permissions (e.g., `600`)
3. **Backup strategy**: Back up both `config.yml` and `appdata.json`
4. **Dev mode**: Never enable `ALLOW_UNAUTHENTICATED_CONFIG` in production

## Future Improvements

Potential enhancements (not implemented):
- Encrypt sensitive fields in YAML using a master key
- Add config versioning/history
- Support for multiple config profiles
- Config validation against JSON schema
- Hot-reload on config changes
