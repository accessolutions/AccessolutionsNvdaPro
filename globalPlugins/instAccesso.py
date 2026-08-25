"""Ouvre l’installateur officiel de NVDA.

Ce module n’installe pas l’extension Accessolutions NVDA Pro. Il conserve un
raccourci destiné aux utilisateurs qui souhaitent installer NVDA depuis une
version portable. L’extension elle-même doit être installée avec le gestionnaire
des extensions de NVDA.
"""

import addonHandler
import globalPluginHandler
import globalVars
import scriptHandler
import tones
import ui
from logHandler import log

addonHandler.initTranslation()


_MISSING = object()
_INSTALLER_DEFAULT_OPTIONS = ("enableStartOnLogon", "copyPortableConfig")


def showInstallGui():
	"""Ouvre le dialogue officiel « Installer NVDA » avec les options voulues."""
	appArgs = globalVars.appArgs
	previousValues = {
		option: getattr(appArgs, option, _MISSING)
		for option in _INSTALLER_DEFAULT_OPTIONS
	}
	try:
		# L’interface officielle lit ces valeurs lors de la création du dialogue.
		# Elles ne sont pas conservées afin de ne pas modifier les arguments de NVDA.
		for option in _INSTALLER_DEFAULT_OPTIONS:
			setattr(appArgs, option, True)
		from gui import installerGui

		installerGui.showInstallGui()
	finally:
		for option, value in previousValues.items():
			if value is _MISSING:
				delattr(appArgs, option)
			else:
				setattr(appArgs, option, value)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	@scriptHandler.script(
		description=_("Ouvre l’installateur officiel de NVDA (pas celui de l’extension)."),
		gesture="kb:windows+control+i",
	)
	def script_installNVDA(self, gesture):
		try:
			showInstallGui()
		except (AttributeError, ImportError, OSError, RuntimeError, TypeError) as error:
			log.exception("Impossible d’ouvrir l’installateur de NVDA")
			ui.message(_("Impossible d’ouvrir l’installateur de NVDA : %s") % error)
		else:
			ones.beep(1000, 50)
