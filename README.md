# Juju prometheus Ceph exporter charm

This charm provides the [Prometheus Ceph exporter](https://github.com/digitalocean/ceph_exporter), part of the [Prometheus](https://prometheus.io/) monitoring system

# Introduction and Preparation

The charm implements ceph-exporter functionality for Prometheus, it consumes the prometheus-ceph-exporter snap package,
Charm needs to be deployed where Ceph is running, a special read-only account ("exporter") will be created by the charm.
Since the snap is confined to his own filesystem, ceph config file and "exporter" keyring will be created in ($SNAP_DATA) :

```
/var/snap/prometheus-ceph-exporter/current/
```

# How to Deploy:

From the MAAS host:
```
export JUJU_REPOSITORY=$PWD/charms
export INTERFACE_PATH=$PWD/interfaces
```

# Build the charm

```
charm build -s bionic
```

# Deploy the charm

```
juju deploy local:xenial/prometheus-ceph-exporter
juju add-relation prometheus-ceph-exporter ceph-mon:client
```

To change the port, refer to the daemon_arguments provided by the snap package at:
    /var/snap/prometheus-ceph-exporter/current/daemon_arguments

# Juju resources

The charm supports juju resources, which can be handy in offline deployments.
Prefetch the snaps:
```
snap download core
snap download prometheus-ceph-exporter
```
Provide the snaps as resources to the application:

```
juju deploy cs:prometheus-ceph-exporter \
--resource prometheus-ceph-exporter=prometheus-ceph-exporter_20.snap \
--resource core=core_7917.snap
```

# Testing

This charm implements testing which can be run to deploy and verify the
charm. With an available environment run the tests with the command:

```
make test
```

Unit testing  has been stubbed out but does not include comprehensive tests at
this time. When available unit tests can be run with:

```
make unit
```

Unit tests do not deploy the charm and do not require building prior to running
the test suite.

# Contact Information
- Charm bugs: https://bugs.launchpad.net/charm-prometheus-ceph-exporter
