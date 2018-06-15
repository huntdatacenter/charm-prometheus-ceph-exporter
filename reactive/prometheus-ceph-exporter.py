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
import time

from charmhelpers.core import host, hookenv
from charmhelpers.core.templating import render
from charms.reactive import (
    when,
    when_not,
    set_state,
    remove_state,
)
from charms.reactive.helpers import any_file_changed
from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.contrib.network.ip import get_address_in_network

from charmhelpers.fetch import (
    apt_install,
)

SNAP_NAME = 'prometheus-ceph-exporter'
SVC_NAME = 'snap.prometheus-ceph-exporter.ceph-exporter'
SNAP_DATA = '/var/snap/' + SNAP_NAME + '/current/'
PORT_DEF = 9128


class ServiceError(Exception):
    pass


def templates_changed(tmpl_list):
    return any_file_changed(['templates/{}'.format(x) for x in tmpl_list])


def validate_config(filename):
    return yaml.safe_load(open(filename))


@when_not('ceph-libs-installed')
def install_libs():
    apt_install(['ceph-common', 'python-ceph'], fatal=True)
    set_state('ceph-libs-installed')


@when('snap.installed.prometheus-ceph-exporter')
@when_not('ports-open')
def open_port():
    hookenv.open_port(PORT_DEF)
    set_state('ports-open')


@when('ceph.available')
@when_not('exporter.started')
def configure_exporter(ceph_client):
    service_name = hookenv.service_name()
    daemon_conf = os.path.join(os.sep, SNAP_DATA, 'daemon_arguments')
    charm_ceph_conf = os.path.join(os.sep, SNAP_DATA, 'ceph.conf')
    cephx_key = os.path.join(os.sep, SNAP_DATA, 'ceph.client.%s.keyring' %
                             (service_name))

    ceph_context = {
        'auth_supported': ceph_client.auth(),
        'mon_hosts': ceph_client.mon_hosts(),
        'service_name': service_name,
        'ringpath': SNAP_DATA,
    }

    # Write out the ceph.conf
    render('ceph.conf', charm_ceph_conf, ceph_context)

    ceph_key_context = {
        'key': str(ceph_client.key()),
        'service_name': service_name,
    }

    # Write out the cephx_key also
    render('ceph.keyring', cephx_key, ceph_key_context)

    daemon_context = {
        'daemon_arguments': hookenv.config('daemon_arguments'),
        'service_name': service_name,
    }

    # Write out the daemon.arguments file
    render('daemon_arguments', daemon_conf, daemon_context)

    # Start ceph-exporter
    hookenv.log('Starting {}...'.format(SVC_NAME))
    host.service_start(SVC_NAME)
    time.sleep(10)  # service is type=simple can't tell if it actually started
    if host.service_running(SVC_NAME):
        hookenv.status_set('active', 'Running')
    else:
        raise ServiceError("Service didn't start: {}".format(SVC_NAME))
    set_state('exporter.started')


def get_exporter_host(interface='ceph-exporter'):
    """Get address of local ceph-exporter host for use by http clients

    If an access-network has been configured, expect selected address to be on
    that network. If none can be found, revert to primary address.

    If network spaces (Juju >= 2.0) are supported, use network-get to retrieve
    the network binding for the interface

    @param interface: Network space binding to check
                      Usually the relationship name
    @returns IP for use with http clients
    """
    access_network = hookenv.config('access-network')
    if access_network:
        return get_address_in_network(access_network)
    else:
        try:
            # NOTE(aluria)
            # Try to use network spaces to resolve binding for interface, and
            # to resolve the IP
            return hookenv.network_get_primary_address(interface)
        except NotImplementedError:
            # NOTE(aluria): skip - fallback to previous behaviour (in OS Charms)
            pass

    return hookenv.unit_get('private-address')


# Relations
@when('exporter.started')
@when('ceph-exporter.available')  # Relation name is "ceph-exporter"
def configure_ceph_exporter_relation(target):
    hostname = get_exporter_host()
    target.configure(PORT_DEF, hostname=hostname)


@when('exporter.started')
@when_not('ceph.connected')
def mon_relation_broken():
    host.service_stop(SVC_NAME)
    hookenv.status_set('blocked', 'No ceph-mon relation')
    remove_state('exporter.started')


@when('nrpe-external-master.available')
def update_nrpe_config(svc):
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe_setup.add_check('prometheus_ceph_exporter_http',
                         'Prometheus Ceph Exporter HTTP check',
                         'check_http -I 127.0.0.1 -p {} -u /metrics'.format(PORT_DEF)
                         )
    nrpe_setup.write()
