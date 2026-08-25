# -*- coding: utf-8 -*-
# rechercheIncrementale.py 
# Version 2023.02.08

import addonHandler
import globalPluginHandler
import speech
import api
import ui
import controlTypes
from logHandler import log
import inputCore
import ctypes
import core
import textInfos
from scriptHandler import script

addonHandler.initTranslation()

try:
	REASON_CARET = controlTypes.OutputReason.CARET
except AttributeError:
	# NVDA < 2021.1
	REASON_CARET = controlTypes.REASON_CARET


SEARCH_TIMEOUT_MS = 4000


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	scriptCategory = _("Accessolutions")

	def __init__(self):
		super().__init__()
		self.searchString = ""
		self._searchCount = 0
		self._searchActive = False
		self._treeInterceptor = None
		self._lastSearchedText = None

	@script(
		description=_("Lance une recherche incrémentale virtuelle dans un document web."),
		gesture="kb:control+i",
	)
	def script_rechercheIncrementale(self, gesture):
		focus = api.getFocusObject()
		treeInterceptor = getattr(focus, "treeInterceptor", None)
		if treeInterceptor is None or not getattr(treeInterceptor, "isReady", True):
			ui.message(_("La recherche incrémentale est disponible uniquement dans un document web prêt."))
			return
		manager = inputCore.manager
		if manager is None:
			ui.message(_("La recherche incrémentale n'est pas disponible actuellement."))
			return
		currentCapture = getattr(manager, "_captureFunc", None)
		if currentCapture is not None and currentCapture != self._captureFunc:
			ui.message(_("Impossible de démarrer la recherche pendant une autre capture clavier."))
			return
		if self._searchActive:
			self._cancelSearch()
		webAccess = getattr(treeInterceptor, "webAccess", None)
		if webAccess is not None:
			webAccess.zone = None
		treeInterceptor.passThrough = False
		self.searchString = ""
		self._lastSearchedText = None
		self._treeInterceptor = treeInterceptor
		self._searchActive = True
		# NVDA ne fournit pas d'API publique pour capturer temporairement les gestes.
		# L'accès privé est donc isolé et vérifié afin de ne jamais remplacer une
		# capture appartenant à NVDA ou à une autre extension.
		manager._captureFunc = self._captureFunc
		ui.message(_("Recherche incrémentale activée."))
		self._scheduleSearch()

	def _releaseCapture(self):
		manager = inputCore.manager
		if manager is not None and getattr(manager, "_captureFunc", None) == self._captureFunc:
			manager._captureFunc = None
		self._searchActive = False

	def _scheduleSearch(self):
		self._searchCount += 1
		count = self._searchCount
		# Le délai nul laisse NVDA terminer le traitement de la frappe avant de
		# déplacer le curseur virtuel et de parler la ligne trouvée.
		core.callLater(0, self._performSearch, count, self.searchString)
		core.callLater(SEARCH_TIMEOUT_MS, self.stopSearch, count)

	def _getCurrentTreeInterceptor(self):
		focus = api.getFocusObject()
		return getattr(focus, "treeInterceptor", None)

	def _getGestureIdentifier(self, gesture):
		identifiers = [
			identifier for identifier in gesture.normalizedIdentifiers
			if identifier.startswith("kb")
		]
		return min(identifiers, key=len) if identifiers else None

	def _getCharacter(self, gesture):
		vkCode = getattr(gesture, "vkCode", None)
		scanCode = getattr(gesture, "scanCode", None)
		if vkCode is None or scanCode is None:
			return ""
		keyStates = (ctypes.c_ubyte * 256)()
		user32 = ctypes.windll.user32
		if not user32.GetKeyboardState(keyStates):
			return ""
		charBuf = ctypes.create_unicode_buffer(8)
		focus = api.getFocusObject()
		threadId = getattr(focus, "windowThreadID", 0)
		hkl = user32.GetKeyboardLayout(threadId)
		result = user32.ToUnicodeEx(
			vkCode,
			scanCode,
			keyStates,
			charBuf,
			len(charBuf),
			0x4,
			hkl,
		)
		return charBuf[:result] if result > 0 else ""

	def _captureFunc(self, gesture):
		if not self._searchActive:
			return True
		if self._getCurrentTreeInterceptor() is not self._treeInterceptor:
			# Le document a changé : ne jamais appliquer la requête à un autre document.
			self._releaseCapture()
			self._treeInterceptor = None
			return True
		if gesture.isModifier:
			return True
		gestureIdentifier = self._getGestureIdentifier(gesture)
		if gestureIdentifier is None:
			self._releaseCapture()
			self._treeInterceptor = None
			return True
		main = gestureIdentifier.split(":", 1)[1]

		if main in ("escape", "esc"):
			self._cancelSearch()
			return False
		if main == "enter":
			self.stopSearch(self._searchCount)
			return False
		if main in ("tab", "shift+tab"):
			self.stopSearch(self._searchCount)
			return True
		if main == "backspace":
			self.searchString = self.searchString[:-1]
			self._scheduleSearch()
			return False

		try:
			character = self._getCharacter(gesture)
		except Exception:
			log.exception("getCharacter")
			character = ""
		if character:
			self.searchString += character
			log.info(u"Recherche incrémentale : %s", self.searchString)
			self._scheduleSearch()
			return False

		# Une commande non textuelle met fin à la capture sans bloquer NVDA.
		self.stopSearch(self._searchCount)
		return True

	def _performSearch(self, count, searchText):
		if (
			count != self._searchCount
			or not self._searchActive
			or searchText != self.searchString
		):
			return
		if not searchText:
			self._lastSearchedText = ""
			return
		if self._getCurrentTreeInterceptor() is not self._treeInterceptor:
			self._releaseCapture()
			self._treeInterceptor = None
			return

		treeInterceptor = self._treeInterceptor
		try:
			info = treeInterceptor.makeTextInfo(textInfos.POSITION_FIRST)
			found = info.find(searchText, caseSensitive=False)
			self._lastSearchedText = searchText
			speech.cancelSpeech()
			if not found:
				ui.message(_("%s introuvable") % searchText)
				return

			# La sélection et la lecture restent virtuelles : aucune fenêtre n'est
			# créée et aucune touche n'est envoyée à la page web.
			treeInterceptor.selection = info
			lineInfo = info.copy()
			lineInfo.expand(textInfos.UNIT_LINE)
			speech.speakTextInfo(
				lineInfo,
				unit=textInfos.UNIT_LINE,
				reason=REASON_CARET,
			)
		except Exception:
			ui.message(_("Une erreur est survenue pendant la recherche."))
			log.exception("Recherche incrémentale impossible")

	def stopSearch(self, count):
		if count != self._searchCount or not self._searchActive:
			return

		if self.searchString and self._lastSearchedText != self.searchString:
			self._performSearch(count, self.searchString)
			if not self._searchActive:
				return

		searchText = self.searchString
		self._releaseCapture()
		self._treeInterceptor = None
		self._searchCount += 1
		if not searchText:
			speech.cancelSpeech()
			speech.speakMessage(_("Recherche annulée."))

	def _cancelSearch(self):
		if not self._searchActive:
			return
		self._searchCount += 1
		self._releaseCapture()
		self._treeInterceptor = None
		self.searchString = ""
		self._lastSearchedText = None
		speech.cancelSpeech()
		speech.speakMessage(_("Recherche annulée."))

	def terminate(self):
		self._searchCount += 1
		self._releaseCapture()
		self._treeInterceptor = None
	