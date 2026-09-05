# NetOps Lab frontend

The Phase 5 frontend is a dependency-free operations console built with HTML,
CSS, and JavaScript modules. It reads all inventory and runtime state from the
Phase 4 backend at `http://127.0.0.1:8000` and never calls endpoint mutation
APIs directly.

## Run locally

Start the Containerlab environment and FastAPI backend inside Lima first. From
the repository directory on macOS, serve the frontend:

```bash
python3 -m http.server 8090 --directory frontend
```

Open `http://127.0.0.1:8090`. Do not open `index.html` as a `file://` URL;
JavaScript modules and backend requests require an HTTP origin.

The Dashboard, Network, Systems, and Architecture pages are implemented.
Active Directory, Tickets, and Automation are explicitly marked Planned Phase.
Dashboard and device data refresh in place every five seconds. An open device
drawer remains selected during successful refreshes.

If the backend is unavailable, the console clears live data and displays a
visible error state rather than substituting hardcoded status values.

Run the lightweight frontend checks with:

```bash
node frontend/tests/check_frontend.mjs
```

The existing direct endpoint pages remain available for focused testing. The
main console uses only centralized backend routes for actions and live state.
