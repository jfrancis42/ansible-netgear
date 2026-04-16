# ordo_artificum.netgear — Ansible Collection for Netgear Smart Managed Plus Switches

Manage Netgear Smart Managed Plus switches entirely from Ansible — no CLI,
no SSH, no REST API required.  The collection reverse-engineers the switch's
HTTP web UI and exposes all configuration as idempotent Ansible modules.

> **Early release — lightly tested.**  This collection is new.  All modules
> have been exercised against a single GS105Ev2 (firmware V1.6.0.24), but
> coverage on other models and firmware versions is unknown.  Please open an
> issue if something doesn't work on your hardware.

Developed and tested against the **Netgear GS105Ev2** (firmware V1.6.0.24).
Other Netgear Smart Managed Plus switches that share the same HTTP web UI
interface may be compatible.

---

## Requirements

- Ansible 2.9 or later
- Python `requests` library on the **controller** node

---

## Installation

```bash
ansible-galaxy collection install ordo_artificum.netgear
```

---

## Modules

| Module | Description |
|--------|-------------|
| `facts` | Gather all switch state as Ansible facts under the `netgear` key |
| `system` | Configure switch name, IP settings, and admin password |
| `port` | Set speed/duplex and flow control on one or more ports |
| `mirror` | Enable or disable port mirroring (SPAN) |
| `igmp` | Configure IGMP snooping, loop detection, and broadcast filtering |
| `qos` | Set the global QoS scheduling mode |
| `bandwidth` | Set ingress/egress rate limits on one or more ports |
| `vlan` | Manage 802.1Q VLANs and port PVIDs |
| `maintenance` | Reboot, factory reset, or run cable diagnostics |

All modules:
- Run on the Ansible controller (`connection: local`)
- Support `--check` mode
- Are idempotent — running twice with the same parameters produces `changed=false`

## Connection parameters

Every module accepts:

| Parameter  | Required | Default | Description |
|------------|----------|---------|-------------|
| `host`     | yes      |         | Switch IP or hostname |
| `password` | yes      |         | Login password |
| `timeout`  | no       | `10.0`  | HTTP request timeout (seconds) |

The GS105Ev2 does not use a username — only a password is required.

## Quick example

```yaml
- name: Configure Netgear switch
  hosts: switches
  connection: local
  gather_facts: false
  tasks:

    - name: Gather switch facts
      ordo_artificum.netgear.facts:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"

    - name: Full L2 hardening
      ordo_artificum.netgear.igmp:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        igmp_enabled: true
        validate_ip_header: true
        block_unknown_multicast: true
        loop_detection: true
        broadcast_filter: true

    - name: Create VLAN 10 (port 5 trunk, ports 1-4 access)
      ordo_artificum.netgear.vlan:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        vlan_id: 10
        tagged_ports: [5]
        untagged_ports: [1, 2, 3, 4]
        pvid: 10
        state: present
```

For full documentation and workflow examples see the
[repository README](https://github.com/jfrancis42/ansible-netgear).

## Known firmware limitations

- **Single-session limit**: the switch allows only one active web session at
  a time.  The SDK always logs out after each module run to free the slot.
- **Power saving**: `set_power_saving()` is accepted by the firmware but does
  not persist across a GET — the hardware overrides it.
- **No backup/restore API**: the GS105Ev2 firmware does not expose a
  configuration backup/restore endpoint.
- **Port mirroring direction**: the hardware always mirrors both rx and tx;
  ingress-only or egress-only mirroring is not configurable.

## License

GNU General Public License v3.0.
