FROM debian:12-slim

RUN apt-get update \
  && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends iproute2 iputils-ping python3 samba \
  && rm -rf /var/lib/apt/lists/*

COPY containers/file-server/fileserver_api.py /usr/local/lib/netops/fileserver_api.py
COPY containers/file-server/entrypoint.sh /usr/local/bin/netops-file01
COPY containers/file-server/smb.conf /etc/samba/smb.conf
COPY configs/fileserver_shares.json /config/fileserver_shares.json
RUN chmod 0755 /usr/local/bin/netops-file01 \
  && mkdir -p /srv/shares/Public /srv/shares/HR /srv/shares/Finance /srv/shares/Engineering /srv/shares/IT-Tools \
  && chmod -R 0775 /srv/shares

EXPOSE 445 8092

ENTRYPOINT ["/usr/local/bin/netops-file01"]
