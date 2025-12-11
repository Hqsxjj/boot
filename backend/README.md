# 115 Telegram Bot Admin - Backend API

Production-ready Flask backend for the 115 Telegram Bot Admin application.

## Features

- **App Factory Pattern**: Clean `create_app()` factory for easy testing and configuration
- **JWT Authentication**: Token-based authentication with 24-hour expiry
- **2FA Support**: TOTP-based two-factor authentication with QR code provisioning
- **Rate Limiting**: 5 login attempts per minute, 50 requests per hour globally
- **CORS Support**: Configurable cross-origin resource sharing for SPA
- **Persistence Layer**: JSON-based data store with thread-safe operations
- **Secret Storage**: SQLAlchemy-based encrypted secret storage for sensitive credentials
- **115 Cloud Integration**: QR code login, cookie validation, and session management for 115 cloud
- **Offline Tasks**: Queue and manage offline download tasks with database persistence
- **Task Polling**: Automatic background sync of task status from 115 API
- **Secret Masking**: Automatic masking of sensitive fields in API responses
- **Comprehensive Tests**: Unit tests for all endpoints and data operations

## Project Structure

```
backend/
├── main.py                 # App factory and entry point
├── p115_bridge.py         # 115 cloud service wrapper
├── blueprints/            # API route blueprints
│   ├── auth.py           # Authentication endpoints
│   ├── config.py         # Configuration management with secret masking
│   ├── cloud115.py       # 115 cloud login endpoints
│   ├── offline.py        # Offline task management endpoints
│   └── health.py         # Health check
├── middleware/           # Custom middleware
│   └── auth.py          # JWT authentication decorator
├── models/              # Data models
│   ├── database.py      # SQLAlchemy setup and initialization
│   ├── secret.py        # Secret model for encrypted storage
│   └── offline_task.py  # Offline task model with status tracking
├── persistence/         # Data storage layer
│   └── store.py        # JSON-based data store
├── services/           # Business logic services
│   ├── secret_store.py    # Encrypted secret storage service
│   ├── offline_tasks.py   # Offline task management service
│   └── task_poller.py     # Background task polling service
├── tests/              # Unit tests
│   ├── test_app.py     # Comprehensive test suite
│   ├── test_cloud115.py # 115 cloud integration tests
│   └── test_offline.py  # Offline task tests
└── requirements.txt    # Python dependencies
```

## Installation

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Environment variables:

- `SECRET_KEY`: Flask secret key (default: `dev-secret-key-change-in-production`)
- `JWT_SECRET_KEY`: JWT signing key (default: `jwt-secret-key-change-in-production`)
- `DATA_PATH`: Path to JSON data file (default: `/data/appdata.json`)
- `DATABASE_URL`: SQLAlchemy database URL (default: `sqlite:////data/secrets.db`)
- `SECRETS_ENCRYPTION_KEY`: Encryption key for secret store (default: auto-generated)
- `CORS_ORIGINS`: Comma-separated list of allowed origins (default: `http://localhost:5173,http://localhost:3000`)
- `OFFLINE_TASK_POLL_INTERVAL`: Background poller interval in seconds (default: `60`)
- `PORT`: Server port (default: `5000`)
- `DEBUG`: Enable debug mode (default: `False`)

## Running the Server

### Development

```bash
export DATA_PATH=/tmp/appdata.json
export DEBUG=True
python main.py
```

### Production

```bash
export SECRET_KEY=your-secure-secret-key
export JWT_SECRET_KEY=your-secure-jwt-key
export DATA_PATH=/data/appdata.json
export CORS_ORIGINS=https://yourdomain.com
gunicorn -w 4 -b 0.0.0.0:5000 main:app
```

Or use the app factory:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "main:create_app()"
```

## API Endpoints

### Health Check

**GET** `/api/health`

Returns service health status.

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "service": "115-telegram-bot-admin",
    "version": "1.0.0"
  }
}
```

### Authentication

#### Login

**POST** `/api/auth/login`

