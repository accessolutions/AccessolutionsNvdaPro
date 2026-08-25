# -*- coding: utf-8 -*-
# scripte pour OpenBook version 17 juin 2015
# (C) Accessolutions 2015

import speech
import appModuleHandler


def _getSpeechMode():
	"""Retourne le mode courant avec compatibilité NVDA ancienne et moderne."""
	try:
		return speech.getState().speechMode
	except AttributeError:
		return speech.speechMode


def _setSpeechMode(mode):
	"""Modifie le mode de parole selon l'API disponible dans NVDA."""
	try:
		setSpeechMode = speech.setSpeechMode
	except AttributeError:
		speech.speechMode = mode
	else:
		setSpeechMode(mode)


def _getSpeechModeOff():
	try:
		return speech.SpeechMode.off
	except AttributeError:
		return speech.speechMode_off


class AppModule(appModuleHandler.AppModule):

	def __init__(self):
		super(AppModule, self).__init__()
		self._speechModeBeforeOpenBook = None
		self._speechModeSaved = False

	def event_appModule_gainFocus(self):
		if not self._speechModeSaved:
			self._speechModeBeforeOpenBook = _getSpeechMode()
			self._speechModeSaved = True
		speech.cancelSpeech()
		_setSpeechMode(_getSpeechModeOff())
		
	def event_appModule_loseFocus(self):
		self._restoreSpeechMode()

	def _restoreSpeechMode(self):
		if not self._speechModeSaved:
			return
		previousMode = self._speechModeBeforeOpenBook
		try:
			_setSpeechMode(previousMode)
		finally:
			self._speechModeBeforeOpenBook = None
			self._speechModeSaved = False

	def terminate(self):
		self._restoreSpeechMode()
		super(AppModule, self).terminate()
