#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: system
short_description: Manage system settings on a Netgear Smart Managed Plus switch
description:
  - Configure the switch name, IP settings, and admin password.
  - Any parameter left unset is left unchanged on the switch.
options:
  host:
    description: Switch management IP or hostname.
    required: true
    type: str
  password:
    description: Login password (current password).
    required: true
    type: str
    no_log: true
  timeout:
    description: HTTP request timeout in seconds.
    type: float
    default: 10.0
  name:
    description: Switch name (up to 20 characters).
    type: str
  ip:
    description: Static IP address.
    type: str
  netmask:
    description: Subnet mask.
    type: str
  gateway:
    description: Default gateway.
    type: str
  dhcp:
    description: Enable DHCP.  When true, C(ip)/C(netmask)/C(gateway) are ignored.
    type: bool
  new_password:
    description: New admin password.  C(password) is used as the old password.
    type: str
    no_log: true
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - Changing C(ip) or enabling C(dhcp) will change the switch management
    address; subsequent tasks must target the new address.
  - Password changes always report C(changed=true) — there is no way to verify
    the current password without attempting to change it.
'''

EXAMPLES = r'''
- name: Set switch name and static IP
  ordo_artificum.netgear.system:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    name: lab-gs105-1
    ip: 192.168.0.1
    netmask: 255.255.255.0
    gateway: 192.168.0.254
    dhcp: false
  connection: local

- name: Enable DHCP
  ordo_artificum.netgear.system:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    dhcp: true
  connection: local

- name: Rotate admin password
  ordo_artificum.netgear.system:
    host: "{{ ansible_host }}"
    password: "{{ current_password }}"
    new_password: "{{ new_password }}"
  connection: local
  no_log: true
'''

RETURN = r'''
config:
  description: Switch configuration after any changes.
  returned: always
  type: dict
changed:
  description: Whether any changes were made to the switch.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.ordo_artificum.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_switch_config,
    )
except ImportError:
    pass


def run_module():
    argument_spec = dict(
        **CONNECTION_ARGS,
        name=dict(type='str'),
        ip=dict(type='str'),
        netmask=dict(type='str'),
        gateway=dict(type='str'),
        dhcp=dict(type='bool'),
        new_password=dict(type='str', no_log=True),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    changed = False

    try:
        with make_switch(p) as sw:
            current = sw.get_switch_config()

            # -- switch name --
            if p['name'] is not None and p['name'] != current.name:
                changed = True
                if not module.check_mode:
                    sw.set_switch_name(p['name'])

            # -- IP settings --
            ip_needs_change = (
                (p['dhcp'] is not None and p['dhcp'] != current.dhcp) or
                (p['ip'] is not None and p['ip'] != current.ip) or
                (p['netmask'] is not None and p['netmask'] != current.netmask) or
                (p['gateway'] is not None and p['gateway'] != current.gateway)
            )
            if ip_needs_change:
                changed = True
                if not module.check_mode:
                    sw.set_ip_settings(
                        ip=p['ip'],
                        netmask=p['netmask'],
                        gateway=p['gateway'],
                        dhcp=p['dhcp'],
                    )

            # -- password --
            if p['new_password'] is not None:
                changed = True
                if not module.check_mode:
                    sw.change_password(
                        old_password=p['password'],
                        new_password=p['new_password'],
                    )

            if changed and not module.check_mode:
                final = sw.get_switch_config()
            else:
                final = current

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, config=serialize_switch_config(final))


def main():
    run_module()


if __name__ == '__main__':
    main()
