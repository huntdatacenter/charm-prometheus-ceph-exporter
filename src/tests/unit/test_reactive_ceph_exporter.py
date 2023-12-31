"""Ceph exporter reactive module unit tests."""
import grp
import os
import pwd
import shutil
import tempfile
import unittest

from charmhelpers.core import unitdata
from charmhelpers.core.templating import render

import mock

import yaml

# This must be present before importing the reactive module.
os.environ["JUJU_UNIT_NAME"] = "prometheus-ceph-exporter/0"

import reactive.prometheus_ceph_exporter  # noqa: I100,E402


os.environ["CHARM_DIR"] = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)


class SimpleConfigMock(dict):
    """Config object mock for hookenv.config."""

    def __init__(self, *arg, **kw):
        """Class constructor."""
        super(SimpleConfigMock, self).__init__(*arg, **kw)
        self._changed_dict = {}
        self._changed_default = True

    def changed(self, key):
        """Return whether a config value has changed."""
        return self._changed_dict.get(key, self._changed_default)

    def set_changed(self, changed_dict):
        """Update config."""
        self._changed_dict.update(changed_dict)


class MockCephClient:
    """Mock ceph client."""

    def __init__(self, *arg, **kw):
        """Class constructor."""
        pass

    @property
    def auth(self):
        """Fake authentication."""
        return True

    def mon_hosts(self):
        """Hard-code monitor hosts."""
        return ["1.2.3.4", "5.6.7.8"]

    @property
    def key(self):
        """Hard-code ceph client key."""
        return "mockcephclientkey"


@mock.patch("os.chown")
@mock.patch("os.chmod")
@mock.patch("os.fchown")
@mock.patch("reactive.prometheus_ceph_exporter.hookenv.status_set")
@mock.patch("reactive.prometheus_ceph_exporter.hookenv.unit_get")
@mock.patch("reactive.prometheus_ceph_exporter.host.service_start")
@mock.patch("reactive.prometheus_ceph_exporter.snap.install")
@mock.patch("reactive.prometheus_ceph_exporter.host.service_running")
@mock.patch("reactive.prometheus_ceph_exporter.hookenv.config")
class TestcephExporterContext(unittest.TestCase):
    """Unit tests for the reactive module."""

    def setUp(self):
        """Pre-test setup."""
        super(TestcephExporterContext, self).setUp()
        self._init_tempdir_and_filenames()
        self._init_load_config_yml_defaults()
        self._init_override_render_for_nonroot()

    def _init_tempdir_and_filenames(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        self.maxDiff = None
        reactive.prometheus_ceph_exporter.SNAP_DATA = self.dir
        # ugly hack, to avoid carrying global unitdata state across tests
        os.environ["UNIT_STATE_DB"] = os.path.join(self.dir, ".unit-state.db")
        unitdata._KV = None
        reactive.prometheus_ceph_exporter.daemon_conf = os.path.join(
            self.dir, "daemon_conf"
        )
        reactive.prometheus_ceph_exporter.charm_ceph_conf = os.path.join(
            self.dir, "charm_ceph_conf"
        )
        reactive.prometheus_ceph_exporter.cephx_key = os.path.join(
            self.dir, "cephx_key"
        )

    def _init_load_config_yml_defaults(self):
        # create def_config with parsed config.yaml defaults
        with open(os.path.join(os.environ["CHARM_DIR"], "config.yaml"), "r") as fh:
            config_yaml = yaml.safe_load(fh)
            self.def_config = SimpleConfigMock(
                {
                    k: v["default"]
                    for k, v in config_yaml["options"].items()
                    if v.get("default")
                }
            )

    def _config_file(self, key):
        return reactive.prometheus_ceph_exporter.config_paths(key)["target"]

    def _init_override_render_for_nonroot(self):
        # need to override render() when running as non-root
        def mock_render(*args, **kwargs):
            user = pwd.getpwuid(os.geteuid()).pw_name
            group = grp.getgrgid(os.getegid()).gr_name
            render(*args, **kwargs, owner=user, group=group)

        self.mock_render = mock.patch(
            "reactive.prometheus_ceph_exporter.render", side_effect=mock_render
        )
        self.mock_render.start()
        self.addCleanup(self.mock_render.stop)

    def test_basic_config(
        self,
        _mock_hookenv_config,
        _mock_service_running,
        _mock_snap_install,
        _mock_service_start,
        *args
    ):
        """Test of the configure_exporter() method."""
        config = self.def_config
        config.update({"daemon_arguments": "foo_arguments"})
        _mock_hookenv_config.return_value = config
        _mock_service_running.return_value = True
        _mock_service_start.return_value = True
        _mock_snap_install.return_value = True
        ceph_client = MockCephClient()
        reactive.prometheus_ceph_exporter.configure_exporter(ceph_client)
        # Read the rendered files before the asserts or the tmpfile is removed
        with open(reactive.prometheus_ceph_exporter.daemon_conf, "r") as f:
            daemon_conf_content = f.read()
        with open(reactive.prometheus_ceph_exporter.charm_ceph_conf, "r") as f:
            ceph_conf_content = f.read()
        with open(reactive.prometheus_ceph_exporter.cephx_key, "r") as f:
            cephx_key_content = f.read()
        exp_daemon_conf_content = "foo_arguments"
        exp_ceph_conf_content = "mon host = 1.2.3.4 5.6.7.8"
        exp_cephx_key_content = "key = mockcephclientkey"

        self.assertIn(exp_daemon_conf_content, daemon_conf_content)
        self.assertIn(exp_ceph_conf_content, ceph_conf_content)
        self.assertIn(exp_cephx_key_content, cephx_key_content)
