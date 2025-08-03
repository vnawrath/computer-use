# syntax=docker/dockerfile:1
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:0 \
    SCREEN_GEOM=1280x800x24 \
    NO_VNC_PORT=6080 \
    VNC_PORT=5900 \
    USER=appuser \
    HOME=/home/appuser

# Install base packages (excluding firefox for now)
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb x11vnc openbox curl ca-certificates python3 python3-pip net-tools \
    xauth xfonts-base x11-xkb-utils \
    # GUI applications
    mousepad \
    kitty \
    pcmanfm \
    # Additional utilities
    xdg-utils \
    # noVNC + websockify runtime deps
    git \
    # Dependencies for Firefox installation
    wget \
    gpg \
    # Dependencies for PyAutoGUI
    python3-tk python3-dev scrot xsel \
    # SSH client for generating SSH keys
    openssh-client \
 && rm -rf /var/lib/apt/lists/*

# Install lazygit manually from GitHub releases
RUN LAZYGIT_VERSION=$(curl -s "https://api.github.com/repos/jesseduffield/lazygit/releases/latest" | grep -Po '"tag_name": "v\K[^"]*') \
 && curl -Lo lazygit.tar.gz "https://github.com/jesseduffield/lazygit/releases/latest/download/lazygit_${LAZYGIT_VERSION}_Linux_x86_64.tar.gz" \
 && tar -xf lazygit.tar.gz -C /usr/local/bin/ \
 && rm lazygit.tar.gz

# Install Firefox from Mozilla's official APT repository
RUN install -d -m 0755 /etc/apt/keyrings && \
    wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null && \
    gpg -n -q --import --import-options import-show /etc/apt/keyrings/packages.mozilla.org.asc | awk '/pub/{getline; gsub(/^ +| +$/,""); if($0 == "35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3") print "\nThe key fingerprint matches ("$0").\n"; else print "\nVerification failed: the fingerprint ("$0") does not match the expected one.\n"}' && \
    echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" | tee -a /etc/apt/sources.list.d/mozilla.list > /dev/null && \
    echo 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000' | tee /etc/apt/preferences.d/mozilla && \
    apt-get update && apt-get install -y --no-install-recommends \
        firefox \
        # Additional dependencies for Firefox
        libpci-dev \
        libcanberra-gtk3-module \
        libgles2-mesa-dev \
        dbus-x11 \
        fonts-dejavu-core \
        libnss3-dev \
 && rm -rf /var/lib/apt/lists/*

# Install Obsidian from official .deb package
RUN OBSIDIAN_VERSION=$(curl -s "https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest" | grep -Po '"tag_name": "v\K[^"]*') \
 && curl -Lo obsidian.deb "https://github.com/obsidianmd/obsidian-releases/releases/latest/download/obsidian_${OBSIDIAN_VERSION}_amd64.deb" \
 && apt-get update && apt-get install -y --no-install-recommends \
    ./obsidian.deb \
    # Additional dependencies for Obsidian
    libatomic1 \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
 && rm obsidian.deb \
 && rm -rf /var/lib/apt/lists/*

# Create Obsidian wrapper script to handle sandboxing issues in containers
RUN echo '#!/bin/bash\n\
# Obsidian wrapper script for Docker containers\n\
# Disables sandboxing to prevent namespace issues\n\
exec /opt/Obsidian/obsidian \\\n\
  --no-sandbox \\\n\
  --disable-setuid-sandbox \\\n\
  --disable-dev-shm-usage \\\n\
  --disable-gpu \\\n\
  --disable-software-rasterizer \\\n\
  --disable-background-timer-throttling \\\n\
  --disable-backgrounding-occluded-windows \\\n\
  --disable-renderer-backgrounding \\\n\
  --disable-features=TranslateUI \\\n\
  --disable-ipc-flooding-protection \\\n\
  "$@"' > /usr/local/bin/obsidian-safe \
 && chmod +x /usr/local/bin/obsidian-safe \
 && ln -sf /usr/local/bin/obsidian-safe /usr/local/bin/obsidian

# Add a non-root user
RUN useradd -m -d $HOME -s /bin/bash $USER

# Fetch a known stable noVNC (tag) + websockify (submodule)
RUN git clone --depth 1 --branch v1.4.0 https://github.com/novnc/noVNC.git /opt/noVNC \
 && git clone --depth 1 --branch v0.11.0 https://github.com/novnc/websockify /opt/noVNC/utils/websockify \
 && ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html

# Install Python packages for the Computer Control API
RUN pip3 install --no-cache-dir \
    flask==2.3.3 \
    flask-limiter==3.5.0 \
    pyautogui==0.9.54 \
    pillow==10.0.1

# Create app directory and copy the Computer Control API there
RUN mkdir -p /app
COPY computer_control_api.py /app/computer_control_api.py
COPY API_USAGE.md /app/API_USAGE.md

# Entry script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Optional: set a VNC/password (empty by default). User can set at runtime.
ENV VNC_PASSWORD=""

# tini for proper signal handling
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*

EXPOSE 6080 5000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -fs http://localhost:${NO_VNC_PORT}/ || exit 1

USER $USER
WORKDIR $HOME

ENTRYPOINT ["/usr/bin/tini","--","/entrypoint.sh"]
