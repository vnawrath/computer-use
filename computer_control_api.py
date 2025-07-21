from flask import Flask, request, jsonify
import subprocess
import base64
import io
import json
import os
import time
from PIL import Image

# Set display environment variable for containerized X11
os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/appuser/.Xauthority"

# Import pyautogui after setting environment variables
try:
    import pyautogui

    PYAUTOGUI_AVAILABLE = True
except Exception as e:
    print(f"Warning: PyAutoGUI not available: {e}")
    PYAUTOGUI_AVAILABLE = False

app = Flask(__name__)

# Configure pyautogui
pyautogui.FAILSAFE = False  # Disable failsafe for containerized environment
pyautogui.PAUSE = 0.1  # Small delay between actions


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "Computer Control API is running"})


@app.route("/computer", methods=["POST"])
def computer_action():
    """Handle computer use tool actions following Anthropic's schema"""
    try:
        data = request.json
        action = data.get("action")

        if not action:
            return jsonify({"error": "Missing 'action' parameter"}), 400

        if action == "screenshot":
            return handle_screenshot()
        elif action == "left_click":
            coordinate = data.get("coordinate", [])
            if len(coordinate) != 2:
                return jsonify({"error": "coordinate must be [x, y]"}), 400
            return handle_left_click(coordinate[0], coordinate[1])
        elif action == "right_click":
            coordinate = data.get("coordinate", [])
            if len(coordinate) != 2:
                return jsonify({"error": "coordinate must be [x, y]"}), 400
            return handle_right_click(coordinate[0], coordinate[1])
        elif action == "double_click":
            coordinate = data.get("coordinate", [])
            if len(coordinate) != 2:
                return jsonify({"error": "coordinate must be [x, y]"}), 400
            return handle_double_click(coordinate[0], coordinate[1])
        elif action == "type":
            text = data.get("text", "")
            return handle_type(text)
        elif action == "key":
            key = data.get("key", "")
            return handle_key(key)
        elif action == "mouse_move":
            coordinate = data.get("coordinate", [])
            if len(coordinate) != 2:
                return jsonify({"error": "coordinate must be [x, y]"}), 400
            return handle_mouse_move(coordinate[0], coordinate[1])
        elif action == "scroll":
            coordinate = data.get("coordinate", [])
            scroll_direction = data.get("scroll_direction", "down")
            scroll_amount = data.get("scroll_amount", 3)
            if len(coordinate) != 2:
                return jsonify({"error": "coordinate must be [x, y]"}), 400
            return handle_scroll(
                coordinate[0], coordinate[1], scroll_direction, scroll_amount
            )
        elif action == "left_click_drag":
            start_coordinate = data.get("start_coordinate", [])
            end_coordinate = data.get("end_coordinate", [])
            if len(start_coordinate) != 2 or len(end_coordinate) != 2:
                return (
                    jsonify(
                        {"error": "start_coordinate and end_coordinate must be [x, y]"}
                    ),
                    400,
                )
            return handle_drag(
                start_coordinate[0],
                start_coordinate[1],
                end_coordinate[0],
                end_coordinate[1],
            )
        elif action == "wait":
            duration = data.get("duration", 1.0)
            return handle_wait(duration)
        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/bash", methods=["POST"])
