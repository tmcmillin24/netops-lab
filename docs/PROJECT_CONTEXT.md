# NetOps Lab Project Context

## Big Picture Vision

NetOps Lab is meant to become a realistic, interactive small-office infrastructure environment that demonstrates practical systems administration, networking, troubleshooting, monitoring, automation, and IT operations skills.

The goal is not to build a static portfolio website with screenshots.

The goal is to build an actual lab where the web interface is connected to real containerized services, simulated endpoints, network devices, and infrastructure behavior.

A recruiter or hiring manager should eventually be able to open the project and interact with a small office environment through a safe frontend.

The project should feel like a lightweight operations console for a real office network.

## Project Goal

The purpose of NetOps Lab is to provide hands-on infrastructure experience while also creating a portfolio project that demonstrates practical:

- system administration
- networking
- troubleshooting
- monitoring
- automation
- backend development
- API integration
- infrastructure operations

The frontend is intended to act as a safe control and visualization layer over actual containerized services and network infrastructure.

The final project should demonstrate real behavior, not just cosmetic status cards.

## Development Philosophy

Development should remain:

- lightweight
- fun and interactive
- inexpensive
- local-first
- ARM64 compatible
- understandable to someone learning infrastructure development

Use free tools and services during development.

AWS deployment may happen later, but AWS should not be required for current development.

Avoid excessive local CPU, memory, and disk usage.

Prefer working infrastructure behavior over unnecessary visual complexity.

## Development Machines

The project is intended to be developed from multiple computers.

The GitHub repository is the shared source of truth so development can continue from either machine.

Current primary development machine:

- 2025 MacBook Pro
- Apple M4
- macOS

## Repository

GitHub repository:

`tmcmillin24/netops-lab`

Current local project path on the Mac:

`~/Desktop/small-office-lab`

## Runtime Architecture

macOS is the development host.

Lima provides a lightweight Linux virtual machine named:

`netlab`

The Lima VM currently uses approximately:

- 2 CPUs
- 4 GB RAM
- 25 GB disk

Docker runs inside Lima.

Containerlab runs inside Lima.

Containerlab should not be expected to run directly from the normal macOS terminal.

Enter the Lima environment from macOS with:

```bash
limactl shell netlab
```

## Containerlab Runtime

Containerlab previously had problems writing generated runtime files into the macOS-mounted repository.

The environment therefore uses:

`CLAB_LABDIR_BASE`

pointing to a Linux-local Containerlab runtime directory.

This setting is persisted in the Lima user's shell configuration.

Do not move Containerlab runtime output back into the repository without intentionally testing the change.

The repository provides `scripts/lab.sh`, which uses the existing
`CLAB_LABDIR_BASE` value or defaults it to the Lima-local
`$HOME/containerlab-runtime` directory. The endpoint images are built inside
Lima with `scripts/build-images.sh`.

## Current Topology

Topology file:

`lab/netops.clab.yml`

Current simulated infrastructure:

- RTR01 - lightweight Linux router/firewall boundary
- CORE01 - Linux Layer-3 core routing between access networks
- SW01-SW03 - Linux bridge access switches
- WS01-WS09 - parameterized Linux workstation endpoints
- PRNT01-PRNT03 - parameterized printer endpoints
- DC01 - ARM64 Samba Active Directory domain controller and DNS service
- FILE01 - ARM64 Samba file server and controlled file-service API

Access layout:

- Floor 1, Administration & Finance — SW01 / `10.10.10.0/24`: WS01-WS03 and PRNT01
- Floor 2, Operations & Support — SW02 / `10.10.20.0/24`: WS04-WS06 and PRNT02
- Floor 3, Engineering — SW03 / `10.10.30.0/24`: WS07-WS09 and PRNT03
- Services — CORE01 services bridge / `10.10.40.0/24`: DC01 at `10.10.40.10` and FILE01 at `10.10.40.20`

