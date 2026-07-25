# The Space image: the Gradio app plus a headless Bambu Studio, so the
# "Slice with Bambu Studio" box actually produces a printer-ready .gcode.3mf
# instead of falling back to an unsliced plate.
#
# Build context is the assembled Space payload (app.py, chess2d/,
# requirements.txt) -- see scripts/deploy_space.py. To build it locally:
#
#   python scripts/deploy_space.py --space-id local/build --dry-run
#   docker build -t chess2d build/space
#   docker run --rm -p 7860:7860 chess2d
#
# Ubuntu 24.04 on purpose: Bambu Studio publishes its Linux build as an
# ubuntu-24.04 AppImage, and an older base (python:*-slim is Debian 12) has too
# old a glibc to run it.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Two dependency sets in one layer: Python for the app, and the GTK/GL/media
# libraries the AppImage links against. xvfb is not optional -- Bambu Studio is
# a GUI program whose command line still wants a display to start on.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        python3 \
        python3-venv \
        xvfb \
        libgtk-3-0 \
        libwebkit2gtk-4.1-0 \
        libsoup-3.0-0 \
        libgl1 \
        libglu1-mesa \
        libegl1 \
        libgstreamer1.0-0 \
        libgstreamer-plugins-base1.0-0 \
        libsecret-1-0 \
        libnotify4 \
        libdbus-1-3 \
        libcurl4 \
        libssl3 \
        libx11-6 \
        libxrandr2 \
        libxinerama1 \
        libxcursor1 \
        libxi6 \
        libfontconfig1 \
        libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Bambu Studio, extracted rather than mounted: --appimage-extract unpacks
# without FUSE, which containers do not have.
#
# Left empty, the release feed is queried for the newest Ubuntu AppImage. That
# query is an unauthenticated GitHub API call (60/hour per IP) and it makes the
# image non-reproducible, so pin an asset for anything you care about:
#
#   docker build --build-arg BAMBU_STUDIO_URL=https://.../Bambu_Studio_ubuntu-24.04_vX.AppImage .
#
# The last step records where the release put its profile tree -- it has moved
# between versions -- so $BAMBU_PROFILES below is a fact, not a guess.
ARG BAMBU_STUDIO_URL=""
RUN set -eux; \
    url="${BAMBU_STUDIO_URL}"; \
    if [ -z "$url" ]; then \
        url="$(curl -fsSL https://api.github.com/repos/bambulab/BambuStudio/releases/latest \
              | grep -o 'https://[^\"]*ubuntu[^\"]*\.AppImage' | head -n 1)"; \
    fi; \
    test -n "$url" || { echo "could not resolve a Bambu Studio AppImage URL"; exit 1; }; \
    echo "Installing Bambu Studio from $url"; \
    curl -fL --retry 3 -o /tmp/BambuStudio.AppImage "$url"; \
    chmod +x /tmp/BambuStudio.AppImage; \
    cd /opt && /tmp/BambuStudio.AppImage --appimage-extract >/dev/null; \
    mv /opt/squashfs-root /opt/bambustudio; \
    rm /tmp/BambuStudio.AppImage; \
    profiles="$(find /opt/bambustudio -type d -name profiles -print -quit)"; \
    test -n "$profiles" || { echo "no profiles/ directory in the AppImage"; exit 1; }; \
    ln -sfn "$profiles" /opt/bambustudio-profiles; \
    echo "profiles: $profiles"

# A wrapper so the app finds one stable path: it supplies the virtual display
# the GUI binary insists on, and -a picks a free server number per call.
RUN printf '%s\n' \
        '#!/bin/sh' \
        'exec xvfb-run -a --server-args="-screen 0 1280x1024x24" /opt/bambustudio/AppRun "$@"' \
        > /usr/local/bin/bambu-studio \
    && chmod +x /usr/local/bin/bambu-studio

# chess2d's own discovery hooks (see src/chess2d/bambu.py): without these it
# would search $PATH and the usual install locations and find nothing usable.
ENV BAMBU_STUDIO=/usr/local/bin/bambu-studio \
    BAMBU_PROFILES=/opt/bambustudio-profiles

# A smoke test with the build log as its output: if the AppImage cannot start at
# all (a missing library, the wrong glibc) this prints the failure where a human
# will see it. The exit code is not trusted -- Bambu Studio's CLI has returned
# non-zero for --help across releases -- so it does not gate the build; the
# `image` CI job slices a real plate for that.
RUN set -eux; \
    test -x /opt/bambustudio/AppRun; \
    bambu-studio --help > /tmp/bambu-help.txt 2>&1 || true; \
    head -n 20 /tmp/bambu-help.txt; \
    rm -f /tmp/bambu-help.txt

# Hugging Face Spaces run the container as UID 1000; matching it here keeps the
# app's temp files and Bambu Studio's config directory writable. Ubuntu 24.04
# ships its own UID 1000 (`ubuntu`), which has to go first or useradd fails.
RUN userdel -r ubuntu 2>/dev/null || true; \
    useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/opt/venv/bin:/usr/local/bin:/usr/bin:/bin \
    PYTHONUNBUFFERED=1 \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860

# Ubuntu's Python is externally managed, so the app gets its own venv.
RUN python3 -m venv /opt/venv && chown -R user:user /opt/venv

USER user
WORKDIR /home/user/app

COPY --chown=user requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

EXPOSE 7860

# Liveness only. A missing slicer deliberately does *not* fail this: the app
# still serves generic 3MFs, and restarting the container would not conjure
# Bambu Studio back. The build log and the `image` CI job cover that instead.
HEALTHCHECK --interval=60s --timeout=15s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/', timeout=10)"

CMD ["python", "app.py"]
