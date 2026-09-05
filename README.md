# NetOps Lab

NetOps Lab is a lightweight, interactive small-office infrastructure lab. It
runs real containerized endpoint services and network links while providing a
safe foundation for monitoring, troubleshooting, and automation exercises.

The current Phase 3 topology contains RTR01, the CORE01 Layer-3 core, three
Linux bridge access switches, nine workstations, and three printers. Each
access network contains three workstations and one printer, with routing
between access networks provided by CORE01.

The complete device inventory and addressing are recorded in
`configs/inventory.json` and `configs/IP_PLAN.md`.

## Requirements

- Apple Silicon macOS host
- Lima VM named `netlab`
- Docker and Containerlab installed inside Lima
- approximately 2 CPUs, 4 GB RAM, and 25 GB disk assigned to Lima

Docker and Containerlab commands must run inside Lima, not in the normal macOS
shell.

## Build and run

Enter the Lima VM:

```bash
limactl shell netlab
```

Change to this repository's mounted macOS path. On the current development Mac:

```bash
cd /Users/tristanmcmillin/Desktop/small-office-lab
```

Build the reusable endpoint and network images:

```bash
./scripts/build-images.sh
```

Deploy and inspect the lab:

```bash
./scripts/lab.sh deploy
./scripts/lab.sh inspect
```

Open the endpoint interfaces from macOS:

- PRNT01: <http://127.0.0.1:8080>
- WS01: <http://127.0.0.1:8081>
- PRNT02: <http://127.0.0.1:8082>
- PRNT03: <http://127.0.0.1:8083>

Run the Phase 5 operations console from the macOS terminal:

```bash
python3 -m http.server 8090 --directory frontend
```

Then open <http://127.0.0.1:8090>. The console provides Dashboard, Network,
Systems, and Architecture views backed by the centralized API. Active
Directory, Tickets, and Automation are labeled Planned Phase. Detailed launch
and behavior notes are in [`frontend/README.md`](frontend/README.md).

## Central backend API

Phase 4 provides a FastAPI service that runs inside Lima and safely aggregates
the inventory, Docker container availability, and live endpoint APIs. Setup,
startup, test commands, routes, and safety restrictions are documented in
[`backend/README.md`](backend/README.md). The development API uses port 8000.

Destroy the lab when finished:

```bash
./scripts/lab.sh destroy
```

The lifecycle script defaults `CLAB_LABDIR_BASE` to Linux-local
`$HOME/containerlab-runtime`. This avoids writing Containerlab runtime output to
the macOS-mounted repository. An existing `CLAB_LABDIR_BASE` value takes
precedence.

## Current limitations

- Printer state is stored in memory and resets on redeployment.
- Editing endpoint source requires rebuilding its image and redeploying the lab.
- Access networks are separate routed subnets but do not use VLAN tagging yet.
- WS01 is the only workstation page published to macOS; all three printer
  pages are published for endpoint testing.
- The reserved services network and API01 are not deployed yet.
- AWS, Windows Server, Active Directory, ticketing, and authentication are not
  part of the current phase.