CORE01 provides the `.1` gateway on each access network. RTR01 and CORE01 use
the `10.10.254.0/30` transit network. Endpoints retain their Containerlab
management interface and use `eth1` for office traffic. Complete addressing is
documented in `configs/IP_PLAN.md` and `configs/inventory.json`.
SW01-SW03 expose management addresses at `10.10.10.2`, `10.10.20.2`, and
`10.10.30.2` on their Linux bridges. This makes same-floor switch diagnostics
real while keeping Containerlab management `eth0` separate and preserving the
existing cross-floor forwarding policy.

CORE01 enforces default-deny forwarding between the three floor networks.
Same-floor endpoints retain local communication and assigned-printer access,
and each floor can reach its CORE01 gateway, DC01, and RTR01. Direct cross-floor
workstation and printer traffic is denied. Containerlab management traffic is
separate from this office policy and remains available to the centralized
backend for controlled monitoring and recovery.

WS01 and PRNT01 remain published through Lima for direct macOS access:

- `http://127.0.0.1:8081` - WS01
- `http://127.0.0.1:8080` - PRNT01
- `http://127.0.0.1:8082` - PRNT02
- `http://127.0.0.1:8083` - PRNT03

Other endpoint services listen on their office-network addresses inside the
lab but do not publish additional macOS ports.

Containerlab also creates management interfaces using a separate management network.

The management network must remain conceptually separate from the simulated office network.

## Important Containerlab Behavior

Do not use:

`docker restart`

on Containerlab nodes as the normal reload method.

During development, restarting a node directly with Docker caused Containerlab-created `eth1` interfaces to disappear.

When infrastructure behavior needs a clean restart, use:

```bash
containerlab destroy -t lab/netops.clab.yml
containerlab deploy -t lab/netops.clab.yml
```

inside the Lima VM.

## Current PRNT01 Implementation

Files:

- `containers/printer/printer_api.py`
- `containers/printer/index.html`

The Python service currently acts as both:

- printer API
- web server for the printer management page

The printer is intended to behave like a controllable network endpoint rather than a static mockup.

PRNT01 currently has real in-memory state and interactive behavior.

Workstations, printers, and network nodes run from the locally built
ARM64-compatible images `netops-workstation:phase3`, `netops-printer:phase3`,
and `netops-network:phase7`. Application files are copied into the endpoint
images at build time; the topology does not depend on absolute macOS source
bind paths.

The workstation offline fault lowers the endpoint's office-facing `eth1`
interface while leaving its Containerlab management interface available for
status inspection and recovery. Bringing a workstation online restores both
the office interface and its `10.10.0.0/16` route through the assigned access
gateway. Controlled ping binds to the validated
source's inventory office IP so it cannot silently fall back through the
management network. A workstation marked offline is therefore unreachable in
office-network connectivity tests.

## Printer Resource Model

Paper tray capacity:

`175 sheets`

Print jobs use a randomized page count:

`1-15 pages`

Each successfully printed page consumes one sheet of paper.

Toner usage is intentionally simplified rather than modeled with real-world cartridge yield.

Current toner rules:

- 1-5 pages = 1% toner
- 6-10 pages = 2% toner
- 11-15 pages = 3% toner

Toner should only decrease when a print job successfully completes.

A larger print job should therefore consume more toner than a smaller print job.

## Resource Warning Thresholds

Paper and toner have warning levels.

Current thresholds:

- 76-100% = NORMAL
- 51-75% = NOTICE
- 26-50% = LOW
- 1-25% = VERY LOW
- 0% = EMPTY

Low-resource warnings should not automatically mean the printer is broken.

A printer can still be READY while paper or toner is getting low.

Zero paper or zero toner should place the printer into an attention/error condition.

## Print Queue Model

Print jobs have unique job IDs beginning around:

`1001`

Each job currently includes:

- job ID
- sending device
- page count
- job state
- internal toner requirement

The visible queue should not show the internal toner requirement.

Example visible queue entry:

`Job #1004 - WS01 - 12 pages - QUEUED`

Each workstation submits jobs using its own configured identity. Printers
accept only the three workstations assigned to their access network.

## Print Job Behavior

When a user adds a print job:

