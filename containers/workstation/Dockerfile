FROM python:3.13-alpine

WORKDIR /app

COPY containers/__init__.py /app/containers/__init__.py
COPY containers/common /app/containers/common
COPY containers/workstation /app/containers/workstation
COPY configs/inventory.json /config/inventory.json
COPY configs/lab_extensions.json /config/lab_extensions.json

ENV PYTHONPATH=/app
ENV INVENTORY_PATH=/config/inventory.json

EXPOSE 8081

CMD ["python3", "-m", "containers.workstation.workstation_api"]
