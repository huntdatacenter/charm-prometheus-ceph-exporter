#!/usr/bin/python3

"""Encapsulate prometheus-ceph-exporter testing."""
import logging
import time
import unittest

import zaza.model as model

CURL_TIMEOUT = 180
REQ_TIMEOUT = 12
DEFAULT_API_PORT = "9128"
DEFAULT_API_URL = "/metrics"


class BasePrometheusCephExporterTest(unittest.TestCase):
    """Base for Prometheus-ceph-exporter charm tests."""

    @classmethod
    def setUpClass(cls):
        """Set up tests."""
        super(BasePrometheusCephExporterTest, cls).setUpClass()
        cls.model_name = model.get_juju_model()
        cls.application_name = "prometheus-ceph-exporter"
        cls.lead_unit_name = model.get_lead_unit_name(
            cls.application_name, model_name=cls.model_name
        )
        cls.units = model.get_units(cls.application_name, model_name=cls.model_name)
        cls.prometheus_ceph_exporter_ip = model.get_app_ips(cls.application_name)[0]


class CharmOperationTest(BasePrometheusCephExporterTest):
    """Verify operations."""

    def run_command(self, cmd):
        """Run a command on the lead unit, and scrape stdout."""
        result = model.run_on_unit(self.lead_unit_name, cmd)
        code = result.get("Code")
        if code != "0":
            raise model.CommandRunFailed(cmd, result)
        return result.get("Stdout")

    def tearDown(self):
        """After each test, reset the app config."""
        model.set_application_config(self.application_name, {"snap_channel": "stable"})
        model.block_until_all_units_idle()

    def test_01_api_ready(self):
        """Verify if the API is ready.

        Curl the api endpoint.
        We'll retry until the CURL_TIMEOUT.
        """
        curl_command = "curl http://localhost:{}/metrics".format(DEFAULT_API_PORT)
        timeout = time.time() + CURL_TIMEOUT
        while time.time() < timeout:
            response = model.run_on_unit(self.lead_unit_name, curl_command)
            if response["Code"] == "0":
                return
            logging.warning(
                "Unexpected curl response: {}. Retrying in 30s.".format(response)
            )
            time.sleep(30)

        # we didn't get rc=0 in the allowed time, fail the test
        self.fail(
            "Prometheus-ceph-exporter didn't respond to the command \n"
            "'{curl_command}' as expected.\n"
            "Result: {result}".format(curl_command=curl_command, result=response)
        )

    def test_02_nrpe_http_check(self):
        """Verify nrpe check exists."""
        expected_nrpe_check = (
            "command[check_prometheus_ceph_exporter_http]={} -I 127.0.0.1 -p {} -u {}"
        ).format(
            "/usr/lib/nagios/plugins/check_http", DEFAULT_API_PORT, DEFAULT_API_URL
        )
        logging.debug(
            "Verify the nrpe check is created and has the required content..."
        )
        cmd = "cat /etc/nagios/nrpe.d/check_prometheus_ceph_exporter_http.cfg"
        content = self.run_command(cmd)
        self.assertTrue(expected_nrpe_check in content)

    def test_03_snap_upgrade(self):
        """When upgrading the snap, the running version should be different."""
        cmd = "snap list prometheus-ceph-exporter | egrep 'stable|edge'"
        content = self.run_command(cmd)
        self.assertIn(
            "latest/stable", content, msg="snap version should be stable by default"
        )

        model.set_application_config(self.application_name, {"snap_channel": "edge"})
        model.block_until_all_units_idle()
        content = self.run_command(cmd)
        self.assertIn(
            "latest/edge", content, msg="snap version should be edge by config change"
        )