Authenticate user and receive JWT token.

```json
// Request
{
  "username": "admin",
  "password": "yourpassword"
}

// Response
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "username": "admin",
    "requires2FA": false
  }
}
```

**Rate Limit**: 5 requests per minute

#### Verify OTP

**POST** `/api/auth/verify-otp`

Verify two-factor authentication code.

```json
// Request (requires Authorization header)
{
  "code": "123456"
}

// Response
{
  "success": true,
  "data": {
    "verified": true
  }
}
```

#### Setup 2FA

**POST** `/api/auth/setup-2fa`

Generate and store a new 2FA secret.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "secret": "JBSWY3DPEHPK3PXP",
    "qrCodeUri": "otpauth://totp/admin?secret=JBSWY3DPEHPK3PXP&issuer=115%20Telegram%20Bot"
  }
}
```

#### Get Current User

**GET** `/api/auth/me` or **GET** `/api/me`

Get current user information.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "username": "admin",
    "twoFactorEnabled": false
  }
}
```

### Configuration

#### Get Configuration

**GET** `/api/config`

Retrieve full application configuration with sensitive fields masked.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "telegram": {
      "botToken": "my-**-token",
      "adminUserId": "",
      "whitelistMode": false,
      "notificationChannelId": ""
    },
    "cloud115": {
      "loginMethod": "cookie",
      "cookies": "****",
      "hasValidSession": false,
      ...
    },
    // ... other config sections
  }
}
```

#### Update Configuration

**PUT** `/api/config`

Update application configuration. Sensitive fields are automatically encrypted and stored separately.

```json
// Request (requires Authorization header)
{
  "telegram": {
    "botToken": "your-actual-token",
    "adminUserId": "12345",
    ...
  },
  // ... other config sections
}

// Response (with masked sensitive values)
{
  "success": true,
  "data": { ... } // Updated configuration with masked secrets
}
```

### 115 Cloud Integration

#### Start QR Code Login

**POST** `/api/115/login/qrcode`

Start a QR code login session for 115 cloud.

```json
// Request (requires Authorization header)
{
  "loginApp": "web",
  "loginMethod": "cookie"
}

// Response
{
  "success": true,
  "data": {
    "sessionId": "uuid-string",
    "qrcode": "base64-encoded-qr-code",
    "loginMethod": "cookie",
    "loginApp": "web"
  }
}
```

#### Poll Login Status

**GET** `/api/115/login/status/<sessionId>`

Poll QR code login status. When successful, cookies are automatically persisted.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "status": "waiting|success",
    "message": "..."
  }
}
```

#### Ingest Manual Cookies

**POST** `/api/115/login/cookie`

Manually ingest and validate 115 cookies.

```json
// Request (requires Authorization header)
{
  "cookies": {
    "UID": "...",
    "CID": "...",
    "SEID": "..."
  },
  "loginApp": "web"
}

// Response
{
  "success": true,
  "data": {
    "message": "Cookies validated and stored successfully"
  }
}
```

#### Get Session Health

**GET** `/api/115/session`

Check 115 session health and validity.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "hasValidSession": true,
    "lastCheck": "2024-01-01T12:00:00.000000",
    "message": "Session check complete"
  }
}
```

### Offline Tasks

Offline tasks allow queuing download jobs to 115 cloud with persistence and background sync.

#### Create Offline Task

**POST** `/api/115/offline/tasks`

Create a new offline download task.

```json
// Request (requires Authorization header)
{
  "sourceUrl": "magnet:?xt=urn:btih:... or https://example.com/file.zip",
  "saveCid": "folder-cid-in-115",
  "requestedBy": "telegram-user-id",
  "requestedChat": "telegram-chat-id"
}

