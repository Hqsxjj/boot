# Cloud115 Service Implementation

## Overview

This document describes the implementation of the Cloud115 service that wraps `p115client` for comprehensive 115 cloud operations, including directory browsing, file management, and offline task orchestration.

## Components Added

### 1. `services/cloud115_service.py`

A dedicated service class that encapsulates all 115 cloud operations:

#### Key Features:
- **Authentication**: Uses cookies from `SecretStore` (`cloud115_cookies` key)
- **Graceful Degradation**: Works even when p115client is not installed (logs warnings)
- **Session Metadata**: Tracks login method (cookie/manual/qr) for health reporting

#### Methods:

**Directory Operations:**
- `list_directory(cid)` - Returns directory listing in format compatible with frontend FileSelector:
  ```json
  {
    "success": true,
    "data": [
      {
        "id": "101",
        "name": "电影 (Movies)",
        "children": true,
        "date": "2023-10-25"
      }
    ]
  }
  ```

**File Operations:**
- `rename_file(file_id, new_name)` - Renames files/folders
- `move_file(file_id, target_cid)` - Moves files/folders to another directory
- `delete_file(file_id)` - Deletes files/folders
- `get_download_link(file_id)` - Generates direct download URLs

**Offline Task Operations:**
- `create_offline_task(source_url, save_cid)` - Creates offline download task on 115, returns p115 task ID
- `get_offline_task_status(task_id)` - Fetches real-time status from 115 API with:
  - Status mapping (downloading/completed/failed/pending)
  - Progress (0-100)
  - Download speed (bytes/sec)

**Session Management:**
- `get_session_metadata()` - Returns login method and session info

### 2. Expanded `blueprints/cloud115.py`

Added new REST endpoints for the CloudOrganize UI:

#### New Endpoints:

**`GET /api/115/directories?cid=<cid>`**
- Lists directory contents for FileSelector component
- Returns array of `{id, name, children, date}` entries
- Requires authentication

**`POST /api/115/files/rename`**
- Request: `{"fileId": "...", "newName": "..."}`
- Renames file/folder on 115 cloud
- Returns updated file info

**`POST /api/115/files/move`**
- Request: `{"fileId": "...", "targetCid": "..."}`
- Moves file/folder to target directory
- Returns operation status

**`DELETE /api/115/files`**
- Request: `{"fileId": "..."}`
- Deletes file/folder from 115 cloud
- Returns deletion confirmation

**`POST /api/115/files/offline`**
- Request: `{"sourceUrl": "...", "saveCid": "..."}`
- Alias for offline task creation
- Creates task on 115 and stores in local database
- Returns task with p115_task_id populated

### 3. Updated `services/offline_tasks.py`

Enhanced `sync_all()` method to perform real synchronization:

#### Changes:
- Now queries 115 API for each task with `p115_task_id`
- Updates local database with real-time status, progress, and speed
- Maps 115 status codes to internal `TaskStatus` enum
- Maintains camelCase API responses for frontend compatibility
- Only syncs tasks that have `p115_task_id` set (skips local-only tasks)

#### Status Mapping:
```python
'1' -> 'downloading'
'2' -> 'completed'
'-1' -> 'failed'
'seeding' -> 'completed'
'paused' -> 'pending'
```

### 4. Updated `main.py`

Integrated Cloud115Service into application factory:

```python
# Initialize cloud115 service
cloud115_service = Cloud115Service(secret_store)

# Pass to offline task service for sync operations
offline_task_service = OfflineTaskService(
    session_factory, 
    store, 
    None, 
    cloud115_service
)

# Store in app context
app.cloud115_service = cloud115_service
```

Added helper functions:
- `get_offline_task_service()` - Access service from Flask context
- `get_app()` - Access current app from context

## Testing

### `tests/test_cloud115_service.py`

Comprehensive test coverage with 17 test cases across 3 test classes:

#### TestCloud115Service
- Tests service methods in isolation
- Mocks p115client with proper attribute structures
- Validates data transformations and error handling

#### TestCloud115Endpoints
- Tests HTTP endpoints with full Flask app context
- Validates authentication requirements
- Tests parameter validation and error responses
- Mocks p115client at the service level

#### TestOfflineTaskSync
- Tests sync_all integration with Cloud115Service
- Validates status updates from 115 API
- Ensures camelCase response format

**All 91 tests pass successfully**

## API Response Format

All endpoints maintain consistent JSON envelope:

```json
{
  "success": true,
  "data": { ... }
}
```

Or on error:

```json
{
  "success": false,
  "error": "Error message"
}
```

## Frontend Integration

### FileSelector Component
The `/api/115/directories` endpoint returns data in the exact format expected by `components/FileSelector.tsx`:

```typescript
interface DirectoryEntry {
  id: string;        // File/folder CID
  name: string;      // Display name
  children: boolean; // Is directory?
  date: string;      // Modified date (YYYY-MM-DD)
}
```

### CloudOrganize View
The UI can now call real 115 operations instead of mocks:
- Browse 115 directory structure
- Rename files for organization
- Move files between folders
- Delete unwanted files
- Create offline download tasks that sync with 115

## Backward Compatibility

- Existing `/api/115/offline/tasks` endpoint unchanged
- New `/api/115/files/offline` acts as alias
- Tasks created via either endpoint are stored identically
- sync_all() gracefully handles tasks without p115_task_id
- All existing tests continue to pass

## Error Handling

- Gracefully handles missing p115client (logs warnings)
- Returns structured error responses for missing cookies
- Validates all required parameters
- Handles 115 API errors without crashing
- Uses try-except blocks for robust error catching

## Performance Considerations

- QPS throttling respected from config (`cloud115.qps`)
- Only syncs tasks with p115_task_id (avoids unnecessary API calls)
- Efficient attribute access with fallbacks for p115client variations
- Session reuse via authenticated client caching

## Security

- All endpoints require JWT authentication (`@require_auth`)
- Cookies stored encrypted in SecretStore
- No credentials in logs (uses logger.warning for errors)
- Session metadata separate from cookies

## Next Steps

This implementation provides the foundation for:
1. Real-time offline task monitoring
2. Advanced file organization workflows
3. Batch operations (rename/move multiple files)
4. Download link caching for performance
5. Task retry with actual 115 API calls