- the page count is randomly selected from 1 to 15 pages
- the job is given a unique job ID
- the source device is the submitting workstation
- the job is added to the queue if the printer is online

When a print job successfully completes:

- the job is removed from the queue
- paper decreases by the exact number of printed pages
- toner decreases according to the page-count toner rules
- the printer resource levels are recalculated
- the interface shows a successful completion event

PRNT01 processes queued jobs automatically after a short delay. The delay keeps
the queued job visible long enough to observe while avoiding an unrealistic
manual Complete Print Job control. Automatic processing pauses when the printer
is offline or a resource failure occurs and resumes after the condition is
repaired.

## Offline Behavior

If PRNT01 is offline, a new print job should not be accepted.

The interface should show an explicit error such as:

`PRINT FAILED: PRNT01 is offline. Job was not added to the queue.`

This is different from a resource failure.

An offline printer should reject the incoming job rather than silently queue it.

## Resource Failure Behavior

If the printer is online, jobs may be added to the queue even if the printer later cannot complete them.

If a queued job requires more paper than remains in the tray:

- the job should fail during the print attempt
- the printer should enter an attention state
- the job should remain in the queue
- the interface should show a clear failure message
- the user should be able to refill paper and retry

If a queued job requires more toner than remains:

- the job should fail during the print attempt
- the printer should enter an attention state
- the job should remain available for retry
- the interface should show a clear failure message
- the user should be able to replace toner and retry

Failed jobs should not simply disappear.

## Printer Recovery Behavior

Current lab/testing actions include:

- Set Offline
- Set Ready
- Add Print Job
- Complete Print Job
- Empty Paper
- Refill Paper
- Empty Toner
- Refill Toner

The empty/refill controls are intentional fault-injection and recovery controls for the lab.

Buttons such as `Use Toner` should not exist.

Resource use should happen naturally through printer activity.

## Printer Queue Interface

The main printer page should not continuously grow vertically as jobs are added.

The queue uses a collapsible/dropdown-style interface.

The queue panel should:

- remain collapsed unless opened
- show the number of queued jobs
- have a maximum height
- scroll internally if many jobs exist
- avoid pushing the printer controls downward

Printer controls should remain in a consistent location.

Visible queue entries should show:

- job number
- source device
- page count
- job state

Do not show per-job toner percentage in the visible queue.

## Printer Monitoring Direction

The current PRNT01 simulation is an early example of the broader monitoring direction for the lab.

Useful monitoring concepts include:

- device availability
- service availability
- resource warning levels
- failure states
- alert conditions
- recovery events
- queue state
- incident history

The printer should eventually feed its state into the larger NetOps Lab dashboard rather than existing only as a standalone management page.

## Current Office Topology

The deployed office baseline includes:

- router/firewall
- core switch
- multiple access switches
- 9 workstations
- 3 printers
- routed access networks

A likely access-layer layout is:

### Access Switch 1

- 3 workstations
- 1 printer

### Access Switch 2

- 3 workstations
- 1 printer

### Access Switch 3

- 3 workstations
- 1 printer

The access switches and DC01 services segment connect to CORE01, and CORE01
connects to RTR01. Additional servers and VLAN tagging remain future work.

## Planned Network Functionality

Future networking features may include:

- VLANs
- routing
- switching
- DNS
- DHCP concepts
- interface state
- ARP tables
- routing tables
- network reachability
- simulated link failures
- disconnect/reconnect behavior
- controlled troubleshooting scenarios

Possible user actions may include:

- ping
- traceroute
- DNS queries
- viewing interfaces
- viewing routes
- viewing ARP information
- checking service health
- disabling and restoring simulated connections

## Interactive Frontend

The primary frontend is implemented under `frontend/` as a lightweight
vanilla HTML, CSS, and JavaScript operations console. It is served locally on
port 8090 and uses only the centralized API on port 8000 for inventory, live
state, device actions, print submission, and controlled diagnostics. It
refreshes one combined overview/device response every five seconds without
reloading the page.

The primary navigation includes:

