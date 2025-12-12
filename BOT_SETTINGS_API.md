# Bot Settings API Implementation

This implementation provides a complete bot settings API for the Telegram bot integration with the following features:

## Architecture

### Files Created/Modified

1. **`backend/services/telegram_bot.py`** - Core service for bot operations
2. **`backend/blueprints/bot.py`** - REST API endpoints 
3. **`backend/main.py`** - Updated to register bot blueprint
4. **`backend/tests/test_bot.py`** - Comprehensive test suite

## Service Layer (`telegram_bot.py`)

The `TelegramBotService` class provides:

- **Bot Token Validation**: Validates tokens via Telegram's `getMe` API
- **Secure Credential Storage**: Saves bot token and admin ID via `SecretStore`
- **Test Message Sending**: Sends verification messages to admin/channel
- **Command Management**: Handles default and custom bot commands
- **Error Handling**: Comprehensive error handling with timeout support

## API Endpoints (`bot.py`)

### GET `/api/bot/config`
- **Auth**: Optional (respects `ALLOW_UNAUTHENTICATED_CONFIG`)
- **Returns**: Telegram config with real values from secret store
- **Response**: `{ success: true, data: { botToken, adminUserId, notificationChannelId, whitelistMode, hasValidConfig } }`

### POST `/api/bot/config`  
- **Auth**: Required
- **Body**: Bot configuration fields
- **Validates**: Bot token via Telegram API before saving
- **Storage**: Bot token & admin ID → SecretStore, other config → YAML

### GET `/api/bot/commands`
- **Auth**: Optional 
- **Returns**: List of bot commands with `cmd`, `desc`, `example`
- **Fallback**: Returns defaults if no custom commands saved

### PUT `/api/bot/commands`
- **Auth**: Required
- **Body**: `{ commands: [{ cmd, desc, example }, ...] }`
- **Validates**: Command format before saving to SecretStore

### POST `/api/bot/test-message`
- **Auth**: Required
- **Body**: `{ target_type: 'admin'|'channel', target_id?: string }`
- **Function**: Sends test message via Telegram API
- **Returns**: Message delivery confirmation

## Security Features

1. **Encrypted Storage**: All sensitive data (bot tokens, admin IDs) stored via `SecretStore`
2. **Token Validation**: Bot tokens validated against Telegram API before acceptance  
3. **Authentication**: Write operations require JWT authentication
4. **Optional Auth**: Read operations support unauthenticated access in dev mode
5. **Error Handling**: Detailed error responses without exposing internals

## Integration Points

- **SecretStore**: For encrypted credential storage
- **ConfigStore**: For non-sensitive configuration
- **Telegram API**: For token validation and test messaging
- **Existing Auth**: Reuses current JWT-based authentication

## Test Coverage

Comprehensive test suite covering:

- **API Endpoints**: All 5 endpoints with success/error scenarios
- **Authentication**: Both authenticated and unauthenticated access
- **Token Validation**: Success, failure, and timeout cases
- **Message Sending**: Admin and channel test messages
- **Command Management**: CRUD operations for bot commands
- **Error Handling**: Invalid inputs and missing credentials

## Default Bot Commands

The API provides these default commands matching the UI:

```
/start - Initialize bot and check 115 account connection
/magnet - Add magnet/Ed2k/HTTP offline tasks (115)
/123_offline - Add 123 cloud offline download tasks  
/link - Transfer 115 share links (supports encryption)
/rename - Manual file/folder renaming using TMDB
/organize - Auto-categorize 115 default directory
/123_organize - Auto-categorize 123 cloud directory  
/dir - Set or view current default download folder (CID)
/quota - View 115 account offline quota and space usage
/tasks - View current ongoing offline task list
```

## Usage Examples

### Get Bot Configuration
```bash
curl http://localhost:5000/api/bot/config
```

### Update Bot Configuration  
```bash
curl -X POST http://localhost:5000/api/bot/config \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "botToken": "123456:ABC-DEF",
    "adminUserId": "123456789", 
    "notificationChannelId": "-100123456789",
    "whitelistMode": true
  }'
```

### Send Test Message
```bash
curl -X POST http://localhost:5000/api/bot/test-message \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"target_type": "admin"}'
```

### Update Bot Commands
```bash
curl -X PUT http://localhost:5000/api/bot/commands \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "commands": [
      {"cmd": "/custom", "desc": "Custom command", "example": "/custom arg"}
    ]
  }'
```

## Environment Variables

- `ALLOW_UNAUTHENTICATED_CONFIG=true` - Enable unauthenticated read access (dev mode)
- `SECRETS_ENCRYPTION_KEY` - Encryption key for credential storage

## Notes

- Bot token validation prevents saving invalid credentials
- Test messages require both valid token and target configuration  
- Commands are stored encrypted and can be customized per deployment
- All API responses follow consistent `{ success, data|error }` format
- Frontend integration requires no changes - same response format as existing config endpoints