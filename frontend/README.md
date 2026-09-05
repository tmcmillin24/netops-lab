# NetOps Lab frontend

The frontend is a dependency-free operations console built with HTML,
CSS, and JavaScript modules. It reads all inventory and runtime state from the
central backend at `http://127.0.0.1:8000` and never calls endpoint mutation
APIs directly.

## Run locally

Start the Containerlab environment and FastAPI backend inside Lima first. From
the repository directory on macOS, serve the frontend:

```bash
python3 -m http.server 8090 --directory frontend
```

Open `http://127.0.0.1:8090`. Do not open `index.html` as a `file://` URL;
JavaScript modules and backend requests require an HTTP origin.

The Dashboard, Network, Systems, Active Directory, and Architecture pages are
implemented. Tickets and Automation are explicitly marked Planned Phase.
Dashboard and device data refresh from one combined overview response every
five seconds. An open device drawer remains selected during successful
refreshes. The Network page includes allowlisted diagnostics and read-only
route/neighbor information; dashboard incident lists and topology nodes open
the same live device details.

The Active Directory page queries the Samba-based DC01 through controlled
backend routes. It displays live domain/DNS health, nine workstation-assigned
employees, disabled former-employee accounts, and department security groups.
A compact summary and horizontal object tabs keep users, computers, groups,
and disabled accounts in separate views. Group membership is shown on demand. User details
expose only allowlisted enable, disable, unlock, password-reset, and membership
controls.

New accounts may be created in the Employees group without an initial device.
The Unassigned Members view lists enabled accounts awaiting placement and lets
an operator assign an available workstation or laptop; its floor determines the
department security group. Background status polling leaves the directory DOM
intact so long user and computer lists keep their scroll position.

The Network page includes a two-step Add Device wizard for workstations and
laptops. Drafting is non-disruptive and proposes an unused floor address,
switch, and printer. Applying a reviewed draft persists the inventory and
performs the clearly labelled Containerlab redeployment. Employee details can
release a device assignment. Unassigned dynamically provisioned devices can
then be removed from their device drawer; assigned devices and baseline
WS01-WS09 remain protected.

If the backend is unavailable, the console clears live data and displays a
visible error state rather than substituting hardcoded status values.

Run the lightweight frontend checks with:

```bash
node frontend/tests/check_frontend.mjs
```

The existing direct endpoint pages remain available for focused testing. The
main console uses only centralized backend routes for actions and live state.
The backend address is intentionally fixed for the current local-only baseline;
a configurable deployment URL and authentication belong to a future hosting
phase.