- Dashboard
- Network
- Systems
- Active Directory
- Tickets
- Automation
- Architecture

Dashboard, Network, Systems, Active Directory, and Architecture are live
implemented pages. Tickets and Automation are clearly marked Planned Phase and
do not display fabricated data.

Devices are clickable in the topology and Systems tables.

Selecting a device should expose useful live information and safe management or troubleshooting actions.

Examples:

- click a workstation and inspect its status
- click a printer and inspect queue/resources
- click a switch and inspect connected devices
- run ping or traceroute
- view interface information
- inspect DNS behavior
- create a controlled fault
- troubleshoot the fault
- restore service

Device drawers preserve selection during refresh and show only telemetry the
backend actually provides. Printer and workstation controls call allowlisted
central backend routes; the browser never invokes Docker or endpoint mutation
routes directly. Phase 6 provides controlled ping, reachability, traceroute,
and Containerlab-name DNS checks between inventory devices, plus read-only
route and neighbor information. The backend constructs fixed argument lists
for each diagnostic and accepts neither arbitrary targets nor command text.

The frontend is a control and visualization layer over the actual lab.

It should not be a fake dashboard where every value is hardcoded.

## Planned Backend

The current endpoint services use reusable, testable Python state models. A
shared inventory loader resolves each node's identity, address, access switch,
printer assignment, and permitted print sources from `configs/inventory.json`.
Containerlab supplies only `DEVICE_NAME` to endpoints, avoiding duplicated
configuration. Printer state and workstation online/offline state remain
in-memory and reset when the containers are recreated.

The HTTP layer exposes explicit POST operations for print submission and fault
controls. Legacy printer GET routes remain available so the working PRNT01
behavior and existing bookmarks/scripts are not broken. Workstations submit
jobs to their assigned printer over the office-network interface using their
inventory identity; printers validate that identity against their assigned
three-workstation group.

The Phase 4 centralized backend is implemented with FastAPI under `backend/`.
It runs as a process inside the Lima VM on port 8000, sitting between the
future primary frontend and the infrastructure lab. It reads configuration
from `configs/inventory.json`, discovers current Containerlab management
addresses through read-only Docker inspection, and queries live printer and
workstation APIs without confusing management addresses with office IPs.

The centralized backend:

- query live infrastructure state
- expose safe API endpoints
- trigger controlled troubleshooting actions
- manage simulated device behavior
- collect health information
- support monitoring
- support automation
- prevent unrestricted shell access
- support a safe public portfolio demo

Controlled ping accepts only two current inventory hostnames. The backend
constructs a fixed `docker exec` argument list that runs one ping from the
validated source container to the destination's inventory office IP. It never
accepts command text or arbitrary IP addresses and never invokes a shell.

Infrastructure fault injection is available for RTR01, CORE01, and SW01-SW03.
The backend uses fixed, allowlisted `docker exec` argument lists to change only
the known office interfaces or Linux bridge; it does not stop containers or
accept command text. Disabling an access switch removes connectivity for its
attached endpoints. Disabling CORE01 removes routed connectivity while each
access segment retains local switching. Disabling RTR01 removes upstream
connectivity while internal office routing remains available. The frontend
reports direct device state separately from dependency impact and exposes a
restore action for every supported fault.
Access-switch recovery enforces upstream ordering: SW01-SW03 restoration is
rejected with a structured error while CORE01 is offline, directing the
operator to restore CORE01 first. This prevents a local interface operation
from being presented as full connectivity recovery.

Active printer resource faults are returned in the lab overview as structured
alerts. The dashboard lists the affected printer and exact reason, and both the
alert and topology device open live device details and recovery controls.
Printer alerts and dependency impacts open compact device lists in the frontend;
individual device details retain a return path to the originating list.

The centralized backend also keeps a lightweight in-memory feed of up to 50
recent endpoint, infrastructure, printer-health, and connectivity events. Each
event includes a UTC timestamp, severity, device, event type, and message.
Infrastructure events include affected downstream devices for both fault and
recovery transitions; a successful test following a failed source/destination
test records connectivity restoration. The dashboard displays the newest 15
events in a fixed-height scrollable list. This history is intentionally
ephemeral and resets whenever the backend process restarts.

