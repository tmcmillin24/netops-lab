FROM debian:12-slim

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    dnsutils iproute2 iputils-ping python3 samba samba-ad-provision samba-dsdb-modules \
    samba-vfs-modules smbclient winbind \
  && rm -rf /var/lib/apt/lists/*

RUN rm -f /etc/samba/smb.conf

COPY configs/ad_baseline.json /config/ad_baseline.json
COPY containers/domain-controller/provision.py /usr/local/lib/netops/provision.py
COPY containers/domain-controller/entrypoint.sh /usr/local/bin/netops-dc01

RUN chmod 0755 /usr/local/bin/netops-dc01

EXPOSE 53/tcp 53/udp 88/tcp 88/udp 135/tcp 137/udp 138/udp 139/tcp 389/tcp 389/udp 445/tcp 464/tcp 464/udp 636/tcp 3268/tcp 3269/tcp

ENTRYPOINT ["/usr/local/bin/netops-dc01"]
