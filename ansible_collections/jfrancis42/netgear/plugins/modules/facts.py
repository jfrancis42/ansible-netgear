#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: facts
short_description: Gather facts from a Netgear Smart Managed Plus switch
description:
  - Reads all available state from a Netgear Smart Managed Plus switch and
    registers it as Ansible facts under the C(netgear) key.
  - If an individual subsystem read fails, its key will contain
    a dict with an C(_error) key rather than failing the whole task.
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
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - The switch enforces a single-session limit; the module logs out after
    each run to free the slot.
'''

EXAMPLES = r'''
- name: Gather switch facts
  jfrancis42.netgear.facts:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
  connection: local

- name: Show firmware version
  ansible.builtin.debug:
    msg: "Firmware: {{ netgear.config.firmware }}"

- name: Show all port states
  ansible.builtin.debug:
    msg: "Port {{ item.port }}: {{ 'up' if item.enabled else 'down' }}"
  loop: "{{ netgear.ports }}"

- name: Check if 802.1Q is enabled
  ansible.builtin.debug:
    msg: "VLAN mode: {{ 'dot1q' if netgear.vlan.dot1q_enabled else 'off' }}"
'''

RETURN = r'''
ansible_facts:
  description: Facts registered under the C(netgear) key.
  returned: always
  type: dict
  contains:
    netgear:
      description: All switch state.
      type: dict
      contains:
        system:
          description: Read-only system snapshot (MAC, IP, firmware).
          type: dict
        config:
          description: Full switch config including name, DHCP, model, serial.
          type: dict
        ports:
          description: Per-port settings (speed, flow control, link state).
          type: list
        port_stats:
          description: Per-port byte counters and CRC errors.
          type: list
        rate_limits:
          description: Per-port ingress/egress rate limits.
          type: list
        mirror:
          description: Port mirroring configuration.
          type: dict
        igmp:
          description: IGMP snooping configuration.
          type: dict
        loop_detection:
          description: Loop detection enabled state.
          type: bool
        broadcast_filter:
          description: Broadcast filter enabled state.
          type: bool
        qos_mode:
          description: QoS scheduling mode.
          type: str
        vlan:
          description: 802.1Q VLAN configuration.
          type: dict
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.jfrancis42.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_system_info, serialize_switch_config, serialize_port_info,
        serialize_port_stats, serialize_rate_limit, serialize_mirror,
        serialize_igmp, serialize_vlan_entry,
    )
except ImportError:
    pass


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {'_error': str(e)}


def _err(result):
    return isinstance(result, dict) and '_error' in result


def run_module():
    module = AnsibleModule(
        argument_spec=dict(**CONNECTION_ARGS),
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    facts = {}

    try:
        with make_switch(module.params) as sw:

            # -- System --
            r = _safe(sw.get_system_info)
            facts['system'] = {'_error': r['_error']} if _err(r) else serialize_system_info(r)

            r = _safe(sw.get_switch_config)
            facts['config'] = {'_error': r['_error']} if _err(r) else serialize_switch_config(r)

            # -- Ports --
            r = _safe(sw.get_port_settings)
            facts['ports'] = (
                {'_error': r['_error']} if _err(r)
                else [serialize_port_info(p) for p in r]
            )

            r = _safe(sw.get_port_stats)
            facts['port_stats'] = (
                {'_error': r['_error']} if _err(r)
                else [serialize_port_stats(s) for s in r]
            )

            r = _safe(sw.get_rate_limits)
            facts['rate_limits'] = (
                {'_error': r['_error']} if _err(r)
                else [serialize_rate_limit(rl) for rl in r]
            )

            # -- Topology --
            r = _safe(sw.get_mirror_config)
            facts['mirror'] = {'_error': r['_error']} if _err(r) else serialize_mirror(r)

            # -- L2 features --
            r = _safe(sw.get_igmp_config)
            facts['igmp'] = {'_error': r['_error']} if _err(r) else serialize_igmp(r)

            r = _safe(sw.get_loop_detection)
            facts['loop_detection'] = r

            r = _safe(sw.get_broadcast_filter)
            facts['broadcast_filter'] = r

            r = _safe(sw.get_qos_mode)
            facts['qos_mode'] = r

            # -- VLAN --
            vlan_facts = {}
            dot1q_en = _safe(sw.get_dot1q_enabled)
            if _err(dot1q_en):
                vlan_facts['_error'] = dot1q_en['_error']
            else:
                vlan_facts['dot1q_enabled'] = dot1q_en
                if dot1q_en:
                    vids = _safe(sw.get_vlan_ids)
                    if _err(vids):
                        vlan_facts['vlans'] = {'_error': vids['_error']}
                    else:
                        vlans = []
                        for vid in vids:
                            mem = _safe(sw.get_vlan_membership, vid)
                            if not _err(mem):
                                vlans.append(serialize_vlan_entry(vid, mem))
                        vlan_facts['vlans'] = vlans

                    pvids = _safe(sw.get_port_pvids)
                    vlan_facts['pvids'] = pvids if not _err(pvids) else {'_error': pvids['_error']}
                else:
                    vlan_facts['vlans'] = []

            facts['vlan'] = vlan_facts

    except Exception as e:
        module.fail_json(msg='Failed to connect to switch: %s' % str(e))

    module.exit_json(changed=False, ansible_facts={'netgear': facts})


def main():
    run_module()


if __name__ == '__main__':
    main()