Network-device status uses the operational state of its known office-network
interfaces and is labeled with `status_source: linux_interface_state`.
Container availability is checked separately. Endpoint status comes from each
live device service. This distinction avoids presenting a running container as
a healthy office-network device.

The public-facing version must not expose arbitrary shell execution.

## Systems Administration Direction

The project should demonstrate more than basic networking.

Future systems administration components may include:

- Windows Server
- Domain Controller
- Active Directory
- users and groups
- DNS
- Group Policy
- file shares
- permissions
- account provisioning
- password resets
- account lockouts
- endpoint configuration
- service failures
- patching concepts
- server health
- monitoring
- administrative troubleshooting

## Active Directory Direction

Phase 8 implements DC01 as an ARM64-native Samba Active Directory Domain
Controller. This is a real AD-compatible LDAP, Kerberos, DNS, account, group,
SYSVOL, and password-policy service, but it is explicitly not Windows Server.
Native Windows Server is impractical on the current M4 host without a separate
licensed or emulated virtualization layer.

The lab-only domain is `netopslab.test` (`NETOPSLAB` NetBIOS) and DC01 uses
`10.10.40.10`. The directory contains a small `OU=NetOpsLab` hierarchy with
Users, Workstations, Laptops, Servers, Groups, and Admins OUs. Fifteen active
fictional employees map one-to-one to WS01-WS09 and LTP01-LTP06. The six
laptop users are company-issued remote users spanning HR, procurement,
helpdesk, operations, and engineering roles. Three disabled former-employee
accounts remain unassigned for realistic offboarding and audit scenarios.

Employees is the broad workforce group. Finance, Operations, and Engineering
cover floor-aligned resources; HR, Procurement, and Helpdesk provide
role-specific access; Remote-Users covers remote access; and
Monitoring-Readers provides read-only monitoring access. The everyday
`avery.admin` account is not privileged. The separate `avery.admin-adm`
identity receives administrative access through IT-Admins, which is nested in
Domain Admins. `svc_monitor` is a non-interactive service identity with only
Monitoring-Readers membership.

A compact summary and horizontal object tabs separate Users, Unassigned,
Remote Users, Account Attention, Computers, Security Groups, and Disabled
accounts without a persistent sidebar. Group members appear only after an
operator selects a group. The Account Attention view deliberately begins with
Alex Kim locked and Sam Patel requiring a password change so unlock and reset
workflows can be practiced. These states and the displayed password policy are
read from Samba rather than supplied as frontend-only values.

The backend exposes only allowlisted health, user lookup, enable/disable,
password reset, unlock, and group-membership operations. It accepts no command
text, LDAP filters, or arbitrary directory identities. Temporary reset
passwords are generated at runtime, returned once, and not logged or committed.
Directory health transitions and controlled account, membership, assignment,
and provisioning operations are recorded in the central recent-event feed.

The Linux workstation and laptop simulations remain non-domain-joined. Their inventory
metadata links them conceptually to real AD computer objects and assigned users
without claiming a fake live join. Future Windows clients will use DC01 as DNS
and can join the domain to validate actual Group Policy application.

