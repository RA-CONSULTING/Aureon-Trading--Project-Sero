#!/bin/bash
set -euo pipefail
umask 077
if [[ -f /srv/aureon/import/bootstrap-ready ]]; then exit 0; fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential git curl unzip openssl libespeak1 ffmpeg
id aureon >/dev/null 2>&1 || useradd --system --create-home --home-dir /srv/aureon --shell /usr/sbin/nologin aureon
install -d -m 0700 /srv/aureon/import
install -d -m 0750 -o aureon -g aureon /srv/aureon/runtime
python3 -m venv /srv/aureon/venv
/srv/aureon/venv/bin/python -m pip install --disable-pip-version-check cryptography
date -u +%FT%TZ > /srv/aureon/import/bootstrap-ready
