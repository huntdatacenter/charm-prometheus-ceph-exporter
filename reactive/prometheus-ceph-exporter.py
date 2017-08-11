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
import os

from charmhelpers.core import host, hookenv
from charmhelpers.core.templating import render
from charms.reactive import (
    when, when_any, set_state, remove_state
)
from charms.reactive.helpers import any_file_changed, data_changed
from charmhelpers.contrib.charmsupport import nrpe
# from charms.layer import snap

from charmhelpers.fetch import (
    apt_install,
)

SNAP_NAME = 'prometheus-ceph-exporter'
SVC_NAME = 'snap.prometheus-ceph-exporter.ceph-exporter'
SNAP_DATA = '/var/snap/' + SNAP_NAME + '/current/'
PORT_DEF = 9128


def templates_changed(tmpl_list):
    return any_file_changed(['templates/{}'.format(x) for x in tmpl_list])


def validate_config(filename):
    return yaml.safe_load(open(filename))


@when_any('snap.installed.prometheus-ceph-exporter',
          'ceph-exporter.do-reconfig-yaml')
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


@when('ceph.connected')
def ceph_connected(ceph_client):
    apt_install(['ceph-common', 'python-ceph'])


@when('ceph.available')
def ceph_ready(ceph_client):
    username = hookenv.config('username')
    daemon_conf = os.path.join(os.sep, SNAP_DATA, 'daemon_arguments')
    charm_ceph_conf = os.path.join(os.sep, SNAP_DATA, 'ceph.conf')
    cephx_key = os.path.join(os.sep, SNAP_DATA, 'ceph.client.%s.keyring' % (username))

    ceph_context = {
        'auth_supported': ceph_client.auth(),
        'mon_hosts': ceph_client.mon_hosts(),
        'service_name': username,
        'ringpath': SNAP_DATA,
    }

    # Write out the ceph.conf
    render('ceph.conf', charm_ceph_conf, ceph_context)

    ceph_key_context = {
        'key': str(ceph_client.key()),
        'username': username,
    }

    # Write out the cephx_key also
    render('ceph.keyring', cephx_key, ceph_key_context)

    daemon_context = {
        'daemon_arguments': hookenv.config('daemon_arguments'),
        'username': username,
    }

    # Write out the daemon.arguments file
    render('daemon_arguments', daemon_conf, daemon_context)


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


@when('nrpe-external-master.available')
def update_nrpe_config(svc):
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe_setup.add_check('prometheus_ceph_exporter_http',
                         'Prometheus Ceph Exporter HTTP check',
                         'check_http -I 127.0.0.1 -p {} -u /metrics'.format(PORT_DEF)
                         )
    nrpe_setup.write()
