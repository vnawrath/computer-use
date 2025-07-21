# Computer Control API Usage Guide

This REST API provides computer control capabilities compatible with Anthropic's Computer Use tools schema. The API runs on port 5000 inside the container.

## Available Endpoints

### Health Check
```bash
GET /health
```
Returns the health status of the API.

### Computer Control
```bash
POST /computer
```
Handle computer actions like mouse, keyboard, and screenshots.

### Bash Commands
```bash
POST /bash
```
Execute bash commands.

### Text Editor
```bash
POST /text_editor
```
Basic file operations.

## Computer Control Actions

### Take Screenshot
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "screenshot"}'
```

### Mouse Click
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "left_click", "coordinate": [100, 200]}'
```

### Type Text
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "type", "text": "Hello World!"}'
```

### Press Key
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "key", "key": "enter"}'
```

### Key Combination
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "key", "key": "ctrl+c"}'
```

### Mouse Move
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "mouse_move", "coordinate": [500, 300]}'
```

### Scroll
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "scroll", "coordinate": [500, 300], "scroll_direction": "down", "scroll_amount": 3}'
```

### Drag
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "left_click_drag", "start_coordinate": [100, 100], "end_coordinate": [200, 200]}'
```

### Wait
```bash
curl -X POST http://localhost:5000/computer \
  -H "Content-Type: application/json" \
  -d '{"action": "wait", "duration": 2.0}'
```

## Bash Commands

```bash
curl -X POST http://localhost:5000/bash \
  -H "Content-Type: application/json" \
  -d '{"command": "ls -la"}'
```

### With Working Directory
```bash
curl -X POST http://localhost:5000/bash \
  -H "Content-Type: application/json" \
  -d '{"command": "ls -la", "pwd": "/home/appuser/documents"}'
```

## Text Editor Operations

### View File
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -d '{"command": "view", "path": "/home/appuser/example.txt"}'
```

### View File with Working Directory (for relative paths)
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -d '{"command": "view", "path": "example.txt", "pwd": "/home/appuser"}'
```

### Create File
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -d '{"command": "create", "path": "/home/appuser/example.txt", "file_text": "Hello World!"}'
```

### Create File with Working Directory
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -d '{"command": "create", "path": "example.txt", "pwd": "/home/appuser", "file_text": "Hello World!"}'
```

### Replace Text in File
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -d '{"command": "str_replace", "path": "/home/appuser/example.txt", "old_str": "Hello", "new_str": "Hi"}'
```

### Replace Text with Working Directory
```bash
curl -X POST http://localhost:5000/text_editor \
  -H "Content-Type: application/json" \
  -d '{"command": "str_replace", "path": "example.txt", "pwd": "/home/appuser", "old_str": "Hello", "new_str": "Hi"}'
```

## Working Directory (`pwd`) Parameter

Both bash commands and text editor operations support an optional `pwd` parameter to control the working directory:

### Bash Commands
- The `pwd` parameter sets the working directory for command execution
- Equivalent to running `cd /path && command` but cleaner
- If not provided, commands run from `/home/appuser` (the user's home directory)

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
- Bash commands have a 30-second timeout
- File operations are limited to the container filesystem
- PyAutoGUI failsafe is disabled for containerized operation 