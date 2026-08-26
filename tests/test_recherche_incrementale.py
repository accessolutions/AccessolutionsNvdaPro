"""Tests autonomes de la recherche incrémentielle.

NVDA n'est pas disponible dans l'environnement CI. Les dépendances NVDA sont
remplacées par des stubs minimaux afin de tester le routage et les états du
plugin sans lancer NVDA.
"""

import builtins
import importlib.util
import logging
import os
import sys
import types
import unittest
from unittest.mock import MagicMock


builtins._ = lambda text: text

addon_handler = types.ModuleType("addonHandler")
addon_handler.initTranslation = lambda: None
sys.modules["addonHandler"] = addon_handler

global_plugin_handler = types.ModuleType("globalPluginHandler")


class _GlobalPlugin:

    def __init__(self):
        pass

    def terminate(self):
        pass


global_plugin_handler.GlobalPlugin = _GlobalPlugin
sys.modules["globalPluginHandler"] = global_plugin_handler

speech = types.ModuleType("speech")
speech.cancelled = 0
speech.spoken = []
speech.messages = []
speech.cancelSpeech = lambda: setattr(speech, "cancelled", speech.cancelled + 1)
speech.speakTextInfo = lambda info, **kwargs: speech.spoken.append((info.text, kwargs))
speech.speakMessage = lambda message: speech.messages.append(message)
sys.modules["speech"] = speech

api = types.ModuleType("api")
api.focus = None
api.getFocusObject = lambda: api.focus
sys.modules["api"] = api

ui = types.ModuleType("ui")
ui.messages = []
ui.message = lambda message: ui.messages.append(message)
sys.modules["ui"] = ui

control_types = types.ModuleType("controlTypes")
control_types.OutputReason = types.SimpleNamespace(CARET="caret")
sys.modules["controlTypes"] = control_types

log_handler = types.ModuleType("logHandler")
log_handler.log = logging.getLogger("recherche_incrementale_tests")
sys.modules["logHandler"] = log_handler

input_core = types.ModuleType("inputCore")
input_core.manager = types.SimpleNamespace(_captureFunc=None)
sys.modules["inputCore"] = input_core

core = types.ModuleType("core")
core.callLater = lambda delay, callback, *args: None
sys.modules["core"] = core

text_infos = types.ModuleType("textInfos")
text_infos.POSITION_FIRST = "first"
text_infos.POSITION_CARET = "caret"
text_infos.POSITION_SELECTION = "selection"
text_infos.UNIT_LINE = "line"
text_infos.UNIT_PARAGRAPH = "paragraph"
sys.modules["textInfos"] = text_infos

script_handler = types.ModuleType("scriptHandler")
script_handler.script = lambda **kwargs: (lambda function: function)
sys.modules["scriptHandler"] = script_handler


_PLUGIN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "globalPlugins",
    "rechercheIncrementale.py",
)
_spec = importlib.util.spec_from_file_location(
    "recherche_incrementale_under_test",
    _PLUGIN_PATH,
)
recherche_incrementale = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(recherche_incrementale)


class _Focus:

    def __init__(self, tree_interceptor):
        self.treeInterceptor = tree_interceptor


class _TreeInterceptor:

    def __init__(self):
        self.isReady = True
        self.passThrough = False
        self.selection = None


class _DelegatingTree(_TreeInterceptor):

    def __init__(self):
        super().__init__()
        self.script_findNext = MagicMock()


class _Gesture:

    def __init__(self, identifier, character=""):
        self.isModifier = False
        self.normalizedIdentifiers = (identifier,)
        self.character = character


class _AnnouncementInfo:

    def __init__(self, text="correspondance"):
        self.text = text
        self.unit = None

    def copy(self):
        return _AnnouncementInfo(self.text)

    def expand(self, unit):
        self.unit = unit
        if unit == text_infos.UNIT_LINE:
            self.text = "ligne trouvée"
        elif unit == text_infos.UNIT_PARAGRAPH:
            self.text = "ligne trouvée\nsuite du paragraphe"

    def setEndPoint(self, other, which):
        del other, which
        self.text = "suite du paragraphe"


