#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: igmp
short_description: Configure IGMP snooping, loop detection, and broadcast filtering
description:
  - Configure IGMP snooping, loop detection, and broadcast filtering on a
    Netgear Smart Managed Plus switch.
  - Any parameter left unset is left unchanged on the switch.  At least one
    parameter must be specified.
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
  igmp_enabled:
    description: Enable or disable IGMP snooping.
    type: bool
  vlan_id:
    description: >
      Restrict IGMP snooping to a specific VLAN ID (as a string, e.g. C('10')).
      An empty string means all VLANs.
    type: str
  validate_ip_header:
    description: Enable IP header validation for IGMP snooping.
    type: bool
  block_unknown_multicast:
    description: Block unknown multicast traffic when IGMP snooping is enabled.
    type: bool
  static_router_port:
    description: >
      Static router port number as a string (C('1')–C('5')).  Use C('0') for none.
    type: str
  loop_detection:
    description: Enable or disable loop detection.
    type: bool
  broadcast_filter:
    description: Enable or disable broadcast storm filtering.
    type: bool
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - IGMP snooping parameters are applied together in a single write.  When
    C(igmp_enabled) is omitted, the current enabled state is preserved.
'''

EXAMPLES = r'''
- name: Enable IGMP snooping
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    igmp_enabled: true
  connection: local

- name: Enable loop detection and broadcast filter
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    loop_detection: true
    broadcast_filter: true
  connection: local

- name: Full L2 hardening in one task
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    igmp_enabled: true
    validate_ip_header: true
    block_unknown_multicast: true
    loop_detection: true
    broadcast_filter: true
  connection: local

- name: Restrict IGMP snooping to VLAN 10 with static router port on gi5
  ordo_artificum.netgear.igmp:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    igmp_enabled: true
    vlan_id: "10"
    static_router_port: "5"
  connection: local
'''

RETURN = r'''
igmp:
  description: IGMP snooping configuration after any changes.
  returned: always
  type: dict
loop_detection:
  description: Loop detection state after any changes.
  returned: always
  type: bool
broadcast_filter:
  description: Broadcast filter state after any changes.
  returned: always
  type: bool
changed:
  description: Whether any settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_igmp,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        igmp_enabled=dict(type='bool'),
        vlan_id=dict(type='str'),
        validate_ip_header=dict(type='bool'),
        block_unknown_multicast=dict(type='bool'),
        static_router_port=dict(type='str'),
        loop_detection=dict(type='bool'),
        broadcast_filter=dict(type='bool'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[[
            'igmp_enabled', 'vlan_id', 'validate_ip_header',
            'block_unknown_multicast', 'static_router_port',
            'loop_detection', 'broadcast_filter',
        ]],
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    changed = False

    try:
        with make_switch(p) as sw:
            cur_igmp  = sw.get_igmp_config()
            cur_loop  = sw.get_loop_detection()
            cur_bcast = sw.get_broadcast_filter()

            # -- IGMP snooping --
            any_igmp_param = any(p[k] is not None for k in [
                'igmp_enabled', 'vlan_id', 'validate_ip_header',
                'block_unknown_multicast', 'static_router_port',
            ])
            if any_igmp_param:
                want_enabled  = p['igmp_enabled'] if p['igmp_enabled'] is not None else cur_igmp.enabled
                want_vlan     = p['vlan_id'] if p['vlan_id'] is not None else cur_igmp.vlan_id
                want_val_ip   = p['validate_ip_header'] if p['validate_ip_header'] is not None else cur_igmp.validate_ip_header
                want_block    = p['block_unknown_multicast'] if p['block_unknown_multicast'] is not None else cur_igmp.block_unknown_multicast
                want_rport    = p['static_router_port'] if p['static_router_port'] is not None else cur_igmp.static_router_port

                igmp_needs_change = (
                    cur_igmp.enabled != want_enabled or
                    cur_igmp.vlan_id != want_vlan or
                    cur_igmp.validate_ip_header != want_val_ip or
                    cur_igmp.block_unknown_multicast != want_block or
                    cur_igmp.static_router_port != want_rport
                )
                if igmp_needs_change:
                    changed = True
                    if not module.check_mode:
                        sw.set_igmp_config(
                            enabled=want_enabled,
                            vlan_id=want_vlan,
                            validate_ip_header=want_val_ip,
                            block_unknown_multicast=want_block,
                            static_router_port=want_rport,
                        )

            # -- loop detection --
            if p['loop_detection'] is not None and p['loop_detection'] != cur_loop:
                changed = True
                if not module.check_mode:
                    sw.set_loop_detection(p['loop_detection'])

            # -- broadcast filter --
            if p['broadcast_filter'] is not None and p['broadcast_filter'] != cur_bcast:
                changed = True
                if not module.check_mode:
                    sw.set_broadcast_filter(p['broadcast_filter'])

            if changed and not module.check_mode:
                final_igmp  = sw.get_igmp_config()
                final_loop  = sw.get_loop_detection()
                final_bcast = sw.get_broadcast_filter()
            else:
                final_igmp  = cur_igmp
                final_loop  = cur_loop
                final_bcast = cur_bcast

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(
        changed=changed,
        igmp=serialize_igmp(final_igmp),
        loop_detection=final_loop,
        broadcast_filter=final_bcast,
    )


def main():
    run_module()


if __name__ == '__main__':
    main()
