# -*- coding: utf-8 -*-
# accesso_brl
# Version 2018.06.19
# Copyright Accessolutions
#A part of NonVisual Desktop Access (NVDA)
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import globalPluginHandler
import braille
import ui
import api
import config
import speech
from logHandler import log
import addonHandler

addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def script_switchBrailleGrade(self, gesture):
		table = config.conf["braille"]["translationTable"]
		if table == "fr-bfu-comp8.utb":
			config.conf["braille"]["translationTable"] = "fr-bfu-g2.ctb"
			speech.speakMessage (_("Braille abrégé"))
		elif table == "fr-bfu-g2.ctb":
			config.conf["braille"]["translationTable"] = "fr-bfu-comp8.utb"
			speech.speakMessage (_("Braille intégral"))
		else:
			ui.message (_("Table braille inconnue"))
		braille.handler.handleUpdate(api.getFocusObject ())
 

	script_switchBrailleGrade.__doc__ = _("Bascule entre braille intégral et braille abrégé")
	script_switchBrailleGrade.category = _("Braille")
	
	__gestures = {
		"kb:windows+control+b" : "switchBrailleGrade",
	}
