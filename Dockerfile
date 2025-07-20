# syntax=docker/dockerfile:1
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:0 \
    SCREEN_GEOM=1280x800x24 \
    NO_VNC_PORT=6080 \
    VNC_PORT=5900 \
    USER=appuser \
    HOME=/home/appuser

# Install base packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc openbox curl ca-certificates python3 net-tools \
    xauth xfonts-base x11-xkb-utils \
    # noVNC + websockify runtime deps
    git \
 && rm -rf /var/lib/apt/lists/*

# Add a non-root user
RUN useradd -m -d $HOME -s /bin/bash $USER

# Fetch a known stable noVNC (tag) + websockify (submodule)
RUN git clone --depth 1 --branch v1.4.0 https://github.com/novnc/noVNC.git /opt/noVNC \
 && git clone --depth 1 --branch v0.11.0 https://github.com/novnc/websockify /opt/noVNC/utils/websockify \
 && ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html

# Entry script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Optional: set a VNC/password (empty by default). User can set at runtime.
ENV VNC_PASSWORD=""

# tini for proper signal handling
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*

EXPOSE 6080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -fs http://localhost:${NO_VNC_PORT}/ || exit 1

USER $USER
WORKDIR $HOME

ENTRYPOINT ["/usr/bin/tini","--","/entrypoint.sh"]
