# Juju prometheus Ceph exporter charm

Based on https://github.com/digitalocean/ceph_exporter

# Introduction and Preparation
The charm implements ceph-exporter functionality for Prometheus.
It uses a snap package, and the charm needs to be deployed where Ceph is running.
The charm needs to talk to Ceph, so a special read-only account is needed for it to work correctly:
       
    sudo ceph auth add client.exporter mon 'allow r'
    sudo ceph auth get client.exporter -o /etc/ceph/ceph.client.exporter.keyring

# Before building the charm

On the MAAS host:

    mkdir -p layers interfaces charms/xenial
    export JUJU_REPOSITORY=$PWD/charms
    export INTERFACE_PATH=$PWD/interfaces

# Build the charm

    charm build

# Deploy the charm

    juju deploy local:xenial/prometheus-ceph-exporter
    juju add-relation prometheus prometheus-ceph-exporter


TODO/Wishlist:
- Create the Ceph user directly via the Charm
- Exporter PORT as a parameter (For now it is hardcoded as 9128)
