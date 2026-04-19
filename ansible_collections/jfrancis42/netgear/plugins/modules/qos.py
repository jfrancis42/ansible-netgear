#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: qos
short_description: Configure QoS mode on a Netgear Smart Managed Plus switch
description:
  - Set the global QoS scheduling mode on a Netgear Smart Managed Plus switch.
  - The GS105Ev2 supports two QoS modes: port-based and 802.1p/DSCP.
    Per-port priority configuration is not available on this hardware.
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
  mode:
    description: >
      QoS scheduling mode.  C(port-based) gives each port a fixed priority;
      C(802.1p/dscp) uses IEEE 802.1p VLAN priority bits and/or DSCP markings.
    required: true
    type: str
    choices: ['port-based', '802.1p/dscp']
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - The GS105Ev2 does not support per-port priority configuration; only the
    global mode can be changed through the web UI.
'''

EXAMPLES = r'''
- name: Set QoS to port-based mode
  jfrancis42.netgear.qos:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    mode: port-based
  connection: local

- name: Set QoS to 802.1p/DSCP mode
  jfrancis42.netgear.qos:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    mode: 802.1p/dscp
  connection: local
'''

RETURN = r'''
mode:
  description: QoS mode after any changes.
  returned: always
  type: str
changed:
  description: Whether the QoS mode was changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.jfrancis42.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        mode=dict(type='str', required=True, choices=['port-based', '802.1p/dscp']),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    desired_mode = p['mode']

    try:
        with make_switch(p) as sw:
            current_mode = sw.get_qos_mode()

            if current_mode != desired_mode:
                changed = True
                if not module.check_mode:
                    sw.set_qos_mode(desired_mode)
                    current_mode = sw.get_qos_mode()
            else:
                changed = False

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, mode=current_mode)


def main():
    run_module()


if __name__ == '__main__':
    main()