class _FirstSearchInfo:

    def __init__(self, text="alpha au début du document"):
        self.text = text
        self.find_called = False

    def copy(self):
        return _FirstSearchInfo(self.text)

    def expand(self, unit):
        del unit

    def moveToCodepointOffset(self, offset):
        del offset
        return _FirstSearchInfo("")

    def setEndPoint(self, other, which):
        del other, which
        self.text = "alpha"

    def find(self, text, **kwargs):
        del text, kwargs
        self.find_called = True
        return False


class _FirstSearchTree(_TreeInterceptor):

    def makeTextInfo(self, position):
        del position
        return _FirstSearchInfo()


class _RelativeSearchInfo:

    def __init__(self):
        self.collapse_end = None

    def collapse(self, end=False):
        self.collapse_end = end

    def find(self, text, **kwargs):
        del text, kwargs
        return True


class _RelativeSearchTree(_TreeInterceptor):

    def __init__(self):
        super().__init__()
        self.info = _RelativeSearchInfo()

    def makeTextInfo(self, position):
        del position
        return self.info


class RechercheIncrementaleTests(unittest.TestCase):

    def setUp(self):
        self.tree = _TreeInterceptor()
        api.focus = _Focus(self.tree)
        input_core.manager._captureFunc = None
        speech.spoken.clear()
        speech.messages.clear()
        ui.messages.clear()

    def _active_plugin(self):
        plugin = recherche_incrementale.GlobalPlugin()
        plugin._searchActive = True
        plugin._treeInterceptor = self.tree
        return plugin

    def test_character_uses_nvda_keyboard_translation(self):
        plugin = self._active_plugin()
        plugin._scheduleSearch = MagicMock()

        consumed = plugin._captureFunc(_Gesture("kb:1", character="1"))

        self.assertFalse(consumed)
        self.assertEqual("1", plugin.searchString)
        plugin._scheduleSearch.assert_called_once()

    def test_control_character_does_not_enter_query(self):
        plugin = self._active_plugin()
        plugin.stopSearch = MagicMock()

        passed_through = plugin._captureFunc(_Gesture("kb:control+a", character="\x01"))

        self.assertTrue(passed_through)
        self.assertEqual("", plugin.searchString)
        plugin.stopSearch.assert_called_once()

    def test_search_includes_match_at_document_start(self):
        plugin = recherche_incrementale.GlobalPlugin()
        tree = _FirstSearchTree()

        info, found = plugin._findFromStart(tree, "alpha")

        self.assertTrue(found)
        self.assertEqual("", info.text)

    def test_f3_and_shift_f3_use_incremental_search_context(self):
        for identifier, reverse in (("kb:f3", False), ("kb:shift+f3", True)):
            with self.subTest(identifier=identifier):
                plugin = self._active_plugin()
                plugin.searchString = "alpha"
                plugin._lastSearchText = "alpha"
                plugin._lastSearchTreeInterceptor = self.tree
                plugin.stopSearch = MagicMock()
                plugin._findRelative = MagicMock(return_value=True)

                consumed = plugin._captureFunc(_Gesture(identifier))

                self.assertFalse(consumed)
                plugin.stopSearch.assert_called_once_with(plugin._searchCount)
                plugin._findRelative.assert_called_once_with(reverse)

    def test_f3_delegates_to_native_search_without_context(self):
        tree = _DelegatingTree()
        api.focus = _Focus(tree)
        plugin = recherche_incrementale.GlobalPlugin()
        gesture = _Gesture("kb:f3")

        plugin.script_findNext(gesture)

        tree.script_findNext.assert_called_once_with(gesture)

    def test_relative_search_collapses_in_requested_direction(self):
        tree = _RelativeSearchTree()
        api.focus = _Focus(tree)

        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                plugin = recherche_incrementale.GlobalPlugin()
                plugin._lastSearchText = "alpha"
                plugin._lastSearchTreeInterceptor = tree
                plugin._announceSearchResult = MagicMock()

                self.assertTrue(plugin._findRelative(reverse))
                self.assertEqual(reverse, tree.info.collapse_end)

    def test_result_speaks_line_and_remaining_paragraph(self):
        plugin = recherche_incrementale.GlobalPlugin()
        info = _AnnouncementInfo()

        plugin._announceSearchResult(self.tree, info)

        self.assertEqual(info, self.tree.selection)
        self.assertEqual(2, len(speech.spoken))
        self.assertEqual("ligne trouvée", speech.spoken[0][0])
        self.assertEqual("suite du paragraphe", speech.spoken[1][0])


if __name__ == "__main__":
    unittest.main()
