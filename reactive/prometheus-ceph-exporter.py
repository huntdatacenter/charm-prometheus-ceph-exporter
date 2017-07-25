# Copyright 2017 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import yaml
# import subprocess
import os

from charmhelpers.core import host, hookenv
from charmhelpers.core.templating import render
from charms.reactive import (
    when, when_not, set_state, remove_state
)
from charms.reactive.helpers import any_file_changed, data_changed
from charms.layer import snap

from charmhelpers.fetch import (
    apt_install,
)

# from charmhelpers.contrib.storage.linux.ceph import (
#    send_request_if_needed,
#    is_request_complete,
#    ensure_ceph_keyring,
#    CephBrokerRq,
#    delete_keyring,
# )


SNAP_NAME = 'prometheus-ceph-exporter'
SVC_NAME = 'snap.prometheus-ceph-exporter.ceph-exporter'
SNAP_DATA = '/var/snap/' + SNAP_NAME + '/current/'
PORT_DEF = 9128


def templates_changed(tmpl_list):
    return any_file_changed(['templates/{}'.format(x) for x in tmpl_list])


@when_not('ceph-exporter.installed')
def install_packages():
    hookenv.status_set('maintenance', 'Installing software')
    config = hookenv.config()
    channel = config.get('snap_channel', 'stable')
    snap.install(SNAP_NAME, channel=channel, force_dangerous=False)
    # set_state('ceph-exporter.do-auth-config')
    set_state('ceph-exporter.installed')
    set_state('ceph-exporter.do-check-reconfig')


def validate_config(filename):
    return yaml.safe_load(open(filename))


@when('ceph-exporter.installed')
@when('ceph-exporter.do-reconfig-yaml')
def write_ceph_exporter_config_yaml():
    # config = hookenv.config()
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


# @when('ceph-exporter.do-auth-config')
# def ceph_auth_config():
#     # Working around snap confinement, creating ceph user, moving conf to snap confined environment ($SNAP_DATA)
#     hookenv.status_set('maintenance', 'Creating ceph user')
#     hookenv.log('Creating exporter ceph user')
#     subprocess.check_call(['ceph', 'auth', 'add', 'client.exporter', 'mon', "allow r"])
#     hookenv.log('Creating exporter keyring file onto {}'.format(SNAP_DATA))
#     subprocess.check_call(['ceph', 'auth', 'get', 'client.exporter', '-o', SNAP_DATA + 'ceph.client.exporter.keyring'])
#     hookenv.log('Copying ceph.conf onto {}'.format(SNAP_DATA))
#     subprocess.check_call(['cp', '/etc/ceph/ceph.conf', SNAP_DATA + 'ceph.conf'])
#     hookenv.log('Modifying snap ceph.conf to point to $SNAP_DATA')
#     subprocess.check_call(['sed', '-i', 's=/etc/ceph/=' + SNAP_DATA + '=g', SNAP_DATA + 'ceph.conf'])
#     remove_state('ceph-exporter.do-auth-config')

@when('ceph-client.connected')
def ceph_connected(ceph_client):
    apt_install(['ceph-common', 'python-ceph'])


@when('ceph-client.available')
def ceph_ready(ceph_client):
    hookenv.status_set('maintenance', 'Creating ceph user')
    charm_ceph_conf = os.path.join(os.sep, SNAP_DATA, 'ceph.conf')
    cephx_key = os.path.join(os.sep, SNAP_DATA, 'ceph.client.exporter.keyring')

    ceph_context = {
        'auth_supported': ceph_client.auth,
        'mon_hosts': ceph_client.mon_hosts,
    }

    with open(charm_ceph_conf, 'w') as cephconf:
        cephconf.write(render('ceph.conf', ceph_context))

    # Write out the cephx_key also
    with open(cephx_key, 'w') as cephconf:
        cephconf.write(ceph_client.key)


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
@when('ceph-exporter.available')  # Relation name is "ceph-exporter"
def configure_ceph_exporter_relation(target):
    target.configure(PORT_DEF)
