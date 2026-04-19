#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: bandwidth
short_description: Manage bandwidth (rate) limits on a Netgear Smart Managed Plus switch
description:
  - Set ingress and/or egress bandwidth limits on one or more ports of a
    Netgear Smart Managed Plus switch.
  - Rate limits are specified as named labels rather than raw kbps values.
  - Each port is configured individually (the Netgear CGI does not support
    bulk rate-limit configuration).
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
  ingress:
    description: >
      Ingress (incoming) rate limit.  C(no-limit) removes the limit.
      Valid values: C(no-limit), C(512k), C(1m), C(2m), C(4m), C(8m),
      C(16m), C(32m), C(64m), C(128m), C(256m), C(512m).
    type: str
    choices: ['no-limit', '512k', '1m', '2m', '4m', '8m', '16m', '32m',
              '64m', '128m', '256m', '512m']
  egress:
    description: >
      Egress (outgoing) rate limit.  C(no-limit) removes the limit.
      Valid values: same as C(ingress).
    type: str
    choices: ['no-limit', '512k', '1m', '2m', '4m', '8m', '16m', '32m',
              '64m', '128m', '256m', '512m']
notes:
  - Runs on the Ansible controller; use C(connection: local).
  - At least one of C(ingress) or C(egress) must be specified.
  - Rate limits are set per-port; the same ingress and egress values are
    applied to all ports listed in C(port).
'''

EXAMPLES = r'''
- name: Limit port 3 ingress to 1 Mbps, egress to 512 Kbps
  jfrancis42.netgear.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [3]
    ingress: 1m
    egress: 512k
  connection: local

- name: Remove rate limits from ports 1 and 2
  jfrancis42.netgear.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [1, 2]
    ingress: no-limit
    egress: no-limit
  connection: local

- name: Limit guest port ingress only
  jfrancis42.netgear.bandwidth:
    host: "{{ ansible_host }}"
    password: "{{ netgear_password }}"
    port: [4]
    ingress: 8m
  connection: local
'''

RETURN = r'''
bandwidth:
  description: Current rate limit settings for the configured ports.
  returned: always
  type: list
changed:
  description: Whether any rate limit settings were changed.
  returned: always
  type: bool
'''

from ansible.module_utils.basic import AnsibleModule

try:
    from ansible_collections.jfrancis42.netgear.plugins.module_utils.common import (
        CONNECTION_ARGS, make_switch, HAS_SDK, SDK_ERROR,
        serialize_rate_limit,
    )
    if HAS_SDK:
        from ansible_collections.jfrancis42.netgear.plugins.module_utils.netgear_switch import (
            RateLimit,
        )
    else:
        RateLimit = None
except ImportError:
    RateLimit = None
    pass

_LABEL_TO_RATE = None


def _build_label_map():
    global _LABEL_TO_RATE
    if _LABEL_TO_RATE is not None or RateLimit is None:
        return
    labels = [
        'no-limit', '512k', '1m', '2m', '4m', '8m',
        '16m', '32m', '64m', '128m', '256m', '512m',
    ]
    # RateLimit values 1–12 correspond to the labels in order.
    # Exclude NONE (value=0) which is a placeholder, not a configurable rate.
    members = [m for m in sorted(RateLimit, key=lambda m: m.value) if m.value > 0]
    _LABEL_TO_RATE = {label: member for label, member in zip(labels, members)}


def run_module():
    _build_label_map()

    argument_spec = dict(
        **CONNECTION_ARGS,
        port=dict(type='list', elements='int', required=True),
        ingress=dict(
            type='str',
            choices=['no-limit', '512k', '1m', '2m', '4m', '8m',
                     '16m', '32m', '64m', '128m', '256m', '512m'],
        ),
        egress=dict(
            type='str',
            choices=['no-limit', '512k', '1m', '2m', '4m', '8m',
                     '16m', '32m', '64m', '128m', '256m', '512m'],
        ),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True,
        required_one_of=[['ingress', 'egress']],
    )

    if not HAS_SDK:
        module.fail_json(msg='netgear_switch SDK not available: %s' % SDK_ERROR)

    p = module.params
    target_ports = p['port']
    desired_ingress = _LABEL_TO_RATE.get(p['ingress']) if p['ingress'] else None
    desired_egress  = _LABEL_TO_RATE.get(p['egress'])  if p['egress']  else None
    changed = False

    try:
        with make_switch(p) as sw:
            all_rl = sw.get_rate_limits()
            rl_map = {rl.port: rl for rl in all_rl}

            needs_change = any(
                (desired_ingress is not None and rl_map[n].ingress != desired_ingress) or
                (desired_egress  is not None and rl_map[n].egress  != desired_egress)
                for n in target_ports if n in rl_map
            )

            if needs_change:
                changed = True
                if not module.check_mode:
                    for port_num in target_ports:
                        cur = rl_map.get(port_num)
                        if cur is None:
                            continue
                        new_ingress = desired_ingress if desired_ingress is not None else cur.ingress
                        new_egress  = desired_egress  if desired_egress  is not None else cur.egress
                        sw.set_rate_limit(port_num, new_ingress, new_egress)
                    all_rl = sw.get_rate_limits()
                    rl_map = {rl.port: rl for rl in all_rl}

            result = [serialize_rate_limit(rl_map[n]) for n in target_ports if n in rl_map]

    except Exception as e:
        module.fail_json(msg='Switch operation failed: %s' % str(e))

    module.exit_json(changed=changed, bandwidth=result)


def main():
    run_module()


if __name__ == '__main__':
    main()
