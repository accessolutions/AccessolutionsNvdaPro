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
		self._lastSearchText = ""
		self._lastSearchTreeInterceptor = None

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
		self._clearLastSearch()
		self._treeInterceptor = treeInterceptor
		self._searchActive = True
		# NVDA ne fournit pas d'API publique pour capturer temporairement les gestes.
		# L'accès privé est donc isolé et vérifié afin de ne jamais remplacer une
		# capture appartenant à NVDA ou à une autre extension.
		manager._captureFunc = self._captureFunc
		ui.message(_("Recherche incrémentale activée."))
		self._scheduleSearch()

	@script(
		description=_("Recherche l'occurrence suivante du dernier texte recherché."),
		gesture="kb:f3",
	)
	def script_findNext(self, gesture):
		if self._findRelative(reverse=False):
			return
		self._delegateFind("script_findNext", gesture)

	@script(
		description=_("Recherche l'occurrence précédente du dernier texte recherché."),
		gesture="kb:shift+f3",
	)
	def script_findPrevious(self, gesture):
		if self._findRelative(reverse=True):
			return
		self._delegateFind("script_findPrevious", gesture)

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

	def _clearLastSearch(self):
		self._lastSearchText = ""
		self._lastSearchTreeInterceptor = None

	def _delegateFind(self, scriptName, gesture):
		treeInterceptor = self._getCurrentTreeInterceptor()
		findScript = getattr(treeInterceptor, scriptName, None)
		if findScript is not None:
			findScript(gesture)

	def _getGestureIdentifier(self, gesture):
		identifiers = [
			identifier for identifier in gesture.normalizedIdentifiers
			if identifier.startswith("kb")
		]
		return min(identifiers, key=len) if identifiers else None

	def _getCharacter(self, gesture):
		# KeyboardInputGesture.character utilise la conversion officielle de NVDA.
		# Elle tient compte du thread de la fenêtre focalisée, de la disposition
		# active, des modificateurs, des touches mortes et d'AltGr. Une conversion
		# locale avec ToUnicodeEx risquerait notamment de transformer 1 en & sur
		# un clavier français.
		return getattr(gesture, "character", "") or ""

	def _findFromStart(self, treeInterceptor, searchText):
		info = treeInterceptor.makeTextInfo(textInfos.POSITION_FIRST)
		try:
			# TextInfo.find() ignore volontairement la position courante. Pour ne
			# pas ignorer une occurrence située au tout début du document, traiter
			# explicitement le premier paragraphe.
			firstParagraph = info.copy()
			firstParagraph.expand(textInfos.UNIT_PARAGRAPH)
			if (firstParagraph.text or "").casefold().startswith(searchText.casefold()):
				start = firstParagraph.moveToCodepointOffset(0)
				return start, True
		except (AttributeError, LookupError, NotImplementedError, RuntimeError, ValueError):
			# Certains documents ne prennent pas en charge toutes les opérations
			# de positionnement par point de code. La recherche native reste alors
			# le meilleur mécanisme de repli.
			pass
		return info, info.find(searchText, caseSensitive=False)

	def _announceSearchResult(self, treeInterceptor, info):
		lineInfo = info.copy()
		lineInfo.expand(textInfos.UNIT_LINE)
		treeInterceptor.selection = info
		speech.speakTextInfo(
			lineInfo,
			unit=textInfos.UNIT_LINE,
			reason=REASON_CARET,
		)

		# Lire aussi la suite du paragraphe sans répéter la ligne déjà annoncée.
		try:
			paragraphInfo = info.copy()
			paragraphInfo.expand(textInfos.UNIT_PARAGRAPH)
			paragraphRemainder = paragraphInfo.copy()
			paragraphRemainder.setEndPoint(lineInfo, "startToEnd")
			if (paragraphRemainder.text or "").strip():
				speech.speakTextInfo(
					paragraphRemainder,
					unit=textInfos.UNIT_PARAGRAPH,
					reason=REASON_CARET,
				)
		except Exception:
			log.debugWarning("Lecture du reste du paragraphe impossible", exc_info=True)

	def _findRelative(self, reverse):
		treeInterceptor = self._lastSearchTreeInterceptor
		searchText = self._lastSearchText
		if treeInterceptor is None or not searchText:
			return False
		if self._getCurrentTreeInterceptor() is not treeInterceptor:
			self._clearLastSearch()
			return False

		try:
			try:
				info = treeInterceptor.makeTextInfo(textInfos.POSITION_SELECTION)
			except (AttributeError, LookupError, NotImplementedError, RuntimeError):
				info = treeInterceptor.makeTextInfo(textInfos.POSITION_CARET)
			# OffsetsTextInfo.find() ignore la position courante. Replier au
			# début pour avancer et à la fin pour reculer évite de sauter une
			# occurrence adjacente selon le sens de recherche demandé.
			info.collapse(end=reverse)
			found = info.find(searchText, caseSensitive=False, reverse=reverse)
			speech.cancelSpeech()
			if not found:
				ui.message(_("%s introuvable") % searchText)
				return True
			self._announceSearchResult(treeInterceptor, info)
			return True
		except Exception:
			ui.message(_("Une erreur est survenue pendant la recherche."))
			log.exception("Recherche relative impossible")
			return True

	def _captureFunc(self, gesture):
		if not self._searchActive:
			return True
		if self._getCurrentTreeInterceptor() is not self._treeInterceptor:
			# Le document a changé : ne jamais appliquer la requête à un autre document.
			self._releaseCapture()
			self._treeInterceptor = None
			self._clearLastSearch()
			return True
		if gesture.isModifier:
			return True
		gestureIdentifier = self._getGestureIdentifier(gesture)
		if gestureIdentifier is None:
			self._releaseCapture()
			self._treeInterceptor = None
			self._clearLastSearch()
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
		if main in ("f3", "shift+f3"):
			if not self.searchString:
				self._releaseCapture()
				self._treeInterceptor = None
				return True
			self.stopSearch(self._searchCount)
			reverse = main == "shift+f3"
			return not self._findRelative(reverse)
		if main == "backspace":
			self.searchString = self.searchString[:-1]
			self._scheduleSearch()
			return False

		try:
			character = self._getCharacter(gesture)
		except Exception:
			log.exception("getCharacter")
			character = ""
		if character and all(char.isprintable() for char in character):
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
			self._clearLastSearch()
			return
		if self._getCurrentTreeInterceptor() is not self._treeInterceptor:
			self._releaseCapture()
			self._treeInterceptor = None
			self._clearLastSearch()
			return

		treeInterceptor = self._treeInterceptor
		try:
			info, found = self._findFromStart(treeInterceptor, searchText)
			self._lastSearchedText = searchText
			speech.cancelSpeech()
			if not found:
				self._clearLastSearch()
				ui.message(_("%s introuvable") % searchText)
				return

			# La sélection et la lecture restent virtuelles : aucune fenêtre n'est
			# créée et aucune touche n'est envoyée à la page web.
			self._lastSearchText = searchText
			self._lastSearchTreeInterceptor = treeInterceptor
			self._announceSearchResult(treeInterceptor, info)
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
			self._clearLastSearch()
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
		self._clearLastSearch()
		speech.cancelSpeech()
		speech.speakMessage(_("Recherche annulée."))

	def terminate(self):
		self._searchCount += 1
		self._releaseCapture()
		self._treeInterceptor = None
		self._clearLastSearch()

