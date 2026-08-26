"""Tests indépendants de la préparation d'une connexion distante.

NVDA et wxPython ne sont pas disponibles dans l'environnement CI. Les modules
nécessaires au chargement ciblé de remoteRequests sont donc remplacés par des
stubs minimaux.
"""

import builtins
import importlib.util
import logging
import os
import sys
import types
import unittest


builtins._ = lambda text: text

addon_handler = sys.modules.setdefault("addonHandler", types.ModuleType("addonHandler"))
addon_handler.AddonError = getattr(addon_handler, "AddonError", type("AddonError", (Exception,), {}))
addon_handler.initTranslation = getattr(addon_handler, "initTranslation", lambda: None)

config = types.ModuleType("config")
config.conf = {"remote": {"enabled": False}}
sys.modules["config"] = config

global_plugin_handler = types.ModuleType("globalPluginHandler")
global_plugin_handler.runningPlugins = set()
sys.modules["globalPluginHandler"] = global_plugin_handler

gui = types.ModuleType("gui")
gui.messageBox = lambda *args, **kwargs: None
gui.mainFrame = None
sys.modules["gui"] = gui

ui = types.ModuleType("ui")
ui.messages = []
ui.message = lambda message: ui.messages.append(message)
sys.modules["ui"] = ui

wx = types.ModuleType("wx")
wx.YES = 1
wx.NO = 2
wx.NO_DEFAULT = 4
wx.ICON_WARNING = 8
sys.modules["wx"] = wx

log_handler = types.ModuleType("logHandler")
log_handler.log = logging.getLogger("remote_requests_tests")
sys.modules["logHandler"] = log_handler


_REMOTE_REQUESTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "globalPlugins",
    "AccessolutionsNvdaPro",
    "remoteRequests.py",
)
_spec = importlib.util.spec_from_file_location(
    "remote_requests_under_test",
    _REMOTE_REQUESTS_PATH,
)
remote_requests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(remote_requests)


class _FakeBackend:

    def __init__(self, state, state_after_disconnect=None):
        self.name = "fake remote"
        self.current_state = state
        self.state_after_disconnect = state_after_disconnect
        self.disconnect_calls = 0

    def state(self):
        return self.current_state

    def disconnect(self):
        self.disconnect_calls += 1
        self.current_state = (
            self.state_after_disconnect
            if self.state_after_disconnect is not None
            else remote_requests._STATE_DISCONNECTED
        )
        return True


