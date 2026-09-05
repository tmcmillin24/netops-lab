#!/bin/sh

set -eu

config=/etc/samba/smb.conf

if [ ! -f "$config" ]; then
  admin_password=$(python3 -c 'import secrets; print("N0!" + secrets.token_urlsafe(24))')
  samba-tool domain provision \
    --server-role=dc \
    --realm=NETOPSLAB.TEST \
    --domain=NETOPSLAB \
    --host-name=DC01 \
    --host-ip=10.10.40.10 \
    --dns-backend=SAMBA_INTERNAL \
    --use-rfc2307 \
    --adminpass="$admin_password"
  unset admin_password
fi

python3 /usr/local/lib/netops/provision.py

exec samba --foreground --no-process-group
