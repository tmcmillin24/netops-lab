# Repository Guidelines

## Project Purpose

NetOps Lab is an interactive small-office infrastructure operations lab built to demonstrate practical system administration, networking, troubleshooting, monitoring, automation, and backend integration skills.

The final project should be useful as a technical portfolio piece. A recruiter or hiring manager should be able to interact with the environment rather than only view static screenshots.

Keep the project:

- lightweight
- interactive
- beginner-readable
- ARM64 compatible
- free/local during development
- realistic enough to demonstrate infrastructure concepts without unnecessary complexity

Do not redesign the overall architecture or introduce large frameworks unless there is a clear reason.

## Development Environment

The repository is stored on macOS.

Development machine:

- Apple Silicon MacBook Pro
- M4 processor
- macOS host

Docker and Containerlab do **not** run directly in the normal macOS environment.

They run inside a Lima Linux VM named:

`netlab`

Enter the Linux environment from the normal Mac terminal with:

```bash
limactl shell netlab
```

Once inside Lima, build the local endpoint images and deploy the lab with:

```bash
./scripts/build-images.sh
./scripts/lab.sh deploy
```

Destroy the lab with:

```bash
./scripts/lab.sh destroy
```

Do not assume `containerlab` is available from the normal macOS shell.

Do not use `docker restart` on Containerlab nodes as the normal reload method. Doing so previously caused Containerlab-created network interfaces such as `eth1` to disappear.

When container or topology behavior needs a clean restart, destroy and redeploy the Containerlab topology instead.

Containerlab runtime files use the `CLAB_LABDIR_BASE` environment variable inside Lima.

The lifecycle script defaults that variable to the Lima-local
`$HOME/containerlab-runtime` directory when it is not already set.

## Project Structure

- `lab/` - Containerlab topology definitions
- `containers/` - simulated infrastructure devices and services
- `containers/common/` - shared inventory loading and validation
- `containers/printer/` - reusable PRNT01-PRNT03 model, API, and interface
- `containers/workstation/` - reusable WS01-WS09 model, API, and interface
- `containers/network/` - lightweight Linux routing and switching image
- `frontend/` - future primary NetOps Lab user interface
- `backend/` - future centralized backend/API
- `configs/` - infrastructure configuration
- `docs/` - architecture, project context, and documentation
- `scripts/` - repeatable image-build and Containerlab lifecycle commands

Keep new files grouped by responsibility rather than placing unrelated files at the repository root.

## Current Network

The current lab contains RTR01, CORE01, SW01-SW03, WS01-WS09, and
PRNT01-PRNT03. CORE01 routes between three access networks, and each SW node
uses a real Linux bridge for Layer-2 forwarding.

- SW01 / `10.10.10.0/24`: WS01-WS03 and PRNT01
- SW02 / `10.10.20.0/24`: WS04-WS06 and PRNT02
- SW03 / `10.10.30.0/24`: WS07-WS09 and PRNT03
- RTR01-CORE01 transit: `10.10.254.0/30`

The authoritative device mapping is `configs/inventory.json`; the readable
address plan is `configs/IP_PLAN.md`.

The printer interface is accessible from macOS at:

`http://127.0.0.1:8080`

The workstation interface is accessible from macOS at:

`http://127.0.0.1:8081`

PRNT02 and PRNT03 are exposed for testing at ports 8082 and 8083. Endpoint
identity and assignments come from `configs/inventory.json`; topology nodes
set only `DEVICE_NAME` rather than duplicating inventory fields in environment
variables.

Containerlab also creates separate management interfaces and management IP addresses.

Do not confuse Containerlab management addresses with the simulated office-network addresses.

## PRNT01 Behavior

PRNT01 is intended to behave like a real managed network endpoint rather than a static mockup.

Its current implementation includes:

- printer online/offline state
- paper consumption
- toner consumption
- print queue
- randomized print-job page counts
- source workstation information
- resource warnings
- failed print conditions
- recovery/refill actions
- HTTP API behavior
- interactive browser controls

Detailed printer behavior and long-term project direction are documented in:

`docs/PROJECT_CONTEXT.md`

Read that file before changing printer behavior.

## Coding Guidelines

Python:

- use 4-space indentation
- use `snake_case` for functions and variables
- use `UPPER_SNAKE_CASE` for constants
- use `PascalCase` for classes

HTML, CSS, JavaScript, and YAML:

- use 2-space indentation

Prefer simple, readable implementations over unnecessary abstraction.

Keep infrastructure behavior separate from presentation logic where practical.

Do not expose unrestricted shell execution or dangerous administrative functionality through the public-facing demo.

## Agent Behavior

Before making major architectural changes, explain the proposed change and why it is needed.

Do not:

- replace Lima
- replace Containerlab
- introduce paid services during local development
- add unnecessary dependencies
- remove working behavior simply to refactor it
- expose secrets or credentials
- assume x86-only container images
- silently restructure the repository
- turn the project into primarily a frontend design exercise
- replace real infrastructure behavior with purely cosmetic simulations when real behavior can reasonably be implemented

Prefer small, testable changes.

Preserve realistic infrastructure dependencies and failure states.

The project owner is learning while building this lab, so implementations should remain understandable and maintainable.

Read `docs/PROJECT_CONTEXT.md` before making project changes.

## Testing

For Python changes, perform a syntax check when appropriate:

```bash
python3 -m py_compile \
  containers/printer/printer_api.py \
  containers/workstation/workstation_api.py
```

When container behavior changes, redeploy the Containerlab topology and verify affected functionality.

Test both successful and failure scenarios.

Examples include:

- printer online and accepting jobs
- printer offline and rejecting jobs
- insufficient paper
- insufficient toner
- successful print completion
- resource warning thresholds
- recovery after refilling resources

Visible interface changes should also be checked in the browser.

## Git

The GitHub repository is:

`tmcmillin24/netops-lab`

The repository is intended to support development from multiple computers.

Use concise commit messages describing completed behavior.

Examples:

- `Build interactive printer simulation`
- `Add printer queue failure handling`
- `Add workstation source to print jobs`
- `Add printer resource warning thresholds`

Do not commit:

- credentials
- secrets
- Containerlab runtime files
- generated temporary files
- machine-specific runtime artifacts

Network nodes, workstations, and printers run from locally built ARM64 images.
Application source is copied into the images at build time, so source changes
require rebuilding the images before redeploying the topology. Do not
reintroduce machine-specific source bind paths without a deliberate reason and
portability testing.

## Project Context

`AGENTS.md` contains working rules for agents and contributors.

`docs/PROJECT_CONTEXT.md` contains the larger project vision, current technical state, infrastructure decisions, printer simulation rules, and planned future architecture.

Both files should be treated as standing project documentation and kept updated as major design decisions are made.
