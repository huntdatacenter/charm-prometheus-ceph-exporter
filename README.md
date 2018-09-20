# Juju prometheus Ceph exporter charm
Based on https://github.com/digitalocean/ceph_exporter

# Introduction and Preparation
The charm implements ceph-exporter functionality for Prometheus, it consumes the prometheus-ceph-exporter snap package,
Charm needs to be deployed where Ceph is running, a special read-only account ("exporter") will be created by the charm.
Since the snap is confined to his own filesystem, ceph config file and "exporter" keyring will be created in ($SNAP_DATA) :

   /var/snap/prometheus-ceph-exporter/current/

# How to Deploy:

From the MAAS host:

    export JUJU_REPOSITORY=$PWD/charms
    export INTERFACE_PATH=$PWD/interfaces

# Build the charm

    charm build -s xenial

# Deploy the charm

    juju deploy local:xenial/prometheus-ceph-exporter
    juju add-relation prometheus-ceph-exporter ceph-mon:client

To change the port, refer to the daemon_arguments provided by the snap package at:
    /var/snap/prometheus-ceph-exporter/current/daemon_arguments

# Testing

This charm implements amulet testing which can be run to deploy and verify the
charm. With an available environment run the tests with the command:

    tox -e amulet

Amulet tests must be run from within a fully built charm folder. If you have
downloaded this charm from source instead of the charmstore it is a layered
charm and must be built and tests run from the build directory. Be aware timers
are used to allow for deployment, if your environment has a particularly slow
time to deploy nodes or blocks packages from installing this can cause failure
for the amulet test.

Amulet tests also require a working juju environment and juju-deployer to run.
Juju can be installed via snap and amulet via pip with with:

    sudo snap install juju --classic
    sudo pip install bundletester

Unit testing  has been stubbed out but does not include comprehensive tests at
this time. When available unit tests can be run with:

    tox -e unit

Unit tests do not deploy the charm and do not require building prior to running
the test suite.
