# Device notes for common GNS3 images

Prompts are defaults on a fresh image; hostnames change them. Always confirm with
`console read mode="last_page"` before using a prompt as `wait_pattern`.

| Image | First login | Prompts (regex for `wait_pattern`) | Config mode | Netmiko `device_type` |
|---|---|---|---|---|
| Cisco IOSv / CSR1000v / Catalyst 8000V | none (IOSv may ask "initial configuration dialog?" - answer `no`) | `Router>` user, `Router#` enable -> `[>#]\s*$` | `enable`, `configure terminal`, `end`, `write memory` | `cisco_ios` (`cisco_xe` for IOS-XE) |
| Cisco IOSvL2 / IOU L2 | none | `Switch>` / `Switch#` | as IOS | `cisco_ios` |
| Cisco NX-OSv 9000 | `admin`, set password on first boot | `switch#` | `configure terminal` | `cisco_nxos` |
| Cisco IOS XRv / XRv 9000 | create root user on first boot | `RP/0/RP0/CPU0:ios#` | `configure`, `commit`, `end` | `cisco_xr` |
| Arista vEOS | `admin`, no password | `switch>` / `localhost>` (image dependent), `#` when enabled | `enable`, `configure terminal` | `arista_eos` |
| MikroTik CHR | `admin`, empty password, then set a new one | `\[admin@MikroTik\] >` | commands are paths: `/ip address add ...` | `mikrotik_routeros` |
| FortiGate (7.x) | `admin`, empty password, then set a new one | `FortiGate-VM64 #` | `config system interface` ... `next` / `end` | `fortinet` |
| Cumulus VX | `cumulus` / `cumulus` (forced change) | `cumulus@cumulus:~\$` | `nv set ...`, `nv config apply` | `linux` |
| Alpine / Debian / Ubuntu Cloud Guest | image or cloud-init credentials | `login:`, `\$ $`, `# $` | shell | `linux` |
| VPCS | none | `PC1>` | `ip 10.0.0.10/24 10.0.0.1`, `save` | - (console only) |

## Console habits that save time

- Wake a console with `send` `"\n"`, then `read` `last_page`.
- Boot to login: `send_and_wait` without `command`, `wait_pattern="login:"`, `timeout` 120-300 s.
- Long `show` output: `handle_pagination: True` (sends space at `--More--`), or disable paging first
  (`terminal length 0` on IOS/EOS/NX-OS, `config system console` / `set output standard` on FortiOS).
- Keep pasted lines short (under ~80 characters) on FortiOS and older IOS consoles.
- A stuck CLI: `keystroke` `ctrl_c`, then `enter`.

## Enabling SSH (minimal)

- **IOS / IOS-XE**: `hostname R1`, `ip domain-name lab.local`, `crypto key generate rsa modulus 2048`,
  `username admin privilege 15 secret <pw>`, `line vty 0 4` -> `login local`, `transport input ssh`.
- **Arista EOS**: `username admin secret <pw>`; SSH is on by default once a management IP is set.
- **MikroTik**: `/ip service enable ssh`, `/user set admin password=<pw>`.
- **FortiOS**: `config system interface` -> `edit port1` -> `set allowaccess ping ssh https` -> `end`.
- **Linux**: `apk add openssh` (Alpine) or `apt install openssh-server`, then enable the service.

The server's `ssh_setup` prompt walks through these per device type.
