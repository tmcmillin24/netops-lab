# NetOps Lab backend

The Phase 4 backend is the safe central interface to the running Containerlab
environment. Run it inside the Lima `netlab` VM so it can discover the lab
containers on Docker's management network and execute allowlisted connectivity
tests from known source containers.

## Setup and start

From the repository directory inside Lima:

```bash
sudo apt-get install python3-venv
python3 -m venv "$HOME/.venvs/netops-lab"
. "$HOME/.venvs/netops-lab/bin/activate"
python3 -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

The API is available at `http://127.0.0.1:8000`, with interactive OpenAPI
documentation at `http://127.0.0.1:8000/docs`. Start Containerlab before the
backend when live device data is required.

Run tests from the repository root with:

```bash
pytest -q backend/tests tests
```

## Routes

- `GET /api/health` — backend health
- `GET /api/lab` — live lab summary
- `GET /api/devices` and `GET /api/devices/{hostname}` — inventory plus runtime status
- `GET /api/printers` and `GET /api/printers/{hostname}` — printer status
- `GET|POST /api/printers/{hostname}/jobs` — queue inspection and job submission
- `POST /api/printers/{hostname}/actions/{action}` — allowlisted printer actions
- `GET /api/workstations` and `GET /api/workstations/{hostname}` — workstation status
- `POST /api/workstations/{hostname}/actions/{action}` — online/offline controls
- `POST /api/connectivity/ping` — controlled known-device ping

Printer actions are `complete`, `offline`, `ready`, `empty-paper`,
`refill-paper`, `empty-toner`, and `refill-toner`. Workstation actions are
`offline` and `online`.

## Safety boundary

The API never accepts shell text, arbitrary IP addresses, or internet targets.
Ping accepts two inventory hostnames. It constructs a fixed argument list for
one ping from the validated source container to the destination's configured
office IP. Printer and workstation actions are mapped to a small allowlist of
existing endpoint API routes.