def bash_command():
    """Handle bash tool commands following Anthropic's schema"""
    try:
        data = request.json
        command = data.get("command", "")
        pwd = data.get("pwd", "/home/appuser")  # Default to appuser home directory

        if not command:
            return jsonify({"error": "Missing 'command' parameter"}), 400

        # Execute command safely
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=pwd,  # Use provided working directory
        )

        return jsonify(
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        )

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timed out"}), 408
    except FileNotFoundError as e:
        return jsonify({"error": f"Working directory not found: {pwd}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/text_editor", methods=["POST"])
def text_editor():
    """Handle basic text editor operations"""
    try:
        data = request.json
        command = data.get("command", "")
        path = data.get("path", "")
        pwd = data.get("pwd", "/home/appuser")  # Default to appuser home directory

        if command == "view":
            return handle_view_file(path, pwd)
        elif command == "create":
            file_text = data.get("file_text", "")
            return handle_create_file(path, file_text, pwd)
        elif command == "str_replace":
            old_str = data.get("old_str", "")
            new_str = data.get("new_str", "")
            return handle_str_replace(path, old_str, new_str, pwd)
        else:
            return jsonify({"error": f"Unknown text editor command: {command}"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Computer action handlers
def handle_screenshot():
    """Take a screenshot and return as base64"""
    # Use scrot command for better container compatibility
    try:
        result = subprocess.run(
            ["scrot", "-o", "/tmp/screenshot.png"], capture_output=True, timeout=10
        )
        if result.returncode == 0:
            with open("/tmp/screenshot.png", "rb") as f:
                img_data = f.read()
            img_base64 = base64.b64encode(img_data).decode()
            # Get image dimensions using PIL
            with Image.open("/tmp/screenshot.png") as img:
                width, height = img.size
            os.remove("/tmp/screenshot.png")
            return jsonify(
                {
                    "type": "image",
                    "format": "png",
                    "data": img_base64,
                    "width": width,
                    "height": height,
                }
            )
        else:
            return (
                jsonify(
                    {"error": f"Screenshot command failed: {result.stderr.decode()}"}
                ),
                500,
            )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Screenshot command timed out"}), 500
    except Exception as e:
        return jsonify({"error": f"Screenshot failed: {str(e)}"}), 500


def handle_left_click(x, y):
    """Perform left click at coordinates"""
    if not PYAUTOGUI_AVAILABLE:
        return jsonify({"error": "PyAutoGUI not available for mouse control"}), 500
    try:
        pyautogui.click(x, y)
        return jsonify({"result": f"Left clicked at ({x}, {y})"})
    except Exception as e:
        return jsonify({"error": f"Click failed: {str(e)}"}), 500


def handle_right_click(x, y):
    """Perform right click at coordinates"""
    pyautogui.rightClick(x, y)
    return jsonify({"result": f"Right clicked at ({x}, {y})"})


def handle_double_click(x, y):
    """Perform double click at coordinates"""
    pyautogui.doubleClick(x, y)
    return jsonify({"result": f"Double clicked at ({x}, {y})"})


def handle_type(text):
    """Type text"""
    pyautogui.write(text)
    return jsonify({"result": f"Typed: {text}"})


def handle_key(key):
    """Press key or key combination"""
    try:
        # Handle key combinations like 'ctrl+c'
        if "+" in key:
            keys = key.split("+")
            pyautogui.hotkey(*keys)
        else:
            pyautogui.press(key)
        return jsonify({"result": f"Pressed key: {key}"})
    except Exception as e:
        return jsonify({"error": f"Invalid key: {key}"}), 400


def handle_mouse_move(x, y):
    """Move mouse to coordinates"""
    pyautogui.moveTo(x, y)
    return jsonify({"result": f"Moved mouse to ({x}, {y})"})


def handle_scroll(x, y, direction, amount):
    """Scroll at coordinates"""
    pyautogui.moveTo(x, y)
    if direction.lower() in ["up"]:
        pyautogui.scroll(amount)
    elif direction.lower() in ["down"]:
        pyautogui.scroll(-amount)
    else:
        return jsonify({"error": f"Invalid scroll direction: {direction}"}), 400

    return jsonify({"result": f"Scrolled {direction} by {amount} at ({x}, {y})"})


def handle_drag(start_x, start_y, end_x, end_y):
    """Drag from start to end coordinates"""
    pyautogui.dragTo(end_x, end_y, button="left", duration=0.5)
    return jsonify(
        {"result": f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})"}
    )


def handle_wait(duration):
    """Wait for specified duration"""
    time.sleep(duration)
    return jsonify({"result": f"Waited for {duration} seconds"})


# Text editor handlers
def _resolve_path(path, pwd=None):
    """Resolve path relative to pwd if provided and path is relative"""
    if pwd is None:
        pwd = "/home/appuser"  # Default to appuser home directory
    if not os.path.isabs(path):
        return os.path.join(pwd, path)
    return path


def handle_view_file(path, pwd=None):
    """View file contents"""
    try:
        resolved_path = _resolve_path(path, pwd)
        with open(resolved_path, "r") as f:
            content = f.read()
        return jsonify({"content": content})
    except FileNotFoundError:
        return jsonify({"error": f"File not found: {resolved_path}"}), 404


def handle_create_file(path, content, pwd=None):
    """Create file with content"""
    try:
        resolved_path = _resolve_path(path, pwd)
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        with open(resolved_path, "w") as f:
            f.write(content)
        return jsonify({"result": f"Created file: {resolved_path}"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def handle_str_replace(path, old_str, new_str, pwd=None):
    """Replace string in file"""
    try:
        resolved_path = _resolve_path(path, pwd)
        with open(resolved_path, "r") as f:
            content = f.read()

        if old_str not in content:
            return jsonify({"error": f"String not found: {old_str}"}), 400

        new_content = content.replace(old_str, new_str)

        with open(resolved_path, "w") as f:
            f.write(new_content)

        return jsonify({"result": f"Replaced '{old_str}' with '{new_str}' in {path}"})
    except FileNotFoundError:
        return jsonify({"error": f"File not found: {resolved_path}"}), 404


if __name__ == "__main__":
    # Run on all interfaces to allow external connections
    app.run(host="0.0.0.0", port=5000, debug=True)
