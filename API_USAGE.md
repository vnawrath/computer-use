# Computer Control API Usage Guide

This REST API provides computer control capabilities compatible with Anthropic's Computer Use tools schema. The API runs on port 5000 inside the container.

## Security & Authentication

**Important**: All endpoints except `/health` require API key authentication when deployed.

### Authentication
Include your API key in the `X-API-Key` header:
```bash
curl -H "X-API-Key: your-api-key-here" https://your-domain.com/endpoint
```

### Rate Limits
The API implements rate limiting per IP address. Defaults are generous and configurable via environment variables:
- Computer control: 60 requests/minute, 3600/hour (env: `COMPUTER_RATE_PER_MINUTE`, `COMPUTER_RATE_PER_HOUR`)
- Bash commands: 60 requests/minute, 3600/hour (env: `BASH_RATE_PER_MINUTE`, `BASH_RATE_PER_HOUR`)
- Text editor: 60 requests/minute, 3600/hour (env: `TEXT_RATE_PER_MINUTE`, `TEXT_RATE_PER_HOUR`)
- Global defaults: 60 requests/minute, 3600/hour (env: `GLOBAL_RATE_PER_MINUTE`, `GLOBAL_RATE_PER_HOUR`)

Notes:
- Per-endpoint limits override global defaults and include both minute and hour windows.
- Limits are keyed by client IP. If running behind a proxy, real client IPs are respected via `ProxyFix`.

## Available Endpoints

### Health Check
```bash
GET /health
```
Returns the health status of the API. **No authentication required.**

### Computer Control
```bash
POST /computer
```
Handle computer actions like mouse, keyboard, and screenshots. **Requires API key.**

### Bash Commands
```bash
POST /bash
```
Execute bash commands. **Requires API key.** Returns immediate response for short commands (≤30s timeout) or 202 with polling URL for long commands (>30s timeout).

```bash
GET /bash/status/{command_id}
```
Poll the status of an asynchronously running bash command. **Requires API key.**

```bash
GET /bash/commands
```
List all currently running and recently completed bash commands. **Requires API key.**

### Text Editor
```bash
POST /text_editor
```
Basic file operations. **Requires API key.**

## Computer Control Actions

### Take Screenshot
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "screenshot"}'
```

### Mouse Click
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "left_click", "coordinate": [100, 200]}'
```

### Type Text
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "type", "text": "Hello World!"}'
```

### Press Key
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "key", "key": "enter"}'
```

### Key Combination
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "key", "key": "ctrl+c"}'
```

### Mouse Move
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "mouse_move", "coordinate": [500, 300]}'
```

### Scroll
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "scroll", "coordinate": [500, 300], "scroll_direction": "down", "scroll_amount": 3}'
```

### Drag
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "left_click_drag", "start_coordinate": [100, 100], "end_coordinate": [200, 200]}'
```

### Wait
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"action": "wait", "duration": 2.0}'
```

## Bash Commands

Execute bash commands with automatic async handling for long-running operations.

### Basic Command Execution
```bash
curl -X POST http://localhost:5000/bash \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "ls -la"}'
```

### With Working Directory
```bash
curl -X POST http://localhost:5000/bash \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "ls -la", "pwd": "/home/appuser/documents"}'
```

### With Custom Timeout (per-request)
```bash
curl -X POST http://localhost:5000/bash \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "sleep 60 && echo done", "timeout": 120}'
```

### Asynchronous Command Execution

**Important**: Commands with a timeout greater than 30 seconds are automatically executed asynchronously and return a `202 Accepted` response with a polling URL.

#### Long-running Command (Async Response)
```bash
curl -X POST http://localhost:5000/bash \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "npm install", "pwd": "/home/appuser/my-project", "timeout": 900}'
```

**Response (202 Accepted):**
```json
{
  "status": "accepted",
  "message": "Command is running asynchronously",
  "command_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "poll_url": "/bash/status/f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

#### Polling Command Status
```bash
curl -X GET http://localhost:5000/bash/status/f47ac10b-58cc-4372-a567-0e02b2c3d479 \
  -H "X-API-Key: your-api-key-here"
```

**Response (Running):**
```json
{
  "status": "running",
  "command": "npm install",
  "started_at": "2024-01-15T10:30:00.123456",
  "elapsed_seconds": 45.67
}
```

**Response (Completed):**
```json
{
  "status": "completed",
  "stdout": "added 234 packages from 123 contributors...",
  "stderr": "",
  "returncode": 0,
  "completed_at": "2024-01-15T10:32:15.789012"
}
```

**Response (Timeout):**
```json
{
  "status": "timeout",
  "error": "Command timed out after 900 seconds",
  "completed_at": "2024-01-15T10:45:00.123456"
}
```

**Response (Error):**
```json
{
  "status": "error",
  "error": "Working directory not found: /invalid/path",
  "completed_at": "2024-01-15T10:30:01.234567"
}
```

#### List All Commands
```bash
curl -X GET http://localhost:5000/bash/commands \
  -H "X-API-Key: your-api-key-here"
```

**Response:**
```json
{
  "running": {
    "f47ac10b-58cc-4372-a567-0e02b2c3d479": {
      "command": "npm install",
      "started_at": "2024-01-15T10:30:00.123456",
      "elapsed_seconds": 45.67
    }
  },
  "completed": {
    "a1b2c3d4-e5f6-7890-1234-567890abcdef": {
      "status": "completed",
      "completed_at": "2024-01-15T10:25:30.987654"
    }
  }
}
```

### Command Execution Behavior

- **Synchronous (immediate response)**: Commands with timeout ≤ 30 seconds
- **Asynchronous (202 + polling)**: Commands with timeout > 30 seconds
- **Result retention**: Completed command results are kept for 1 hour, then automatically cleaned up
- **Concurrent execution**: Multiple commands can run simultaneously in separate threads

## Text Editor Operations

### View File
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "view", "path": "/home/appuser/example.txt"}'
```

### View File with Working Directory (for relative paths)
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "view", "path": "example.txt", "pwd": "/home/appuser"}'
```

