#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: mirror
short_description: Configure port mirroring on a Netgear Smart Managed Plus switch
description:
  - Enable or disable port mirroring (SPAN).
  - The GS105Ev2 mirrors all traffic (rx+tx) on the source ports; ingress-only
    or egress-only mirroring is not supported by the hardware.
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
  dest_port:
    description: Destination port number (traffic is copied here).  Required when C(state=present).
    type: int
  source_ports:
    description: Source port number(s) to mirror.  Required when C(state=present).
    type: list
    elements: int
  state:
    description: C(present) enables mirroring; C(absent) disables it.
    type: str
    choices: [present, absent]
    default: present
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - The GS105Ev2 supports one mirror session only.
  - The hardware always mirrors both rx and tx; the direction cannot be
    configured separately.
'''

EXAMPLES = r'''
- name: Mirror ports 1-3 to port 5 for packet capture
  jfrancis42.netgear.mirror:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    dest_port: 5
    source_ports: [1, 2, 3]
    state: present
  connection: local

- name: Disable port mirroring
  jfrancis42.netgear.mirror:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    state: absent
  connection: local
'''

RETURN = r'''
mirror:
  description: Port mirroring configuration after any changes.
  returned: always
  type: dict
changed:
  description: Whether the mirroring configuration was changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.jfrancis42.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_mirror,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        dest_port=dict(type='int'),
        source_ports=dict(type='list', elements='int'),
        state=dict(type='str', choices=['present', 'absent'], default='present'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_if=[
            ('state', 'present', ['dest_port', 'source_ports']),
        ],
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    want_enabled = (p['state'] == 'present')

    try:
        with make_switch(p) as sw:
            current = sw.get_mirror_config()

            if want_enabled:
                desired_src = sorted(p['source_ports'])
                needs_change = (
                    not current.enabled or
                    current.dest_port != p['dest_port'] or
                    sorted(current.source_ports) != desired_src
                )
                if needs_change and not module.check_mode:
                    sw.set_mirror_config(
                        enabled=True,
                        dest_port=p['dest_port'],
                        source_ports=p['source_ports'],
                    )
            else:
                needs_change = current.enabled
                if needs_change and not module.check_mode:
                    sw.set_mirror_config(enabled=False, dest_port=1, source_ports=[])

            final = sw.get_mirror_config() if (needs_change and not module.check_mode) else current

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=needs_change, mirror=serialize_mirror(final))


def main():
    run_module()


if __name__ == '__main__':
    main()
