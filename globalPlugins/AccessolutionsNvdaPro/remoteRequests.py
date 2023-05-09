# *-* coding: utf8 *-*
# Version 2018.06.19

import globalPluginHandler
import os
import ui
import gui
import wx
from logHandler import log
import api
import speech
import random
import urllib

def runRemote ():
	remote = None
	for g in globalPluginHandler.runningPlugins:
		if hasattr (g, "connect_as_slave"):
			remote = g
			break
	if remote is None:
		ui.message (u"Le module NVDA Remote est introuvable")
		return
	if remote.is_connected ():
		if gui.messageBox(u"Voulez-vous vous déconnecter ?",
						u"Assistance Accessolutions",
						wx.YES|wx.NO | wx.CANCEL) !=wx.YES:
			return
		ui.message (u"Déconnexion")
		remote.disconnect ()
		return
	if gui.messageBox(u"Voulez-vous vous connecter à l'assistance Accessolutions ?",
		u"Assistance Accessolutions",
		wx.YES|wx.NO | wx.CANCEL) !=wx.YES:
		return
	randomKey = format ("%07d" % random.randrange (0, 9999999))
	remote.connect_as_slave(("nvdaremote.accessolutions.fr", 80), randomKey)
	session = remote.master_session or remote.slave_session
	url = session.get_connection_info().get_url_to_connect()
	winUser = os.getenv("username")
	api.copyToClip(unicode(url))
	nvdaRequests (url, winUser)
	
def nvdaRequests (url, userName):
	api_url = "http://assistance.accessolutions.fr/api/v0.1/nvda-requests" 
	nvda_remote_url = url
	win_user_name = userName
	
	data = "{\"nvda_remote_url\": \"%s\", \"win_user_name\": \"%s\"}" % (
		nvda_remote_url,
		win_user_name
		)
	opener = urllib.FancyURLopener()
	opener.addheader("Content-type", "application/json")
	f = opener.open(api_url, data)
	if f.code != 201:
		raise Exception("HTTP return code %s" % f.code)
	log.info (u"Demande d'assistance effectuée.")
