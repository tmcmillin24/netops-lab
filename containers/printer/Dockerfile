FROM python:3.13-alpine

WORKDIR /app

COPY containers/__init__.py /app/containers/__init__.py
COPY containers/common /app/containers/common
COPY containers/printer /app/containers/printer
COPY configs/inventory.json /config/inventory.json

ENV PYTHONPATH=/app
ENV INVENTORY_PATH=/config/inventory.json

EXPOSE 8080

CMD ["python3", "-m", "containers.printer.printer_api"]
