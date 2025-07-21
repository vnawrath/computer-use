#!/usr/bin/env bash
set -euo pipefail

# Allow overriding geometry via env, but we FIX it here (do not auto-resize)
GEOM="${SCREEN_GEOM:-1280x800x24}"

echo "[entrypoint] Starting Xvfb at geometry ${GEOM}"
Xvfb "${DISPLAY}" -screen 0 "${GEOM}" -nolisten tcp -dpi 96 &
XVFB_PID=$!

# Simple wait loop to ensure X is up
for i in {1..20}; do
  if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

echo "[entrypoint] Starting openbox"
openbox-session >/dev/null 2>&1 &
WM_PID=$!

# Create (optional) x11vnc password file if VNC_PASSWORD supplied
if [ -n "${VNC_PASSWORD}" ]; then
  echo "[entrypoint] Setting VNC password."
  PASSFILE="$HOME/.vncpass"
  mkdir -p "$HOME"
  x11vnc -storepasswd "${VNC_PASSWORD}" "${PASSFILE}"
  PASS_OPTS="-rfbauth ${PASSFILE}"
else
  PASS_OPTS="-nopw"
fi

echo "[entrypoint] Starting x11vnc (fixed size: disabling RandR)"
# -noxrandr ensures clients cannot request size changes
x11vnc -display "${DISPLAY}" \
  -forever -shared -rfbport ${VNC_PORT} \
  -noxdamage -noxfixes -noxrecord -noxrandr \
  ${PASS_OPTS} \
  -bg -o /tmp/x11vnc.log

echo "[entrypoint] Starting noVNC on port ${NO_VNC_PORT}"
/opt/noVNC/utils/novnc_proxy --vnc localhost:${VNC_PORT} --listen ${NO_VNC_PORT} &
NOVNC_PID=$!

echo "[entrypoint] Waiting for X11 to be fully ready..."
sleep 2

# Set up X11 permissions for appuser
export DISPLAY=:0
# Create a dummy .Xauthority file to avoid auth errors
touch "$HOME/.Xauthority"
# Allow all local connections to X11 for simplicity in container
xhost +local: >/dev/null 2>&1 || true
# Set XAUTHORITY environment
export XAUTHORITY="$HOME/.Xauthority"

echo "[entrypoint] Starting Computer Control API on port 5000"
cd /app
python3 computer_control_api.py &
API_PID=$!

# Trap signals to clean up
cleanup() {
  echo "[entrypoint] Shutting down..."
  kill $API_PID $NOVNC_PID $WM_PID $XVFB_PID 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM

echo "[entrypoint] All services started. (Xvfb pid $XVFB_PID, API pid $API_PID)"
wait $NOVNC_PID
