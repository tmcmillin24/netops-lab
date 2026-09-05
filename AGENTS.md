# NetOps Lab Agent Instructions

## Purpose

NetOps Lab is an interactive small-office infrastructure operations portfolio lab.

Prioritize:
1. Real infrastructure behavior
2. Interactivity
3. Troubleshooting value
4. Low resource usage
5. Clear, maintainable code
6. ARM64 compatibility

Do not turn the project into a primarily cosmetic frontend demo.

## Environment

Host:
- macOS
- Apple Silicon M4

Infrastructure runtime:
- Lima VM: `netlab`
- Docker runs inside Lima
- Containerlab runs inside Lima

Enter Lima with:

```bash
limactl shell netlab
```

Deploy:

```bash
containerlab deploy -t lab/netops.clab.yml
```

Destroy:

```bash
containerlab destroy -t lab/netops.clab.yml
```

Do not assume Containerlab runs directly on macOS.

Do not use `docker restart` on Containerlab nodes. It has previously removed Containerlab-created interfaces such as `eth1`. Redeploy instead.

## Architecture Rules

Preserve:
- Lima
- Docker
- Containerlab
- current working device behavior
- ARM64 compatibility
- low local resource usage

Do not:
- introduce AWS unless explicitly requested
- introduce paid services unless explicitly requested
- expose arbitrary shell execution
- add unnecessary frameworks/dependencies
- silently restructure the repository
- replace working functionality merely to refactor it

Prefer small, testable changes.

## Repository Areas

- `lab/` — topology
- `containers/` — simulated devices/services
- `backend/` — centralized API/backend
- `frontend/` — operations console
- `configs/` — shared configuration
- `docs/` — project documentation
- `tests/` — automated tests

## Current Lab

The project currently includes the small-office topology and simulated workstation/printer environment.

Detailed architecture, device mappings, printer rules, future roadmap, and historical decisions are documented in:

`docs/PROJECT_CONTEXT.md`

Do not automatically reread that entire file for every task.

Read only the relevant sections when:
- the requested change depends on an existing design decision
- architecture is being changed
- device behavior is being changed
- the user explicitly asks you to consult it

Use repository code as the source of truth for current implementation details.

## Coding

Python:
- 4-space indentation
- `snake_case`
- `UPPER_SNAKE_CASE` constants
- `PascalCase` classes

HTML/CSS/JavaScript/YAML:
- 2-space indentation

Prefer readable code over unnecessary abstraction.

## Working Style

For normal tasks:
1. Inspect only the files relevant to the request.
2. Make the smallest reasonable change.
3. Test the changed behavior.
4. Summarize the result.
5. Stop.

Do not repeatedly inspect the entire repository unless necessary.

Do not provide long explanations of unchanged architecture.

Do not begin unrelated future work.

For major architectural changes:
- explain the proposed design first
- identify risks
- wait for approval if the change is significant

## Testing

Run only tests/checks relevant to the changed area.

Examples:

Python syntax:

```bash
python3 -m py_compile <changed-file>
```

Use targeted automated tests when available.

Redeploy Containerlab only when container/network behavior actually requires it.

Do not perform expensive or redundant validation when a smaller targeted check is sufficient.

## Documentation

Update documentation only when implementation or a real design decision changes.

Do not rewrite `PROJECT_CONTEXT.md` after routine code changes.

## Git

Do not commit:
- secrets
- credentials
- runtime artifacts
- temporary files

Use concise commit messages describing completed behavior.