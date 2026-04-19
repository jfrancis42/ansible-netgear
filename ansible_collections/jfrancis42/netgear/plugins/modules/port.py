#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: port
short_description: Configure port settings on a Netgear Smart Managed Plus switch
description:
  - Set speed/duplex and flow control on one or more ports.
  - Only parameters that are explicitly set are changed; unspecified parameters
    are left as-is on the switch.
  - Each port is configured in a separate request (the Netgear CGI does not
    support bulk port configuration).
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
  port:
    description: Port number(s) to configure (1-based).
    required: true
    type: list
    elements: int
  speed:
    description: >
      Configured speed/duplex.  Use C(DISABLE) to administratively disable
      a port (equivalent to C(shutdown) in the CLI).  C(AUTO) negotiates
      up to 1 Gbit/s.
    type: str
    choices: [AUTO, DISABLE, M10H, M10F, M100H, M100F]
  flow_control:
    description: Enable flow control on the port(s).
    type: bool
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - GS105Ev2 does not support forcing 1 Gbit/s; use C(AUTO) and allow
    the hardware to negotiate to 1 Gbit/s when the link partner supports it.
  - To disable a port, set C(speed: DISABLE).  To re-enable it, set
    C(speed: AUTO) (or any other speed).
'''

EXAMPLES = r'''
- name: Enable ports 1-4 at auto speed with flow control
  jfrancis42.netgear.port:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [1, 2, 3, 4]
    speed: AUTO
    flow_control: true
  connection: local

- name: Disable an unused port
  jfrancis42.netgear.port:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [5]
    speed: DISABLE
  connection: local

- name: Force port 2 to 100M full-duplex, no flow control
  jfrancis42.netgear.port:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [2]
    speed: M100F
    flow_control: false
  connection: local
'''

RETURN = r'''
ports:
  description: Current settings for the configured ports after any changes.
  returned: always
  type: list
changed:
  description: Whether any port settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.jfrancis42.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_port_info, PortSpeed,
    )
    if HAS_SDK and PortSpeed is not None:
        _SPEED_MAP = {member.name: member for member in PortSpeed
                      if member.name not in ('NONE',)}
    else:
        _SPEED_MAP = {}
except ImportError:
    _SPEED_MAP = {}
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        port=dict(type='list', elements='int', required=True),
        speed=dict(type='str', choices=['AUTO', 'DISABLE', 'M10H', 'M10F', 'M100H', 'M100F']),
        flow_control=dict(type='bool'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['speed', 'flow_control']],
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    target_ports = p['port']
    desired_speed = _SPEED_MAP.get(p['speed']) if p['speed'] else None

    try:
        with make_switch(p) as sw:
            all_ports = sw.get_port_settings()
            port_map = {pi.port: pi for pi in all_ports}

            # Check whether any targeted port differs from the desired settings
            needs_change = False
            for port_num in target_ports:
                pi = port_map.get(port_num)
                if pi is None:
                    module.fail_json(msg='Port %d not found on switch' % port_num)
                if desired_speed is not None and pi.speed_cfg != desired_speed:
                    needs_change = True
                    break
                if p['flow_control'] is not None and pi.fc_enabled != p['flow_control']:
                    needs_change = True
                    break

            if needs_change and not module.check_mode:
                for port_num in target_ports:
                    sw.set_port(
                        port_num,
                        speed=desired_speed,
                        fc_enabled=p['flow_control'],
                    )
                all_ports = sw.get_port_settings()
                port_map = {pi.port: pi for pi in all_ports}

            result_ports = [serialize_port_info(port_map[n])
                            for n in target_ports if n in port_map]

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=needs_change, ports=result_ports)


def main():
    run_module()


if __name__ == '__main__':
    main()
