# NetOps Lab IP Plan

This is the addressing baseline for the deployed small-office topology. The
services subnet is reserved for API01 and later infrastructure services but is
not connected during Phase 2.

| Network | CIDR | Gateway | Purpose |
| --- | --- | --- | --- |
| Access 1 | `10.10.10.0/24` | `10.10.10.1` | SW01, WS01-WS03, PRNT01 |
| Access 2 | `10.10.20.0/24` | `10.10.20.1` | SW02, WS04-WS06, PRNT02 |
| Access 3 | `10.10.30.0/24` | `10.10.30.1` | SW03, WS07-WS09, PRNT03 |
| Services | `10.10.40.0/24` | `10.10.40.1` | API01 and future infrastructure services |
| Core transit | `10.10.254.0/30` | N/A | RTR01 (`.1`) to CORE01 (`.2`) |

## Device addresses

| Device | Office-network address | Connection |
| --- | --- | --- |
| RTR01 | `10.10.254.1/30` | CORE01 |
| CORE01 | `10.10.254.2/30` | RTR01 |
| CORE01 | `10.10.10.1/24` | SW01 gateway |
| CORE01 | `10.10.20.1/24` | SW02 gateway |
| CORE01 | `10.10.30.1/24` | SW03 gateway |
| WS01 | `10.10.10.11/24` | SW01 |
| WS02 | `10.10.10.12/24` | SW01 |
| WS03 | `10.10.10.13/24` | SW01 |
| PRNT01 | `10.10.10.21/24` | SW01 |
| WS04 | `10.10.20.11/24` | SW02 |
| WS05 | `10.10.20.12/24` | SW02 |
| WS06 | `10.10.20.13/24` | SW02 |
| PRNT02 | `10.10.20.21/24` | SW02 |
| WS07 | `10.10.30.11/24` | SW03 |
| WS08 | `10.10.30.12/24` | SW03 |
| WS09 | `10.10.30.13/24` | SW03 |
| PRNT03 | `10.10.30.21/24` | SW03 |

## Endpoint allocation

Each access network follows the same pattern:

- `.1` - CORE01 routed gateway
- `.11` through `.13` - workstations
- `.21` - printer

Containerlab management addresses are dynamically assigned on its separate
management network. They are not part of this office-network IP plan.
