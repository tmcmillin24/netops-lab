# NetOps Lab IP Plan

This is the addressing baseline for the deployed small-office topology. The
services subnet hosts DC01 and reserves space for later infrastructure services.

| Network | CIDR | Gateway | Purpose |
| --- | --- | --- | --- |
| Access 1 | `10.10.10.0/24` | `10.10.10.1` | Floor 1 — Administration & Finance; SW01, WS01-WS03, PRNT01 |
| Access 2 | `10.10.20.0/24` | `10.10.20.1` | Floor 2 — Operations & Support; SW02, WS04-WS06, PRNT02 |
| Access 3 | `10.10.30.0/24` | `10.10.30.1` | Floor 3 — Engineering; SW03, WS07-WS09, PRNT03 |
| Services | `10.10.40.0/24` | `10.10.40.1` | DC01, FILE01, and future infrastructure services |
| Core transit | `10.10.254.0/30` | N/A | RTR01 (`.1`) to CORE01 (`.2`) |

## Device addresses

| Device | Office-network address | Connection |
| --- | --- | --- |
| RTR01 | `10.10.254.1/30` | CORE01 |
| CORE01 | `10.10.254.2/30` | RTR01 |
| CORE01 | `10.10.10.1/24` | SW01 gateway |
| CORE01 | `10.10.20.1/24` | SW02 gateway |
| CORE01 | `10.10.30.1/24` | SW03 gateway |
| SW01 | `10.10.10.2/24` | Floor 1 switch management |
| SW02 | `10.10.20.2/24` | Floor 2 switch management |
| SW03 | `10.10.30.2/24` | Floor 3 switch management |
| CORE01 | `10.10.40.1/24` | Services gateway |
| DC01 | `10.10.40.10/24` | CORE01; Samba AD DS and DNS |
| FILE01 | `10.10.40.20/24` | CORE01 services bridge; Samba file services |
| WS01 | `10.10.10.11/24` | SW01 |
| WS02 | `10.10.10.12/24` | SW01 |
| WS03 | `10.10.10.13/24` | SW01 |
| LTP01 | `10.10.10.14/24` | SW01 — company-issued remote laptop |
| LTP02 | `10.10.10.15/24` | SW01 — company-issued remote laptop |
| PRNT01 | `10.10.10.21/24` | SW01 |
| WS04 | `10.10.20.11/24` | SW02 |
| WS05 | `10.10.20.12/24` | SW02 |
| WS06 | `10.10.20.13/24` | SW02 |
| LTP03 | `10.10.20.14/24` | SW02 — company-issued remote laptop |
| LTP04 | `10.10.20.15/24` | SW02 — company-issued remote laptop |
| PRNT02 | `10.10.20.21/24` | SW02 |
| WS07 | `10.10.30.11/24` | SW03 |
| WS08 | `10.10.30.12/24` | SW03 |
| WS09 | `10.10.30.13/24` | SW03 |
| LTP05 | `10.10.30.14/24` | SW03 — company-issued remote laptop |
| LTP06 | `10.10.30.15/24` | SW03 — company-issued remote laptop |
| PRNT03 | `10.10.30.21/24` | SW03 |

## Endpoint allocation

Each access network follows the same pattern:

- `.1` - CORE01 routed gateway
- `.11` through `.13` - workstations
- `.21` - printer

Containerlab management addresses are dynamically assigned on its separate
management network. They are not part of this office-network IP plan.

## Segmentation policy

CORE01 applies a default-deny forwarding policy between office networks.
Endpoints can communicate within their own floor, reach their local CORE01
gateway, use their assigned same-floor printer, reach DC01, and reach RTR01. Direct traffic
between the three floor subnets is denied. Containerlab management traffic is
not carried through these office interfaces and remains available to the
central backend for controlled monitoring and recovery.

DC01 is authoritative for the lab-only `netopslab.test` domain. Future real
domain clients will use `10.10.40.10` as DNS. The current Linux workstation
simulations have corresponding AD computer objects but are explicitly not
presented as domain joined.
