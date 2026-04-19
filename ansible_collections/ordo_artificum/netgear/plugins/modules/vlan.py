#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: vlan
short_description: Manage 802.1Q VLANs on a Netgear Smart Managed Plus switch
description:
  - Create, update, or delete 802.1Q VLANs on a Netgear Smart Managed Plus switch.
  - Optionally set per-port PVIDs for untagged members.
  - The GS105Ev2 supports 802.1Q VLANs only (no port-based or MTU VLAN modes).
options:
  host:
    description: Switch management IP or hostname.
    required: true
    type: str
  password:
    description: Login password.
    required: true
    type: str
    no_log: true
  timeout:
    description: HTTP request timeout in seconds.
    type: float
    default: 10.0
  vlan_id:
    description: VLAN ID to operate on (2–4094).
    type: int
  tagged_ports:
    description: Tagged (trunk) member ports for the VLAN.
    type: list
    elements: int
  untagged_ports:
    description: Untagged (access) member ports for the VLAN.
    type: list
    elements: int
  pvid:
    description: >
      PVID to assign to each port listed in C(untagged_ports).
      If omitted, PVIDs are left unchanged.
    type: int
  dot1q_enabled:
    description: >
      Explicitly enable or disable 802.1Q VLAN mode.  When C(state=present)
      and C(vlan_id) is specified, 802.1Q mode is enabled automatically.
    type: bool
  state:
    description: >
      C(present) ensures the VLAN exists with the given port membership.
      C(absent) removes the VLAN.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - The GS105Ev2 supports 802.1Q VLANs only.  There is no port-based or
    MTU VLAN mode on this hardware.
  - When C(state=present) and the VLAN does not exist, it is created.
    When it already exists, only the explicitly specified memberships are
    changed; ports not listed in C(tagged_ports) or C(untagged_ports) keep
    their current membership.
  - Enabling 802.1Q mode does not erase existing VLAN configuration.
  - At least one of C(dot1q_enabled) or C(vlan_id) must be specified.
'''

EXAMPLES = r'''
- name: Enable 802.1Q and create VLAN 10 with port 5 as trunk, ports 1-2 as access
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    vlan_id: 10
    tagged_ports: [5]
    untagged_ports: [1, 2]
    pvid: 10
    state: present
  connection: local

- name: Add port 3 as an untagged member of VLAN 10
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    vlan_id: 10
    untagged_ports: [3]
    pvid: 10
    state: present
  connection: local

- name: Remove VLAN 10
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    vlan_id: 10
    state: absent
  connection: local

- name: Enable 802.1Q mode without configuring any VLANs
  ordo_artificum.netgear.vlan:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    dot1q_enabled: true
  connection: local
'''

RETURN = r'''
vlan:
  description: Current VLAN configuration after any changes.
  returned: always
  type: dict
  contains:
    dot1q_enabled:
      description: Whether 802.1Q mode is active.
      type: bool
    vlans:
      description: List of configured VLANs with port membership.
      type: list
    pvids:
      description: Per-port PVID mapping.
      type: dict
changed:
  description: Whether any VLAN settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_vlan_entry,
    )
except ImportError:
    pass

_PORT_COUNT = 5


def _membership_str(vid, current_mem, tagged_ports, untagged_ports, port_count):
    """
    Build an updated membership string for a VLAN.

    Starts from current_mem (or all-'3' for new VLANs — the firmware's
    encoding for "not a member").  Applies tagged_ports and untagged_ports
    on top.  Ports not mentioned keep their current membership.

    Firmware encoding: '1'=untagged, '2'=tagged, '3'=not-a-member.
    """
    base = list(current_mem) if current_mem else ['3'] * port_count
    if tagged_ports is not None:
        for p in tagged_ports:
            if 1 <= p <= port_count:
                base[p - 1] = '2'
    if untagged_ports is not None:
        for p in untagged_ports:
            if 1 <= p <= port_count:
                base[p - 1] = '1'
    return ''.join(base)


def _build_vlan_return(sw, check_mode):
    """Read and serialise current VLAN state."""
    if check_mode:
        return dict(dot1q_enabled=None, vlans=[], pvids={})
    try:
        dot1q_en = sw.get_dot1q_enabled()
        vlans = []
        if dot1q_en:
            vids = sw.get_vlan_ids()
            for vid in vids:
                mem = sw.get_vlan_membership(vid)
                vlans.append(serialize_vlan_entry(vid, mem))
        pvids = sw.get_port_pvids()
        return dict(dot1q_enabled=dot1q_en, vlans=vlans, pvids=pvids)
    except Exception:
        return dict(dot1q_enabled=None, vlans=[], pvids={})


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        vlan_id=dict(type='int'),
        tagged_ports=dict(type='list', elements='int'),
        untagged_ports=dict(type='list', elements='int'),
        pvid=dict(type='int'),
        dot1q_enabled=dict(type='bool'),
        state=dict(type='str', default='present', choices=['present', 'absent']),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['dot1q_enabled', 'vlan_id']],
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    changed = False

    try:
        with make_switch(p) as sw:

            # -- 802.1Q mode --
            dot1q_en = sw.get_dot1q_enabled()

            if p['dot1q_enabled'] is not None and p['dot1q_enabled'] != dot1q_en:
                changed = True
                if not module.check_mode:
                    sw.set_dot1q_enabled(p['dot1q_enabled'])
                    dot1q_en = p['dot1q_enabled']

            # Auto-enable 802.1Q when state=present and vlan_id is specified
            if p['vlan_id'] is not None and p['state'] == 'present' and not dot1q_en:
                changed = True
                if not module.check_mode:
                    sw.set_dot1q_enabled(True)
                    dot1q_en = True

            if p['vlan_id'] is None:
                # Mode-only change — done
                vlan_info = _build_vlan_return(sw, module.check_mode)
                module.exit_json(changed=changed, vlan=vlan_info)
                return

            vid = p['vlan_id']

            if p['state'] == 'absent':
                # Delete VLAN if it exists
                existing_ids = sw.get_vlan_ids() if not module.check_mode else []
                if module.check_mode or vid in existing_ids:
                    # In check mode we assume it exists if vlan_id is given
                    changed = True
                    if not module.check_mode:
                        sw.delete_vlan(vid)
            else:
                # state == 'present'
                existing_ids = sw.get_vlan_ids() if not module.check_mode else []

                if module.check_mode or vid not in existing_ids:
                    # New VLAN
                    changed = True
                    if not module.check_mode:
                        sw.add_vlan(vid)
                        existing_ids = sw.get_vlan_ids()

                if not module.check_mode:
                    # Update membership
                    current_mem = sw.get_vlan_membership(vid) if vid in existing_ids else ''
                    desired_mem = _membership_str(
                        vid, current_mem,
                        p['tagged_ports'], p['untagged_ports'],
                        _PORT_COUNT,
                    )
                    if desired_mem != current_mem:
                        changed = True
                        sw.set_vlan_membership(vid, desired_mem)

                # Set PVIDs for untagged ports
                if p['pvid'] is not None and p['untagged_ports'] and not module.check_mode:
                    current_pvids = sw.get_port_pvids()
                    for port_num in p['untagged_ports']:
                        if current_pvids.get(port_num) != p['pvid']:
                            changed = True
                            sw.set_port_pvid(port_num, p['pvid'])

            vlan_info = _build_vlan_return(sw, module.check_mode)

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, vlan=vlan_info)


def main():
    run_module()


if __name__ == '__main__':
    main()