class RemoteRequestsTests(unittest.TestCase):

    def setUp(self):
        ui.messages.clear()
        global_plugin_handler.runningPlugins.clear()
        gui.messageBox = lambda *args, **kwargs: None
        config.conf = {"remote": {"enabled": False}}

    def test_connection_state_detects_follower_session(self):
        owner = types.SimpleNamespace(
            isConnecting=False,
            followerSession=object(),
            leaderSession=None,
        )
        self.assertEqual(
            remote_requests._STATE_SLAVE,
            remote_requests._connection_state(owner),
        )

    def test_connection_state_is_unknown_without_state_api(self):
        self.assertEqual(
            remote_requests._STATE_UNKNOWN,
            remote_requests._connection_state(object()),
        )

    def test_native_backend_disconnect_is_silent(self):
        class NativeClient:

            isConnected = False
            followerSession = None
            leaderSession = None

            def __init__(self):
                self.silent = None

            def disconnect(self, _silent=False):
                self.silent = _silent

        client = NativeClient()
        backend = remote_requests._RemoteBackend("NVDA Remote", client, native=True)
        self.assertTrue(backend.disconnect())
        self.assertTrue(client.silent)

    def test_active_connection_is_disconnected_before_launch(self):
        backend = _FakeBackend(remote_requests._STATE_SLAVE)
        answers = []
        gui.messageBox = lambda *args, **kwargs: wx.YES
        old_backends = remote_requests._remote_backends
        old_ask = remote_requests._ask_for_access_key
        old_startfile = getattr(remote_requests.os, "startfile", None)
        remote_requests._remote_backends = lambda: [backend]
        remote_requests._ask_for_access_key = lambda: "cle-test"
        remote_requests.os.startfile = lambda url: answers.append(
            (url, backend.current_state)
        )
        try:
            remote_requests.runRemote()
        finally:
            remote_requests._remote_backends = old_backends
            remote_requests._ask_for_access_key = old_ask
            if old_startfile is None:
                del remote_requests.os.startfile
            else:
                remote_requests.os.startfile = old_startfile
        self.assertEqual(1, backend.disconnect_calls)
        self.assertEqual(remote_requests._STATE_DISCONNECTED, answers[0][1])
        self.assertIn("mode=slave", answers[0][0])

    def test_declining_disconnect_does_not_launch(self):
        backend = _FakeBackend(remote_requests._STATE_MASTER)
        gui.messageBox = lambda *args, **kwargs: wx.NO
        self.assertFalse(remote_requests._disconnect_active_backends([backend]))
        self.assertEqual(0, backend.disconnect_calls)

    def test_unknown_status_after_disconnect_still_launches(self):
        backend = _FakeBackend(
            remote_requests._STATE_SLAVE,
            state_after_disconnect=remote_requests._STATE_UNKNOWN,
        )
        answers = []
        gui.messageBox = lambda *args, **kwargs: wx.YES
        old_backends = remote_requests._remote_backends
        old_ask = remote_requests._ask_for_access_key
        old_startfile = getattr(remote_requests.os, "startfile", None)
        remote_requests._remote_backends = lambda: [backend]
        remote_requests._ask_for_access_key = lambda: "cle-test"
        remote_requests.os.startfile = lambda url: answers.append(url)
        try:
            remote_requests.runRemote()
        finally:
            remote_requests._remote_backends = old_backends
            remote_requests._ask_for_access_key = old_ask
            if old_startfile is None:
                del remote_requests.os.startfile
            else:
                remote_requests.os.startfile = old_startfile
        self.assertEqual(1, backend.disconnect_calls)
        self.assertEqual(1, len(answers))

    def test_no_remote_backend_still_launches(self):
        answers = []
        old_backends = remote_requests._remote_backends
        old_ask = remote_requests._ask_for_access_key
        old_startfile = getattr(remote_requests.os, "startfile", None)
        remote_requests._remote_backends = lambda: []
        remote_requests._ask_for_access_key = lambda: "cle-test"
        remote_requests.os.startfile = lambda url: answers.append(url)
        try:
            remote_requests.runRemote()
        finally:
            remote_requests._remote_backends = old_backends
            remote_requests._ask_for_access_key = old_ask
            if old_startfile is None:
                del remote_requests.os.startfile
            else:
                remote_requests.os.startfile = old_startfile
        self.assertEqual(1, len(answers))
        self.assertIn("mode=slave", answers[0])

    def test_telenvda_plugin_is_detected(self):
        plugin_type = type(
            "GlobalPlugin",
            (),
            {
                "__module__": "globalPlugins.telenvdaAccessolutions",
                "is_connected": lambda self: False,
            },
        )
        global_plugin_handler.runningPlugins.add(plugin_type())
        backends = remote_requests._remote_backends()
        self.assertEqual(1, len(backends))
        self.assertIn("telenvda", backends[0].name)

    def test_native_remote_requires_enabled_configuration(self):
        native_client = types.SimpleNamespace(
            isConnected=lambda: False,
            followerSession=None,
            leaderSession=None,
        )
        native_module = types.ModuleType("_remoteClient")
        native_module._remoteClient = native_client
        previous_module = sys.modules.get("_remoteClient")
        sys.modules["_remoteClient"] = native_module
        try:
            config.conf = {"remote": {"enabled": False}}
            self.assertIsNone(remote_requests._native_remote_backend())
            config.conf = {"remote": {"enabled": True}}
            self.assertIsNotNone(remote_requests._native_remote_backend())
        finally:
            if previous_module is None:
                del sys.modules["_remoteClient"]
            else:
                sys.modules["_remoteClient"] = previous_module


if __name__ == "__main__":
    unittest.main()
