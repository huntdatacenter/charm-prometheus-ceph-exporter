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

To change the port, refer to the daemon_arguments provided by the snap package at:
    /var/snap/prometheus-ceph-exporter/current/daemon_arguments