The six current laptops are part of the repository baseline topology so the
24-device environment is reproducible after a clean deployment. The Network
page also supports additional controlled endpoint expansion. A
non-disruptive draft selects a workstation (`WS##`) or laptop (`LTP##`) and one
of the three known floors, proposes the next type-specific hostname and unused
endpoint address, and derives the access switch and printer. The device is
created unassigned. A separate
Apply action persists runtime extensions in the Lima-local writable
`$HOME/netops-lab-state/lab_extensions.json`, creates an allowlisted AD computer
object, and writes `$HOME/netops-lab-state/netops.generated.clab.yml` from only
the marked dynamic sections of the base Containerlab topology. It then rebuilds
the endpoint image and redeploys the lab. The repository remains the declarative
baseline instead of receiving runtime GUI writes. The UI warns about this
interruption before applying. Access
switches discover only office-facing `eth1` and higher ports; Containerlab
management `eth0` remains outside the office bridge. Employee creation is a
separate Active Directory workflow that lists workstations not held by an
assigned account, creates the controlled Samba identity, applies the appropriate
department group, and persists the new assignment. This allows an offboarded
employee's existing workstation to be reassigned without adding another device.
An explicit directory action releases an employee's device assignment without
silently disabling the account. Only dynamically provisioned `WS##` and
`LTP##` endpoints can be removed; baseline WS01-WS09 remain protected, and
removal is rejected until the assigned employee has been unassigned. Successful
removal regenerates and redeploys the topology and cleans up the corresponding
AD computer object.
New employee accounts may be created without an endpoint and always receive the
baseline `Employees` group. Enabled users without a workstation appear in the
Unassigned Members directory view. Assigning one of those users to an available
endpoint derives the floor and department from the endpoint network and applies
the matching Finance, Operations, or Engineering group. Unassignment removes
that department group while retaining `Employees`. Background lab polling does
not rebuild the Active Directory page, preserving table scroll position and
the operator's current selection.

Samba domain data, DNS, and SYSVOL persist in the Lima-local
`$HOME/netops-lab-state/dc01` directory. DC01 alone runs non-privileged with
NET_ADMIN, NET_RAW, and the explicitly approved SYS_ADMIN capability required
to maintain Windows-compatible SYSVOL ACLs. This local-lab security exception
must be reconsidered before public hosting.

## File Server Direction

Phase 9 implements FILE01 at `10.10.40.20` on the existing services network.
CORE01 uses a small Linux services bridge to attach both DC01 and FILE01 while
retaining the existing `10.10.40.1` gateway and floor-to-services policy.
FILE01 uses an ARM64 Debian/Samba container, persists share contents under the
Lima-local `$HOME/netops-lab-state/file01/shares` directory, and exports Public,
HR, Finance, Engineering, and IT-Tools through a real `smbd` process.

The safe backend authorization layer accepts only a known AD user, that user's
assigned workstation or laptop, one configured share, and a read/write
operation. It evaluates live DC01 group membership: Employees controls Public;
HR, Finance, and Engineering control their matching shares; Helpdesk and
IT-Admins can read IT-Tools; and only IT-Admins can write IT-Tools. This is a
controlled authorization model rather than a literal domain-authenticated SMB
mount from every Linux endpoint. The Samba service and exports are real, while
DC01 remains the source of truth for authorization decisions.

Phase 9 supports constrained fault injection for FILE01 offline, SMB stopped,
one disabled share, and one read-only share. Device outages affect aggregate
online/offline counts; SMB and share problems leave FILE01 online but make file
services unhealthy. Access denials and state transitions reuse the central
event feed. The Systems page, topology, device drawer, share inventory, and
controlled access checker expose this state without arbitrary paths or command
execution.

Phase 10 adds contextual remediation controls to the existing FILE01 drawer.
Only active failures surface a repair: an offline server can be brought online,
a stopped SMB service can be restarted, a disabled known share can be
re-enabled, and a read-only share can have expected write access restored.
The same drawer exposes controlled fault actions while healthy: FILE01 can be
set offline, SMB can be stopped, and each configured share can be disabled.
Restoring FILE01 also reinstalls its `10.10.0.0/16` return route through
`10.10.40.1`, because Linux removes that static route when `eth1` is lowered.
The backend exposes constrained recovery routes under `/api/fileserver/actions`
and `/api/fileserver/shares/{share}`. Results include the action, target,
previous/new state, whether anything changed, a message, and resolution time.
The supported routes are `POST /api/fileserver/actions/online`,
`POST /api/fileserver/actions/restart-service`,
`POST /api/fileserver/shares/{share}/enable`, and
`POST /api/fileserver/shares/{share}/restore-write`. Existing
`POST /api/fileserver/shares/{share}/memberships` operations remain the only
way to restore group-derived user access.
The existing event feed records successful state-changing recovery actions,
and normal lab refreshes update device counts, topology, Systems, service
attention, and FILE01 detail state.