**Successful Response (200 OK):**
```json
{
  "content": "File contents here..."
}
```

**Error Responses:**
- **404 Not Found**: File does not exist
  ```json
  {
    "error": "File not found: /path/to/file.txt"
  }
  ```

- **400 Bad Request**: Path is a directory, not a file
  ```json
  {
    "error": "Path is a directory, not a file: /path/to/directory"
  }
  ```

- **400 Bad Request**: Path is not a regular file (e.g., special device file)
  ```json
  {
    "error": "Path is not a regular file: /path/to/special/file"
  }
  ```

- **400 Bad Request**: File contains binary data or invalid encoding
  ```json
  {
    "error": "File contains binary data or invalid encoding: /path/to/binary/file"
  }
  ```

- **403 Forbidden**: Permission denied
  ```json
  {
    "error": "Permission denied: /path/to/protected/file"
  }
  ```

### Create File
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "create", "path": "/home/appuser/example.txt", "file_text": "Hello World!"}'
```

### Create File with Working Directory
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "create", "path": "example.txt", "pwd": "/home/appuser", "file_text": "Hello World!"}'
```

### Replace Text in File
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "str_replace", "path": "/home/appuser/example.txt", "old_str": "Hello", "new_str": "Hi"}'
```

### Replace Text with Working Directory
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"command": "str_replace", "path": "example.txt", "pwd": "/home/appuser", "old_str": "Hello", "new_str": "Hi"}'
```

## Working Directory (`pwd`) and Timeout Parameters

Both bash commands and text editor operations support optional parameters to control execution:

### Bash Commands
- The `pwd` parameter sets the working directory for command execution
- The `timeout` parameter sets the timeout in seconds for the specific command (overrides the default)
- Equivalent to running `cd /path && command` but cleaner
- If not provided, commands run from `/home/appuser` (the user's home directory)
- If timeout not provided, uses the default timeout (configurable via `BASH_TIMEOUT` environment variable)

### Text Editor Operations  
- The `pwd` parameter is used to resolve relative paths
- **Absolute paths** (starting with `/`) ignore the `pwd` parameter
- **Relative paths** are resolved relative to the `pwd` directory
- If `pwd` is not provided, relative paths are resolved from `/home/appuser` (the user's home directory)

### Examples
```bash
# These are equivalent for bash:
{"command": "cd /tmp && ls -la"}
{"command": "ls -la", "pwd": "/tmp"}

# Long-running command with custom timeout:
{"command": "npm run build", "pwd": "/app", "timeout": 1800}

# These are equivalent for text editor:
{"command": "view", "path": "/home/appuser/file.txt"}
{"command": "view", "path": "file.txt", "pwd": "/home/appuser"}
```

## Anthropic Computer Use Schema Compatibility

This API follows Anthropic's Computer Use tools schema:

- **Computer Tool**: All basic actions (screenshot, click, type, key, move, scroll) and enhanced actions (drag, wait, etc.)
- **Bash Tool**: Command execution with stdout/stderr/returncode
- **Text Editor**: Basic file operations

The response format matches Anthropic's expected schema, making it easy to integrate with Claude's Computer Use capabilities.

## Docker Usage

1. Build the container:
```bash
docker build -t computer-control .
```

2. Run the container:
```bash
docker run -p 6080:6080 -p 5000:5000 computer-control
```

3. Access the desktop at: http://localhost:6080
4. Use the API at: http://localhost:5000

## Security Notes

- This API runs in a containerized environment for safety
- Bash commands have a configurable timeout (default: 30 seconds)
- Commands with timeout > 30 seconds run asynchronously to prevent blocking the API
- Command results are stored in memory for 1 hour, then automatically cleaned up
- Screenshots have a configurable timeout (default: 10 seconds)
- File operations are limited to the container filesystem
- PyAutoGUI failsafe is disabled for containerized operation
- Multiple bash commands can run concurrently in separate threads

## Environment Variables

You can configure the following timeouts using environment variables:

- `BASH_TIMEOUT`: Default timeout for bash commands in seconds (default: 30)
- `SCREENSHOT_TIMEOUT`: Timeout for screenshot operations in seconds (default: 10)

**Note**: Commands with timeout > 30 seconds are automatically executed asynchronously with a 202 response and polling URL.

### Example with Custom Timeouts
```bash
# Set longer default timeout for bash commands (10 minutes)
export BASH_TIMEOUT=600

# Run with custom timeouts
docker compose up -d
```

Or directly in docker-compose.yml:
```yaml
environment:
  - BASH_TIMEOUT=600  # 10 minutes (async commands)
  - SCREENSHOT_TIMEOUT=15  # 15 seconds
```