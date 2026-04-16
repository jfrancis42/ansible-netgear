#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: maintenance
short_description: Perform maintenance operations on a Netgear Smart Managed Plus switch
description:
  - Reboot or factory-reset a Netgear Smart Managed Plus switch.
  - Run cable diagnostics on one or more ports.
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
  action:
    description: Maintenance action to perform.
    required: true
    type: str
    choices:
      - reboot
      - factory_reset
      - cable_diag
  ports:
    description: >
      Port numbers to run cable diagnostics on (1-based).
      If omitted, all ports are tested.  Used with C(action=cable_diag).
    type: list
    elements: int
  force:
    description: >
      Required to be C(true) for C(action=factory_reset) as a safety guard.
      A factory reset erases all configuration and resets the switch IP to
      its factory default.
    type: bool
    default: false
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - There is no backup/restore API on the GS105Ev2 firmware.
  - C(reboot) makes the switch temporarily unreachable; add appropriate
    waits in your playbook.
  - C(factory_reset) resets all configuration including the IP address;
    subsequent tasks must target the new (factory default) address.
  - C(cable_diag) disrupts traffic briefly on the tested ports.
    It is always run regardless of check mode (diagnostic, not destructive).
'''

EXAMPLES = r'''
- name: Reboot switch
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: reboot
  connection: local

- name: Factory reset (DESTRUCTIVE)
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: factory_reset
    force: true
  connection: local

- name: Run cable diagnostics on all ports
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: cable_diag
  connection: local
  register: diag

- name: Show cable diagnostic raw output
  ansible.builtin.debug:
    var: diag.cable_diag

- name: Run cable diagnostics on ports 1 and 2 only
  ordo_artificum.netgear.maintenance:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    action: cable_diag
    ports: [1, 2]
  connection: local
'''

RETURN = r'''
changed:
  description: Whether the switch state was changed.
  returned: always
  type: bool
cable_diag:
  description: Raw HTML output from the cable tester (action=cable_diag only).
  returned: when action is cable_diag
  type: str
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        action=dict(
            type='str', required=True,
            choices=['reboot', 'factory_reset', 'cable_diag'],
        ),
        ports=dict(type='list', elements='int'),
        force=dict(type='bool', default=False),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    action = p['action']

    if action == 'factory_reset' and not p['force']:
        module.fail_json(
            msg='action=factory_reset requires force=true.  '
                'This will erase all configuration and reset the switch to factory defaults.'
        )

    try:
        with make_switch(p) as sw:

            if action == 'reboot':
                if not module.check_mode:
                    sw.reboot()
                module.exit_json(changed=True)

            elif action == 'factory_reset':
                if not module.check_mode:
                    sw.factory_reset()
                module.exit_json(changed=True)

            elif action == 'cable_diag':
                port_count = 5
                ports = p['ports'] if p['ports'] else list(range(1, port_count + 1))
                # Cable diagnostics are always run — they are read-only diagnostics
                raw_html = sw.test_cable(ports)
                module.exit_json(changed=False, cable_diag=raw_html)

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))


def main():
    run_module()


if __name__ == '__main__':
    main()