Access recovery continues to use the Phase 9.5 user → AD group → FILE01 share
model. A membership-related denial now links to the existing Manage Access
drawer; no direct user-to-share permission state exists. Phase 10 does not add
permission-refresh or DNS repair controls because Phase 9 introduced no stale
permission cache or FILE01 DNS fault state.

Phase 9.5 adds Manage Access to each FILE01 share without introducing direct
share-user assignments. The drawer derives effective users from current DC01
memberships, shows the read or read/write level contributed by each configured
access group, and lists eligible users who do not yet receive access. Add and
Remove actions call a FILE01-scoped backend route that permits only the groups
configured for that share, then refreshes the FILE01 and Active Directory views.
The authoritative relationship remains user → AD security group → share
permission, and the existing event feed records each membership change.

## Ticketing and IT Operations Direction

Phase 12 implements a lightweight persistent incident workflow on the Tickets
page. An operator selects Easy, Medium, or Hard and generates a compatible
scenario that applies existing workstation, printer, FILE01, share, or Active
Directory membership faults. Easy scenarios require one direct recovery,
Medium scenarios require investigation across a service or access path, and
Hard scenarios combine two related conditions. Ticket responses show only the
reported symptom; root causes and verification checks remain in the Lima-local
`$HOME/netops-lab-state/tickets.json` record.

Tickets use sequential `INC-####` identifiers and move from Open to In Progress
to Resolved. Resolution queries the actual current lab state and is rejected
while any expected recovery condition remains active. Resolved tickets retain
the technician, notes, timestamps, and elapsed resolution time. Monitoring
continues to answer what is broken now, while Tickets retain the work and
resolution history. Scenario generation uses only existing allowlisted actions
and avoids resources already held by another unresolved generated ticket.
The generator can create one to five work items per request. In addition to
incidents, it issues state-verified service requests for access grants, endpoint
provisioning, employee onboarding, and employee offboarding. These requests do
not perform the requested administrative work automatically; the operator uses
the existing Network and Active Directory controls, then ticket verification
confirms the requested live end state.

## Phase 11 Monitoring and Alerts

Phase 11 preserves the existing live health cards, attention drawers, device
status evaluation, event feed, fault injection, and remediation workflows. It
adds a lightweight in-memory alert lifecycle derived from those same live
device, FILE01, printer, and Active Directory states. No separate source of
truth or hardcoded alert feed is used.

Each active condition has one stable alert record with a source, source type,
severity, summary, detected time, status, and related device, account, service,
or share. Repeated polling updates that record instead of creating duplicates.
When the underlying condition recovers, the alert automatically becomes
resolved and receives a resolution timestamp. A later recurrence creates a new
record while the earlier resolution remains in the bounded history. Like the
existing recent-event feed, this history is intentionally ephemeral and resets
when the backend restarts.

Critical severity covers required infrastructure servers and routing devices
that are unavailable. Warning covers endpoint or printer outages, upstream
connectivity impacts, stopped SMB, disabled shares, and locked, disabled, or
password-expired directory accounts. Notice is available for lower-severity
conditions such as a read-only share. The combined operational-health summary
counts active critical, warning, notice, and account-attention alerts.

The Dashboard continues to use its established compact layout and shows one
additional operational alert strip only when active alerts exist. The
Monitoring intentionally shows only active operational alerts, leaving
historical incident ownership to the future ticketing workflow. Alert rows
link back to existing device or directory details and recovery controls. `GET
/api/monitoring` exposes the same read-only derived alert snapshot used by the
overview response.

The project may eventually include an IT support or operations workflow.

Possible future features include:

- users submitting tickets
- printer issues generating tickets
- endpoint outages generating alerts
- administrator troubleshooting workflows
- resolving incidents
- documenting fixes
- linking infrastructure state to ticket status
- tracking recurring failures