// Response (201 Created)
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "p115TaskId": null,
    "sourceUrl": "magnet:?xt=urn:btih:...",
    "saveCid": "folder-cid",
    "status": "pending",
    "progress": 0,
    "speed": null,
    "requestedBy": "user-id",
    "requestedChat": "chat-id",
    "createdAt": "2024-01-01T12:00:00.000000",
    "updatedAt": "2024-01-01T12:00:00.000000"
  }
}
```

#### List Offline Tasks

**GET** `/api/115/offline/tasks`

List offline tasks with optional filtering and pagination.

Query parameters:
- `status`: Filter by status (pending, downloading, completed, failed, cancelled)
- `requestedBy`: Filter by requesting user
- `limit`: Maximum results (default: 50)
- `offset`: Pagination offset (default: 0)
- `refresh`: Set to `true` to sync with 115 before responding

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "uuid-string",
        "status": "downloading",
        "progress": 45,
        "sourceUrl": "magnet:?xt=urn:btih:...",
        "saveCid": "folder-cid",
        ...
      }
    ],
    "total": 10,
    "limit": 50,
    "offset": 0
  }
}
```

#### Get Single Task

**GET** `/api/115/offline/tasks/<taskId>`

Get details of a single offline task.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "status": "downloading",
    "progress": 45,
    ...
  }
}
```

#### Cancel Task

**PATCH** `/api/115/offline/tasks/<taskId>`

Cancel an offline task.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "status": "cancelled",
    ...
  }
}
```

#### Delete Task

**DELETE** `/api/115/offline/tasks/<taskId>`

Delete an offline task record.

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": { ... }
}
```

#### Retry Failed Task

**POST** `/api/115/offline/tasks/<taskId>/retry`

Retry a failed offline task (resets to pending status).

```json
// Response (requires Authorization header)
{
  "success": true,
  "data": {
    "id": "uuid-string",
    "status": "pending",
    "progress": 0,
    ...
  }
}
```

### Offline Task Polling

The backend includes a background poller that periodically syncs offline task status with the 115 API. This ensures:

- **Status Updates**: Task progress and status are automatically refreshed
- **Completion Detection**: Completed tasks are marked as done
- **Error Handling**: Failed tasks can be retried
- **Configurable Interval**: Set via `OFFLINE_TASK_POLL_INTERVAL` environment variable

The poller is started automatically when the app initializes (unless in TESTING mode) and runs as a daemon thread.

## Authentication

All protected endpoints require a JWT token in the Authorization header:

```
Authorization: Bearer <token>
```

Tokens are valid for 24 hours after issuance.

## Error Responses

All error responses follow this format:

```json
{
  "success": false,
  "error": "Error message description"
}
```

Common status codes:
- `400` - Bad request (missing required fields)
- `401` - Unauthorized (invalid or missing token)
- `404` - Not found
- `500` - Internal server error

## Testing

Run the test suite:

```bash
python -m pytest tests/test_app.py -v
```

Run with coverage:

```bash
python -m pytest tests/test_app.py --cov=. --cov-report=html
```

## Data Storage

The application uses a JSON file for data persistence with the following structure:

```json
{
  "admin": {
    "username": "admin",
    "password_hash": "...",
    "two_factor_secret": "...",
    "two_factor_enabled": false
  },
  "config": {
    // Full AppConfig structure
  }
}
```

The data file is created automatically on first run with default values.

## Security Considerations

1. **Change default secrets**: Always set `SECRET_KEY` and `JWT_SECRET_KEY` in production
2. **Use HTTPS**: Never expose the API over plain HTTP in production
3. **Rate limiting**: Built-in rate limiting protects against brute force attacks
4. **Password hashing**: Passwords are hashed using Werkzeug's secure methods
5. **2FA**: Enable two-factor authentication for enhanced security
6. **CORS**: Configure `CORS_ORIGINS` to only allow trusted domains

## Docker Deployment

The backend is designed to run in a Docker container. See the main project README for Docker deployment instructions.

## Development

To extend the API:

1. Create new blueprints in `blueprints/` directory
2. Register blueprints in `main.py` `create_app()` function
3. Add middleware decorators as needed (`@require_auth`)
4. Write tests in `tests/` directory

## License

See main project LICENSE file.
