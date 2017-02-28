import yaml

from charmhelpers.core import host, hookenv
from charmhelpers.core.templating import render
from charms.reactive import (
    when, when_not, set_state, remove_state
)
from charms.reactive.helpers import any_file_changed, data_changed
from charms.layer import snap


SNAP_NAME = 'prometheus-ceph-exporter'
SVC_NAME = 'snap.prometheus-ceph-exporter.ceph-exporter'
PORT_DEF = 9128

def templates_changed(tmpl_list):
    return any_file_changed(['templates/{}'.format(x) for x in tmpl_list])


@when_not('ceph-exporter.installed')
def install_packages():
    hookenv.status_set('maintenance', 'Installing software')
    config = hookenv.config()
    channel = config.get('snap_channel', 'stable')
    # Work around https://pad.lv/1622782
    try:
        snap.install(SNAP_NAME, channel=channel, force_dangerous=False)
    except:
        pass
    set_state('ceph-exporter.installed')
    set_state('ceph-exporter.do-check-reconfig')


def validate_config(filename):
    return yaml.safe_load(open(filename))


@when('ceph-exporter.installed')
@when('ceph-exporter.do-reconfig-yaml')
def write_ceph_exporter_config_yaml():
    config = hookenv.config()
    hookenv.open_port(PORT_DEF)
    set_state('ceph-exporter.do-restart')
    remove_state('ceph-exporter.do-reconfig-yaml')


@when('ceph-exporter.started')
def check_config():
    set_state('ceph-exporter.do-check-reconfig')


@when('ceph-exporter.do-check-reconfig')
def check_reconfig_ceph_exporter():
    config = hookenv.config()

    if data_changed('ceph-exporter.config', config):
        set_state('ceph-exporter.do-reconfig-yaml')

    remove_state('ceph-exporter.do-check-reconfig')


@when('ceph-exporter.do-restart')
def restart_ceph_exporter():
    if not host.service_running(SVC_NAME):
        hookenv.log('Starting {}...'.format(SVC_NAME))
        host.service_start(SVC_NAME)
    else:
        hookenv.log('Restarting {}, config file changed...'.format(SVC_NAME))
        host.service_restart(SVC_NAME)
    hookenv.status_set('active', 'Ready')
    set_state('ceph-exporter.started')
    remove_state('ceph-exporter.do-restart')


# Relations
@when('ceph-exporter.started')
@when('ceph-exporter.available') # Relation name is "ceph-exporter"
def configure_ceph_exporter_relation(target):
    target.configure(PORT_DEF)
