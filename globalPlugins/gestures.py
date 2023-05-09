# *-* coding: utf8 *-*
# gestures.py 
# Version 2015.10.14

import globalPluginHandler
import inputCore
import os
import globalVars

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	
	def __init__ (self):
		super(globalPluginHandler.GlobalPlugin, self).__init__()
		inputCore.manager.localeGestureMap.load(os.path.abspath(os.path.join(os.path.dirname(__file__), r"gestures.ini")))
		