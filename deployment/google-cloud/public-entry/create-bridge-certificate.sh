#!/bin/sh
# Run on the VM as root. Never copy the private key off the VM.
set -eu
[ "$(id -u)" = 0 ] || { echo 'root_required' >&2; exit 1; }
getent group aureon-public >/dev/null || groupadd --system aureon-public
id aureon-public >/dev/null 2>&1 || useradd --system --gid aureon-public --home-dir /nonexistent --shell /usr/sbin/nologin aureon-public
# The operator runs under a different unprivileged identity and needs to read
# only the public certificate.  Execute-only access permits that exact known
# path while the 0640 private key remains unavailable outside the bridge group.
install -d -o root -g aureon-public -m 0751 /etc/aureon-public
# Deliberately refuse to overwrite an existing TLS identity.
[ ! -e /etc/aureon-public/bridge-key.pem ] && [ ! -e /etc/aureon-public/bridge-cert.pem ] || { echo 'tls_identity_already_exists' >&2; exit 1; }
umask 0077
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 180 \
  -subj '/CN=aureon-private-bridge' \
  -addext 'subjectAltName=IP:10.40.0.2' \
  -addext 'basicConstraints=critical,CA:TRUE' \
  -addext 'keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign' \
  -addext 'extendedKeyUsage=serverAuth' \
  -keyout /etc/aureon-public/bridge-key.pem \
  -out /etc/aureon-public/bridge-cert.pem
chown root:aureon-public /etc/aureon-public/bridge-key.pem /etc/aureon-public/bridge-cert.pem
chmod 0640 /etc/aureon-public/bridge-key.pem
# The certificate is public verification material used by the loopback
# operator. The private key remains restricted to the bridge group.
chmod 0644 /etc/aureon-public/bridge-cert.pem
openssl x509 -in /etc/aureon-public/bridge-cert.pem -noout -fingerprint -sha256 -enddate
