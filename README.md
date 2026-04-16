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

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [Inventory and connection setup](#inventory-and-connection-setup)
- [Modules](#modules)
  - [facts](#facts)
  - [system](#system)
  - [port](#port)
  - [mirror](#mirror)
  - [igmp](#igmp)
  - [qos](#qos)
  - [bandwidth](#bandwidth)
  - [vlan](#vlan)
  - [maintenance](#maintenance)
- [Common workflows](#common-workflows)
- [Return values and registered variables](#return-values-and-registered-variables)
- [Check mode](#check-mode)
- [License](#license)

---

## Requirements

- Ansible 2.9 or later
- Python `requests` library on the **controller** node

---

## Installation

```bash
ansible-galaxy collection install ordo_artificum.netgear
```

Or pin a specific version:

```bash
ansible-galaxy collection install ordo_artificum.netgear:==0.1.0
```

---

## Quick start

```yaml
- name: Configure Netgear switch
  hosts: switches
  connection: local          # modules run on the controller, not the switch
  gather_facts: false
  tasks:

    - name: Gather switch facts
      ordo_artificum.netgear.facts:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"

    - name: Show firmware version
      ansible.builtin.debug:
        msg: "Firmware: {{ netgear.config.firmware }}"

    - name: Ensure loop detection and broadcast filter are on
      ordo_artificum.netgear.igmp:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        loop_detection: true
        broadcast_filter: true
```

---

## Inventory and connection setup

Every module connects directly to the switch over HTTP from the Ansible
controller.  Set `connection: local` either in the play header or per
task, **or** set it globally in `ansible.cfg`:

```ini
# ansible.cfg
[defaults]
collections_path = /path/to/your/collections

[ssh_connection]
# not used — switches connect over HTTP, not SSH
```

A typical inventory for switches:

```ini
# inventory/hosts.ini
[switches]
core-switch  ansible_host=10.1.0.32

[switches:vars]
ansible_connection=local
netgear_password=yourpassword
```

Or in YAML:

```yaml
# inventory/hosts.yml
all:
  children:
    switches:
      vars:
        ansible_connection: local
        netgear_password: yourpassword
      hosts:
        core-switch:
          ansible_host: 10.1.0.32
        access-switch:
          ansible_host: 10.1.0.33
```

Store the password in an Ansible Vault file:

```bash
ansible-vault create group_vars/switches/vault.yml
# Add: netgear_password: yourpassword
```

---

## Modules

All modules share these common connection parameters:

| Parameter  | Required | Default | Description |
|------------|----------|---------|-------------|
| `host`     | yes      |         | Switch IP or hostname |
| `password` | yes      |         | Login password |
| `timeout`  | no       | `10.0`  | HTTP request timeout (seconds) |

> **Note:** The GS105Ev2 does not use a username for authentication —
> only a password is required.

---

### facts

Gathers all available switch state and registers it as Ansible facts
under the `netgear` key.  Use this to inspect the current state of the
switch or to make other tasks conditional on switch state.

If an individual subsystem read fails, its key contains
`{'_error': 'message'}` rather than failing the entire task.

```yaml
- name: Gather switch facts
  ordo_artificum.netgear.facts:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
  connection: local

# Facts are now available as netgear.*
- name: Print firmware
  ansible.builtin.debug:
    msg: "{{ netgear.config.firmware }}"

- name: Print all port states
  ansible.builtin.debug:
    msg: "Port {{ item.port }}: {{ item.speed_cfg }}, link {{ item.speed_act | default('down') }}"
  loop: "{{ netgear.ports }}"

- name: Check 802.1Q mode
  ansible.builtin.debug:
    msg: "802.1Q enabled: {{ netgear.vlan.dot1q_enabled }}"
```

**Fact keys returned under `netgear`:**

| Key | Description |
|-----|-------------|
| `system` | MAC address, IP, firmware (read-only snapshot) |
| `config` | Full config: name, model, serial, DHCP, IP, netmask, gateway, firmware |
| `ports` | List of per-port settings (enabled, speed_cfg, speed_act, fc_enabled) |
| `port_stats` | List of per-port byte counters and CRC errors |
| `rate_limits` | Per-port ingress/egress rate limits |
| `mirror` | Port mirroring configuration |
| `igmp` | IGMP snooping configuration |
| `loop_detection` | Loop detection enabled state (`true`/`false`) |
| `broadcast_filter` | Broadcast filter enabled state (`true`/`false`) |
| `qos_mode` | QoS scheduling mode (`port-based` or `802.1p/dscp`) |
| `vlan` | 802.1Q VLAN configuration (`dot1q_enabled`, `vlans`, `pvids`) |

---

### system

Configure the switch name, IP settings, and admin password.
Only parameters you specify are changed; everything else is left as-is.

```yaml
# Set switch name and static IP
- name: Set switch name and static IP
  ordo_artificum.netgear.system:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    name: lab-gs105-1
    ip: 10.1.0.32
    netmask: 255.255.254.0
    gateway: 10.1.0.1
    dhcp: false
  connection: local

# Enable DHCP
- name: Enable DHCP
  ordo_artificum.netgear.system:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    dhcp: true
  connection: local

# Change the admin password
- name: Rotate admin password
  ordo_artificum.netgear.system:
    host: "{{ ansible_host }}"
    password: "{{ current_password }}"
    new_password: "{{ new_password }}"
  connection: local
  no_log: true
```

> **Note:** Changing the IP address or enabling DHCP takes the switch off
> the address you connected to.  Subsequent tasks in the same play must
> target the new address.

> **Note:** Password changes always report `changed=true` — there is no
> way to check the current password without attempting to change it.

---

### port

Configure speed/duplex and flow control on one or more ports.
Only parameters you specify are changed; unspecified parameters are preserved.
Port numbers are 1-based.

**Speed choices:** `AUTO`, `DISABLE` (administratively shut down),
`M10H` (10M half), `M10F` (10M full), `M100H` (100M half), `M100F` (100M full).

> **Note:** The GS105Ev2 does not support forcing 1 Gbit/s.  Use `AUTO`
> and the hardware will negotiate to 1G when the link partner supports it.
> To administratively disable a port, use `speed: DISABLE`.

```yaml
# Enable ports 1-4 at auto speed with flow control
- name: Configure access ports
  ordo_artificum.netgear.port:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [1, 2, 3, 4]
    speed: AUTO
    flow_control: true
  connection: local

# Disable an unused port
- name: Shut down unused port
  ordo_artificum.netgear.port:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [3]
    speed: DISABLE
  connection: local

# Force port 2 to 100M full-duplex, no flow control
- name: Lock port speed
  ordo_artificum.netgear.port:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [2]
    speed: M100F
    flow_control: false
  connection: local
```

---

### mirror

Enable or disable port mirroring (SPAN).  All traffic from the source ports
is copied to the destination port for analysis.

> **Note:** The GS105Ev2 mirrors all traffic (rx+tx) on source ports.
> Ingress-only or egress-only mirroring is not supported by the hardware.

```yaml
# Mirror ports 1-3 to port 5 (capture device on port 5)
- name: Enable port mirroring
  ordo_artificum.netgear.mirror:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    dest_port: 5
    source_ports: [1, 2, 3]
    state: present
  connection: local

# Disable mirroring
- name: Disable port mirroring
  ordo_artificum.netgear.mirror:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    state: absent
  connection: local
```

---

### igmp

Configure IGMP snooping, loop detection, and broadcast filtering.
Any parameter left unset is preserved on the switch.  At least one
parameter must be specified.

```yaml
# Enable IGMP snooping
- name: Enable IGMP snooping
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    igmp_enabled: true
  connection: local

# Enable loop detection and broadcast filter
- name: Enable loop detection and broadcast filter
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    loop_detection: true
    broadcast_filter: true
  connection: local

# Full L2 hardening in one task
- name: Harden L2 settings
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    igmp_enabled: true
    validate_ip_header: true
    block_unknown_multicast: true
    loop_detection: true
    broadcast_filter: true
  connection: local

# Restrict IGMP snooping to VLAN 10, with static router port on port 5
- name: IGMP snooping for VLAN 10
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    igmp_enabled: true
    vlan_id: "10"
    static_router_port: "5"
  connection: local
```

---

### qos

Set the global QoS scheduling mode.

**Mode choices:** `port-based`, `802.1p/dscp`.

> **Note:** The GS105Ev2 does not support per-port priority configuration.
> Only the global mode can be changed.

```yaml
- name: Set QoS to port-based mode
  ordo_artificum.netgear.qos:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    mode: port-based
  connection: local

- name: Set QoS to 802.1p/DSCP mode
  ordo_artificum.netgear.qos:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    mode: 802.1p/dscp
  connection: local
```

---

### bandwidth

Set ingress and/or egress bandwidth limits on one or more ports.
Rate limits use named labels rather than raw kbps values.

**Rate labels:** `no-limit`, `512k`, `1m`, `2m`, `4m`, `8m`, `16m`,
`32m`, `64m`, `128m`, `256m`, `512m`.

```yaml
# Limit port 3 ingress to 1 Mbps, egress to 512 Kbps
- name: Rate-limit guest port
  ordo_artificum.netgear.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [3]
    ingress: 1m
    egress: 512k
  connection: local

# Limit ingress on all client ports to 8 Mbps
- name: Restrict client upload
  ordo_artificum.netgear.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [1, 2, 3, 4]
    ingress: 8m
  connection: local

# Remove rate limits from all ports
- name: Remove bandwidth limits
  ordo_artificum.netgear.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [1, 2, 3, 4, 5]
    ingress: no-limit
    egress: no-limit
  connection: local
```

---

### vlan

Manage 802.1Q VLANs on the switch.  Create, update, or delete VLANs,
and optionally set per-port PVIDs for untagged members.

> **Note:** The GS105Ev2 supports 802.1Q VLANs only.  There is no
> port-based VLAN or MTU VLAN mode on this hardware.

```yaml
# Enable 802.1Q and create VLAN 10: port 5 as trunk, ports 1-2 as access
- name: Create management VLAN 10
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    vlan_id: 10
    tagged_ports: [5]
    untagged_ports: [1, 2]
    pvid: 10
    state: present
  connection: local

# Create a guest VLAN
- name: Create guest VLAN 20
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    vlan_id: 20
    tagged_ports: [5]
    untagged_ports: [3, 4]
    pvid: 20
    state: present
  connection: local

# Delete a VLAN
- name: Remove VLAN 20
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    vlan_id: 20
    state: absent
  connection: local

# Enable 802.1Q mode without configuring VLANs
- name: Enable 802.1Q mode
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    dot1q_enabled: true
  connection: local
```

---

### maintenance

Perform one-off maintenance operations: reboot, factory reset, or cable
diagnostics.

> **Note:** The GS105Ev2 firmware does not provide a backup/restore API.

```yaml
# Reboot the switch
- name: Reboot switch
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: reboot
  connection: local

# Wait for it to come back
- name: Wait for switch to return
  ansible.builtin.wait_for:
    host: "{{ ansible_host }}"
    port: 80
    delay: 10
    timeout: 120

# Run cable diagnostics on all ports
- name: Run cable test
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: cable_diag
  connection: local
  register: diag

- name: Show cable diagnostic output
  ansible.builtin.debug:
    var: diag.cable_diag

# Factory reset (DESTRUCTIVE — erases all config)
- name: Factory reset
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: factory_reset
    force: true        # required safety guard
  connection: local
```

---

## Common workflows

### Initial switch provisioning

```yaml
- name: Provision Netgear switch from factory defaults
  hosts: new_switches
  connection: local
  gather_facts: false

  tasks:

    - name: Set permanent IP address and name
      ordo_artificum.netgear.system:
        host: "{{ initial_host }}"
        password: "{{ initial_password }}"
        name: "{{ inventory_hostname }}"
        ip: "{{ ansible_host }}"
        netmask: "{{ switch_netmask }}"
        gateway: "{{ switch_gateway }}"
        dhcp: false

    - name: Change default password
      ordo_artificum.netgear.system:
        host: "{{ initial_host }}"
        password: "{{ initial_password }}"
        new_password: "{{ netgear_password }}"
      no_log: true

    - name: Wait for switch at new IP
      ansible.builtin.wait_for:
        host: "{{ ansible_host }}"
        port: 80
        timeout: 30

    - name: Harden L2 settings
      ordo_artificum.netgear.igmp:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        igmp_enabled: true
        validate_ip_header: true
        block_unknown_multicast: true
        loop_detection: true
        broadcast_filter: true
```

### VLAN segmentation (802.1Q)

This example creates two VLANs: management (10) and clients (20), with
port 5 as a tagged uplink carrying both.

```yaml
- name: Configure 802.1Q VLANs
  hosts: core-switch
  connection: local
  gather_facts: false

  tasks:

    - name: Management VLAN 10 — port 1 access, port 5 trunk
      ordo_artificum.netgear.vlan:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        vlan_id: 10
        tagged_ports: [5]
        untagged_ports: [1]
        pvid: 10
        state: present

    - name: Client VLAN 20 — ports 2-4 access, port 5 trunk
      ordo_artificum.netgear.vlan:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        vlan_id: 20
        tagged_ports: [5]
        untagged_ports: [2, 3, 4]
        pvid: 20
        state: present
```

### Rate limiting client ports

```yaml
- name: Restrict client bandwidth
  hosts: switches
  connection: local
  gather_facts: false

  tasks:

    - name: Limit client ports to 8 Mbps in and out
      ordo_artificum.netgear.bandwidth:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        port: [1, 2, 3, 4]
        ingress: 8m
        egress: 8m

    - name: Remove limits from uplink port 5
      ordo_artificum.netgear.bandwidth:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        port: [5]
        ingress: no-limit
        egress: no-limit
```

### Network security hardening

```yaml
- name: Harden switch network security
  hosts: switches
  connection: local
  gather_facts: false

  tasks:

    - name: Enable IGMP snooping, loop detection, and broadcast filter
      ordo_artificum.netgear.igmp:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        igmp_enabled: true
        validate_ip_header: true
        block_unknown_multicast: true
        loop_detection: true
        broadcast_filter: true

    - name: Disable unused ports
      ordo_artificum.netgear.port:
        host: "{{ ansible_host }}"
        password: "{{ netgear_password }}"
        port: "{{ unused_ports }}"
        speed: DISABLE
      when: unused_ports is defined and unused_ports | length > 0
```

---

## Return values and registered variables

Every module returns `changed` (bool) and a module-specific key with
the current switch state after the task runs.  Register the result to
use it in subsequent tasks:

```yaml
- name: Gather facts
  ordo_artificum.netgear.facts:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
  connection: local

- name: Fail if firmware is outdated
  ansible.builtin.fail:
    msg: "Firmware {{ netgear.config.firmware }} is unexpected"
  when: "'V1.6.0' not in netgear.config.firmware"

- name: Run cable diagnostics
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: cable_diag
  connection: local
  register: cable_result

- name: Show raw cable diagnostic output
  ansible.builtin.debug:
    var: cable_result.cable_diag
```

---

## Check mode

All modules support `--check` mode.  No changes are written to the
switch; the return value shows what would have changed.

```bash
ansible-playbook site.yml --check --diff
```

`cable_diag` is always run in check mode — it is a read-only diagnostic.

---

## License

GNU General Public License v3.0.
See [LICENSE](https://www.gnu.org/licenses/gpl-3.0.html) for full text.
