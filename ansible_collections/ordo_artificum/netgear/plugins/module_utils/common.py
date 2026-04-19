from __future__ import absolute_import, division, print_function
__metaclass__ = type

# ---------------------------------------------------------------------------
# SDK import
# ---------------------------------------------------------------------------

try:
    from ansible_collections.ordo_artificum.netgear.plugins.module_utils.netgear_switch import (
        Switch, PortSpeed, RateLimit, make_switch as _sdk_make_switch,
    )
    HAS_SDK = True
    SDK_ERROR = None
except ImportError as e:
    HAS_SDK = False
    SDK_ERROR = str(e)
    Switch = None
    PortSpeed = None
    RateLimit = None
    _sdk_make_switch = None


# ---------------------------------------------------------------------------
# Common argument spec — included by every module
# ---------------------------------------------------------------------------

CONNECTION_ARGS = dict(
    host=dict(type='str', required=True),
    password=dict(type='str', required=True, no_log=True),
    timeout=dict(type='float', default=10.0),
)


def make_switch(params):
    """Connect to a switch using module parameters; detects model and firmware."""
    return _sdk_make_switch(
        host=params['host'],
        password=params['password'],
        timeout=params['timeout'],
    )


# ---------------------------------------------------------------------------
# Serialisation helpers — convert SDK dataclass instances to plain dicts
# ---------------------------------------------------------------------------

def serialize_system_info(info):
    return dict(
        mac=info.mac,
        ip=info.ip,
        netmask=info.netmask,
        gateway=info.gateway,
        firmware=info.firmware,
    )


def serialize_switch_config(cfg):
    return dict(
        model=cfg.model,
        name=cfg.name,
        serial=cfg.serial,
        mac=cfg.mac,
        firmware=cfg.firmware,
        dhcp=cfg.dhcp,
        ip=cfg.ip,
        netmask=cfg.netmask,
        gateway=cfg.gateway,
    )


def serialize_port_info(p):
    return dict(
        port=p.port,
        enabled=p.enabled,
        speed_cfg=str(p.speed_cfg),
        speed_act=p.speed_act,
        fc_enabled=p.fc_enabled,
        max_mtu=p.max_mtu,
    )


def serialize_port_stats(s):
    return dict(
        port=s.port,
        bytes_rx=s.bytes_rx,
        bytes_tx=s.bytes_tx,
        crc_errors=s.crc_errors,
    )


def serialize_rate_limit(r):
    return dict(
        port=r.port,
        ingress=str(r.ingress),
        egress=str(r.egress),
        ingress_index=int(r.ingress),
        egress_index=int(r.egress),
    )


def serialize_mirror(m):
    return dict(
        enabled=m.enabled,
        dest_port=m.dest_port,
        source_ports=sorted(m.source_ports),
    )


def serialize_igmp(igmp):
    return dict(
        enabled=igmp.enabled,
        vlan_id=igmp.vlan_id,
        validate_ip_header=igmp.validate_ip_header,
        block_unknown_multicast=igmp.block_unknown_multicast,
        static_router_port=igmp.static_router_port,
    )


def serialize_vlan_entry(vid, membership_str):
    # '1'=untagged, '2'=tagged, '3'=not-a-member (firmware encoding; '0' is also not-a-member)
    untagged = [i + 1 for i, c in enumerate(membership_str) if c == '1']
    tagged   = [i + 1 for i, c in enumerate(membership_str) if c == '2']
    return dict(
        vid=vid,
        membership=membership_str,
        untagged_ports=untagged,
        tagged_ports=tagged,
    )
