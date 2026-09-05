# NetOps Lab backend

The backend is the safe central interface to the running Containerlab
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
- `POST /api/devices/{hostname}/actions/{action}` — allowlisted infrastructure controls
- `POST /api/connectivity/ping` — controlled known-device ping
- `POST /api/connectivity/diagnostic` — allowlisted reachability, traceroute, DNS, or service check
- `GET /api/connectivity/network-info/{hostname}` — routes and neighbor information
- `GET /api/connectivity/events` — recent backend event history
- `GET /api/fileserver/status` — FILE01 device, SMB, share, and fault state
- `GET /api/fileserver/shares` — configured share inventory and group mappings
- `POST /api/fileserver/access-check` — controlled user/device/share authorization check
- `GET /api/fileserver/shares/{share}/access` — effective users derived from live AD groups
- `POST /api/fileserver/shares/{share}/memberships` — add/remove a known user through an allowed share access group
- `POST /api/fileserver/faults/{action}` — allowlisted Phase 9 fault injection (no command input)
- `GET /api/directory` — DC01 health, users, groups, and membership overview
- `GET /api/provisioning/options` — safe floor, employee, and hostname choices
- `POST /api/provisioning/workstations/draft` — validate and reserve a proposed workstation configuration
- `POST /api/provisioning/workstations/apply` — explicitly build and redeploy the reviewed Containerlab change
- `GET /api/directory/users/{username}` — one managed directory identity
- `POST /api/directory/users/{username}/actions/{action}` — enable, disable, or unlock
- `POST /api/directory/users/{username}/password-reset` — one-time lab password reset
- `POST /api/directory/groups/{group}/members/{username}/{action}` — controlled membership change

Printer actions are `complete`, `offline`, `ready`, `empty-paper`,
`refill-paper`, `empty-toner`, and `refill-toner`. Workstation actions are
`offline` and `online`.

## Safety boundary

The API never accepts shell text, arbitrary IP addresses, or internet targets.
Diagnostics accept inventory hostnames and a small allowlist of operation
types. Every runtime operation constructs a fixed argument list without a
shell. Printer, workstation, and infrastructure actions are similarly mapped
to explicit allowlists. Runtime errors return structured messages without
granting access to host commands.

Runtime state and recent events are intentionally in memory. They reset when
the endpoint containers or backend process are recreated.

Directory operations accept only users and groups declared in
`configs/ad_baseline.json`. Password resets generate a temporary value at
runtime and return it once; credentials are not stored in source or application
logs. The backend never accepts PowerShell, LDAP filters, or Samba command text.
