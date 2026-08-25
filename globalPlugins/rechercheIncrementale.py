# *-* coding: utf8 *-*
# rechercheIncrementale.py 
# Version 2023.02.08

import globalPluginHandler
import speech
import api
import ui
import controlTypes
import braille
from logHandler import log
import inputCore
import ctypes
import core
from api import getFocusObject
import textInfos
import browseMode

try:
	REASON_CARET = controlTypes.OutputReason.CARET
except AttributeError:
	# NVDA < 2021.1
	REASON_CARET = controlTypes.REASON_CARET

gCount = 0
class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	
	def __init__ (self):
		super(globalPluginHandler.GlobalPlugin, self).__init__()

	def script_rechercheIncrementale (self, gesture):
		treeInterceptor = api.getFocusObject().treeInterceptor
		treeInterceptor.webAccess.zone = None
		treeInterceptor.passThrough = False
		browseMode.reportPassThrough.last = treeInterceptor.passThrough
		if inputCore.manager._captureFunc is None:
			ui.message(u"recherche")
			self.searchString = ""
			inputCore.manager._captureFunc = self._captureFunc
			global gCount
			gCount += 1
			core.callLater(4000, self.stopSearch, gCount)

	def _captureFunc(self, gesture):
		try:
			global gCount
			gCount += 1
			core.callLater(800, self.stopSearch, gCount)
		except:
			log.exception ("")
		if gesture.isModifier:
			return True
		gestureIdentifier = None
		# Search the shortest gesture identifier (without source)
		for identifier in gesture.normalizedIdentifiers:
			if gestureIdentifier is None:
				gestureIdentifier = identifier
			elif len(identifier) < len(gestureIdentifier):
				gestureIdentifier = identifier

		source, main = inputCore.getDisplayTextForGestureIdentifier(gestureIdentifier)
		
		# récupération du caractère
		try:
			keyStates=(ctypes.c_byte*256)()
			for k in range(256):
				keyStates[k]=ctypes.windll.user32.GetKeyState(k)
			charBuf=ctypes.create_unicode_buffer(5)
			hkl=ctypes.windll.user32.GetKeyboardLayout(api.getFocusObject().windowThreadID)
			res=ctypes.windll.user32.ToUnicodeEx(gesture.vkCode,gesture.scanCode,keyStates,charBuf,len(charBuf),0x4,hkl)
			if res>0:
				for ch in charBuf[:res]:
					self.searchString += ch
		except:
			log.exception ("getCharacter") 

		if gestureIdentifier  == "kb:control+i":
			return True 
		return False
		if gestureIdentifier not in [
			"kb:tab",
			"kb:shift+tab",
			"kb:escape",
			"kb:enter",
			]:
			log.info (u"trouvé")
		elif gestureIdentifier == "kb:tab":
			return True
		elif gestureIdentifier == "kb:shift+tab":
			return True
		elif gestureIdentifier == "kb:escape":
			pass
		elif gestureIdentifier == "kb:enter":
			pass
		return False
	
		inputCore.manager._captureFunc = None
	
	def stopSearch (self, count):
		global gCount
		if count != gCount:
			return
		
		inputCore.manager._captureFunc = None
		if self.searchString == "":
			speech.speakMessage (u"Recherche annulée")
			return

		try:
			treeInterceptor = api.getFocusObject().treeInterceptor
			treeInterceptor._lastFindText = self.searchString
			info = treeInterceptor.makeTextInfo(textInfos.POSITION_FIRST)
			if info.find (self.searchString):
				treeInterceptor.selection = info
				info = info.copy ()
				info.expand(textInfos.UNIT_LINE)
				speech.cancelSpeech ()
				speech.speakTextInfo(info,unit=textInfos.UNIT_LINE,reason=REASON_CARET)
				speech.cancelSpeech ()
				speech.speakTextInfo(info,unit=textInfos.UNIT_LINE,reason=REASON_CARET)
			else:
				speech.speakMessage (u"%s introuvable" % self.searchString)
		except:
			speech.speakMessage (u"erreur")
			log.exception ("")

	__gestures = {
				"kb:control+i" : "rechercheIncrementale",
				}
	