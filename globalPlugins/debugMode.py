# -*- coding: utf-8 -*-
# Activation et désactivation temporaire de la journalisation de débogage.

import addonHandler
import logging
import logHandler
import globalPluginHandler
import ui
import scriptHandler

addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	scriptCategory = _("Accessolutions")

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		self._previousLogLevel = None

	@scriptHandler.script(
		description=_("Activer ou désactiver la journalisation de débogage temporaire."),
		gesture="kb:windows+control+shift+d",
	)
	def script_toggleDebugLogging(self, gesture):
		if self._previousLogLevel is None:
			if logHandler.isLogLevelForced():
				ui.message(_("La journalisation de NVDA est contrôlée par les options de démarrage."))
				return

			self._previousLogLevel = logHandler.log.getEffectiveLevel()
			logging.getLogger().setLevel(logging.DEBUG)
			ui.message(_("Journalisation de débogage activée temporairement."))
			return

		logging.getLogger().setLevel(self._previousLogLevel)
		self._previousLogLevel = None
		ui.message(_("Journalisation de débogage désactivée."))

	def terminate(self):
		if self._previousLogLevel is not None:
			if not logHandler.isLogLevelForced():
				logging.getLogger().setLevel(self._previousLogLevel)
			self._previousLogLevel = None