A lightweight ITSM platform such as GLPI, Zammad, or another appropriate tool may be evaluated later.

Do not add a heavy ticketing platform until it meaningfully improves the project.

## Automation Direction

Automation should eventually be part of the lab.

Possible examples include:

- service health checks
- automated device-status collection
- infrastructure validation
- user provisioning
- configuration checks
- remediation scripts
- alert generation
- recurring maintenance tasks
- automated incident responses

Automation should be tied to meaningful infrastructure behavior rather than added only for appearance.

## Monitoring Direction

The lab should eventually include monitoring concepts such as:

- endpoint availability
- server availability
- service availability
- printer state
- resource warnings
- network health
- interface state
- alert conditions
- failure history
- recovery history

Monitoring should eventually feed information into the main dashboard.

## Troubleshooting Direction

The project should intentionally include faults that can be diagnosed and repaired.

Examples may include:

- printer offline
- empty printer resources
- failed print jobs
- DNS failure
- unreachable workstation
- disconnected interface
- failed service
- incorrect route
- permissions issue
- locked user account
- unavailable file share

Troubleshooting scenarios should expose enough information for the user to reason through the problem.

The goal is to demonstrate operational thinking rather than only pressing a repair button.

## Architecture Page Direction

The project may eventually include an Architecture section that explains:

- physical/logical topology
- network segmentation
- services
- backend architecture
- frontend architecture
- monitoring
- automation
- security decisions
- deployment model

This should make the project understandable to both recruiters and technical reviewers.

## Recruiter Demo Goal

The final project should make it obvious that the builder understands:

- infrastructure architecture
- networking
- system administration
- troubleshooting
- failure handling
- automation
- monitoring
- APIs
- frontend/backend interaction
- operational thinking

The project should be visually clear enough for a recruiter to understand while technically deep enough for an engineer or hiring manager to explore.

The experience should feel interactive and practical rather than academic or purely decorative.

## Public Demo Safety

The eventual public demo should be safe for external users.

Do not expose:

- unrestricted shells
- arbitrary command execution
- real credentials
- private keys
- host-level administrative access
- dangerous infrastructure controls

Interactive actions should be constrained to controlled backend functions.

The public user should be able to explore and troubleshoot the simulated environment without being able to abuse the underlying host.

## Portability

The topology uses locally built network and endpoint images rather than
absolute macOS source bind paths. This removes the previous checkout-path
dependency and avoids downloading packages during every deployment.

Each development computer must build the local endpoint images before its first
deployment and after endpoint source changes.

Each computer provisions its own persistent DC01 state on first deployment.
`scripts/lab.sh` creates the Lima-local state directory automatically; that
state is intentionally not committed to Git.

The repository itself is still mounted into Lima at a machine-specific macOS
path, so the developer must change to the correct checkout directory before
running the repository scripts.

Because this project will be developed from multiple computers, portability is important long term.

## Git and Multi-Computer Development

GitHub is the shared source of truth.

Development should support moving between:

- work Mac
- home computer

Changes should be committed and pushed regularly so another machine can pull the current state.

Machine-specific runtime artifacts should not be committed.

## Current Priorities

The current focus is establishing the core simulated network and endpoint behavior.

PRNT01 is the first interactive endpoint prototype.

The next phases should continue to prioritize real infrastructure behavior before polishing the entire frontend.

When choosing what to build next, prioritize:

1. Real infrastructure behavior
2. Interactivity
3. Troubleshooting scenarios
4. Clear visual feedback
5. Low resource usage
6. Recruiter-friendly demonstrations
7. Beginner-readable implementation
8. Portability
9. Cloud deployment later

The project should demonstrate genuine systems and network administration concepts rather than becoming primarily a frontend design exercise.

## Standing Design Principle

When there is a choice between:

- making something only look realistic

and

- making the underlying infrastructure actually behave realistically

prefer the real behavior when it can be implemented safely and reasonably.

The frontend should reflect the lab.

The lab should not exist only to support fake frontend values.

Keep this document updated as major architecture and behavior decisions are made.
