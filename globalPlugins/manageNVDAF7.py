# -*- coding: utf-8 -*-
"""Compatibilité NVDA+F7 pour les versions anciennes de NVDA.

Les versions modernes de NVDA permettent déjà à la commande standard de la
liste des éléments de fonctionner en mode formulaire. Le geste ne doit donc
pas être redéfini dans ces versions : une redéfinition globale peut entrer en
conflit avec le traitement natif et donner l'impression que seul F7 a été
reconnu.
"""

import addonHandler
import api
import browseMode
import globalPluginHandler
import inputCore
from logHandler import log
import scriptHandler
from scriptHandler import script

addonHandler.initTranslation()


def _needs_legacy_f7_fallback():
	"""Indique si NVDA ne sait pas propager la liste des éléments en mode formulaire."""
	elementsListScript = getattr(
		browseMode.BrowseModeTreeInterceptor,
		"script_elementsList",
		None,
	)
	return not getattr(elementsListScript, "ignoreTreeInterceptorPassThrough", False)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	@script(
		description=_("Ouvre la liste des éléments du document courant"),
		category=inputCore.SCRCAT_BROWSEMODE,
		gesture=("kb:NVDA+f7" if _needs_legacy_f7_fallback() else None),
	)
	def script_manageNVDAF7(self, gesture):
		"""Relaye le geste à l'intercepteur uniquement si NVDA en a besoin."""
		focus = api.getFocusObject()
		if focus is None:
			return
		try:
			treeInterceptor = focus.treeInterceptor
			if not treeInterceptor or not treeInterceptor.isReady:
				return
			func = treeInterceptor.getScript(gesture)
		except Exception:
			log.exception("Impossible de récupérer le script NVDA+F7")
			return
		if func:
			scriptHandler.executeScript(func, gesture)
