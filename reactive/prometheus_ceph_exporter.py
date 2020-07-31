#!/usr/bin/python3
"""Installs and configures prometheus-ceph-exporter."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from zipfile import BadZipFile, ZipFile

from charmhelpers.contrib.charmsupport import nrpe
from charmhelpers.contrib.network.ip import get_address_in_network
from charmhelpers.core import hookenv, host
from charmhelpers.core.templating import render
from charms.layer import snap
from charms.reactive import (
    endpoint_from_flag,
    hook,
    remove_state,
    set_state,
    when,
    when_all,
    when_not,
)
from charms.reactive.helpers import (
    any_file_changed,
    data_changed,
)
import yaml


REACTIVE_DIR = os.path.dirname(os.path.abspath(__file__))
CHARM_DIR = os.path.dirname(REACTIVE_DIR)
DASHBOARD_PATH = os.path.join(CHARM_DIR, "templates/dashboards")
SNAP_NAME = "prometheus-ceph-exporter"
SVC_NAME = "snap.prometheus-ceph-exporter.ceph-exporter"
SNAP_DATA = "/var/snap/" + SNAP_NAME + "/current/"
PORT_DEF = 9128
service_name = hookenv.service_name()
daemon_conf = os.path.join(os.sep, SNAP_DATA, "daemon_arguments")
charm_ceph_conf = os.path.join(os.sep, SNAP_DATA, "ceph.conf")
cephx_key = os.path.join(
    os.sep, SNAP_DATA, "ceph.client.{}.keyring".format(service_name)
)


class ServiceError(Exception):
    """Exception type."""

    pass


def templates_changed(tmpl_list):
    """Return list of changed files."""
    return any_file_changed(["templates/{}".format(x) for x in tmpl_list])


def validate_config(filename):
    """Load yaml from file."""
    return yaml.safe_load(open(filename))


@when("snap.installed.prometheus-ceph-exporter")
@when_not("ports-open")
def open_port():
    """Open the ceph exporter port."""
    hookenv.open_port(PORT_DEF)
    set_state("ports-open")


@when_not("ceph.available")
@when_not("exporter.started")
def waiting_to_configure():
    """Wait for ceph relation to configure."""
    hookenv.status_set("blocked", "Waiting on ceph-mon relation")


@when("ceph.available")
@when_not("exporter.started")
def configure_exporter(ceph_client):
    """Configure the daemon."""
    hookenv.status_set("maintenance", "Installing software")

    config = hookenv.config()
    channel = config.get("snap_channel", "stable")
    snap.install(SNAP_NAME, channel=channel, force_dangerous=False)

    ceph_context = {
        "auth_supported": ceph_client.auth(),
        "mon_hosts": ceph_client.mon_hosts(),
        "service_name": service_name,
        "ringpath": SNAP_DATA,
    }
    data_changed('mon-hosts', ceph_client.mon_hosts())

    # Write out the ceph.conf
    render("ceph.conf", charm_ceph_conf, ceph_context)

    ceph_key_context = {
        "key": str(ceph_client.key()),
        "service_name": service_name,
    }
    data_changed('ceph-key', ceph_client.key())

    # Write out the cephx_key also
    render("ceph.keyring", cephx_key, ceph_key_context)

    daemon_context = {
        "daemon_arguments": hookenv.config("daemon_arguments"),
        "service_name": service_name,
    }

    # Write out the daemon.arguments file
    render("daemon_arguments", daemon_conf, daemon_context)

    # Start ceph-exporter
    hookenv.log("Starting {}...".format(SVC_NAME))
    host.service_start(SVC_NAME)
    time.sleep(10)  # service is type=simple can't tell if it actually started
    if host.service_running(SVC_NAME):
        hookenv.status_set("active", "Running")
    else:
        hookenv.status_set("error", "Service didn't start: {}".format(SVC_NAME))
        raise ServiceError("Service didn't start: {}".format(SVC_NAME))
    set_state("exporter.started")


def get_exporter_host(interface="ceph-exporter"):
    """Get address of local ceph-exporter host for use by http clients.

    If an access-network has been configured, expect selected address to be on
    that network. If none can be found, revert to primary address.

    If network spaces (Juju >= 2.0) are supported, use network-get to retrieve
    the network binding for the interface

    @param interface: Network space binding to check
                      Usually the relationship name
    @returns IP for use with http clients
    """
    access_network = hookenv.config("access-network")
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

    return hookenv.unit_get("private-address")


# Relations
@when("exporter.started")
@when("ceph-exporter.available")  # Relation name is "ceph-exporter"
def configure_ceph_exporter_relation(target):
    """Configure the http port for the scrape."""
    hostname = get_exporter_host()
    target.configure(PORT_DEF, hostname=hostname)


@when("exporter.started")
@when_not("ceph.connected")
def mon_relation_broken():
    """Check for mon relation."""
    host.service_stop(SVC_NAME)
    hookenv.status_set("blocked", "Waiting on ceph-mon relation")
    remove_state("exporter.started")


@when("exporter.started")
@when("ceph.connected")
def mon_relation_changed(ceph_client):
    """Check if mon relation has changed data/members."""
    if data_changed('mon-hosts', ceph_client.mon_hosts()) or data_changed('ceph-key', ceph_client.key()):
        host.service_stop(SVC_NAME)
        hookenv.status_set("maintenance", "Updating ceph-client configuration")
        remove_state("exporter.started")


@when("nrpe-external-master.available")
def update_nrpe_config(svc):
    """Add nrpe check."""
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe_setup.add_check(
        "prometheus_ceph_exporter_http",
        "Prometheus Ceph Exporter HTTP check",
        "check_http -I 127.0.0.1 -p {} -u /metrics".format(PORT_DEF),
    )
    nrpe_setup.write()


@when_not("nrpe-external-master.available")
def remove_nrpe_check():
    """Remove the nrpe check."""
    hostname = nrpe.get_nagios_hostname()
    nrpe_setup = nrpe.NRPE(hostname=hostname)
    nrpe_setup.remove_check(shortname="prometheus_ceph_exporter_http")


@hook("upgrade-charm")
def upgrade():
    """Reset the install state on upgrade, to ensure resource extraction."""
    hookenv.status_set("maintenance", "Charm upgrade in progress")
    update_dashboards_from_resource()
    remove_state("exporter.started")


@when_all("endpoint.dashboards.joined")
def register_grafana_dashboards():
    """After joining to grafana, push the dashboard."""
    grafana_endpoint = endpoint_from_flag("endpoint.dashboards.joined")

    if grafana_endpoint is None:
        return

    hookenv.log("Grafana relation joined, push dashboard")

    # load pre-distributed dashboards, that may havew been overwritten by resource
    dash_dir = Path(DASHBOARD_PATH)
    for dash_file in dash_dir.glob("*.json"):
        dashboard = dash_file.read_text()
        digest = hashlib.md5(dashboard.encode("utf8")).hexdigest()
        dash_dict = json.loads(dashboard)
        dash_dict["digest"] = digest
        dash_dict["source_model"] = hookenv.model_name()
        grafana_endpoint.register_dashboard(dash_file.stem, dash_dict)
        hookenv.log("Pushed {}".format(dash_file))


def update_dashboards_from_resource():
    """Extract resource zip file into templates directory."""
    dashboards_zip_resource = hookenv.resource_get("dashboards")
    if not dashboards_zip_resource:
        hookenv.log("No dashboards resource found", hookenv.DEBUG)
        # no dashboards zip found, go with the default distributed dashboard
        return

    hookenv.log("Installing dashboards from resource", hookenv.DEBUG)
    try:
        shutil.copy(dashboards_zip_resource, DASHBOARD_PATH)
    except IOError as error:
        hookenv.log("Problem copying resource: {}".format(error), hookenv.ERROR)
        return

    try:
        with ZipFile(dashboards_zip_resource, "r") as zipfile:
            zipfile.extractall(path=DASHBOARD_PATH)
            hookenv.log("Extracted dashboards from resource", hookenv.DEBUG)
    except BadZipFile as error:
        hookenv.log("BadZipFile: {}".format(error), hookenv.ERROR)
        return
    except PermissionError as error:
        hookenv.log("Unable to unzip the provided resource: {}".format(error), hookenv.ERROR)
        return

    register_grafana_dashboards()
