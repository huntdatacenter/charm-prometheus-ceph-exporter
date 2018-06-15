#!/usr/bin/python3

import pytest
import amulet
import requests


@pytest.fixture(scope="module")
def deploy():
    deploy = amulet.Deployment(series='xenial')
    deploy.add('prometheus-ceph-exporter')
    deploy.expose('prometheus-ceph-exporter')
    deploy.add('ceph-mon',
               charm='ceph-mon-25',
               units=1,
               )
    deploy.configure('ceph-mon', {'monitor-count': 1})
    deploy.add('prometheus',
               charm='prometheus2',
               )
    deploy.relate('prometheus-ceph-exporter:ceph', 'ceph-mon:client')
    deploy.relate('prometheus-ceph-exporter:ceph-exporter', 'prometheus:target')
    deploy.setup(timeout=1500)
    return deploy


@pytest.fixture(scope="module")
def exporter(deploy):
    return deploy.sentry['prometheus-ceph-exporter'][0]


@pytest.fixture(scope="module")
def prometheus(deploy):
    return deploy.sentry['prometheus'][0]


class TestExporter():

    def test_deploy(self, deploy):
        try:
            deploy.sentry.wait(timeout=1500)
        except amulet.TimeoutError:
            raise

    def test_exporter_metrics(self, exporter):
        page = requests.get('http://{}:9128/metrics'.format(exporter.info['public-address']))
        assert page.status_code == 200
        assert b'ceph_cache_evict_io_bytes' in page.content

    def test_prometheus_config(self, prometheus):
        config = prometheus.file_contents('/var/snap/prometheus/current/prometheus.yml')
        assert "job_name: 'prometheus-ceph-exporter'" in config
