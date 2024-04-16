# *-* coding: utf8 *-*
# Version 2024.04.16

import os
import re
from urllib import request, parse
import wx
from logHandler import log
import api
import globalPluginHandler
import gui

def askRemote():
	username = os.getenv("username")
	computername = os.getenv("computername")
	params = {
		"username": username,
		"computername": computername
	}
	url = "https://accessolutions.fr/nvdaremote"
	data = parse.urlencode(params).encode()
	try:
		with request.urlopen(url, data=data) as reponse:
			urlRedirection = reponse.geturl()
			with request.urlopen(urlRedirection) as reponse_finale:
				return False, None
	except Exception as e:
		if not hasattr(e, "code"):
			log.error(e)
			return False, f"Une erreur est survenue lors de la connexion ({e.reason})."
		if e.code == 302 and e.url:
			return True, e.url
		log.error(e)
		return False, f"Une erreur est survenue lors de la connexion ({e.code}, {e.reason})."
	return False, "Une erreur est survenue lors de la connexion. Veuillez réessayer plus tard."

def getNVDARemoteURL():
	url = "https://nvdaremote.com/download/"
	try:
		response = request.urlopen(url)
		webContent = response.read().decode('utf-8')
		addon_url_match = re.search(r'https?://.*?\.nvda-addon', webContent)
		if addon_url_match:
			return addon_url_match.group(0)
	except Exception as e:
		log.error(e)
	return None


def runRemote ():
	remote = None
	for g in globalPluginHandler.runningPlugins:
		if hasattr (g, "connect_as_slave"):
			remote = g
			break
	if remote is None:
		msg = "NVDA Remote non installé ou non activé. Souhaitez-vous l'installer ?"
		if gui.messageBox(msg, "Assistance Accessolutions", wx.YES|wx.NO) == wx.YES:
			url = getNVDARemoteURL()
			if url:
				tmp_dir = os.path.join(os.getenv("TEMP"), "NVDARemote.nvda-addon")
				with request.urlopen(url) as response, open(tmp_dir, "wb") as f:
					f.write(response.read())
				os.startfile(tmp_dir)
			else:
				gui.messageBox("Impossible de récupérer l'URL de téléchargement de NVDA Remote.", "Assistance Accessolutions - erreur", wx.OK | wx.ICON_ERROR)
		return
	if remote.is_connected ():
		if gui.messageBox(u"Voulez-vous vous déconnecter ?",
						"Assistance Accessolutions",
						wx.YES|wx.NO | wx.CANCEL) !=wx.YES:
			return
		remote.disconnect ()
		return
	if gui.messageBox(u"Voulez-vous vous connecter à l'assistance Accessolutions ? Votre nom d'utilisateur et le nom de votre ordinateur seront transmis à l'opérateur.",
		"Assistance Accessolutions",
		wx.YES | wx.NO | wx.CANCEL
	) != wx.YES:
		return
	res, msg = askRemote()
	if res:
		os.startfile(msg)
	else:
		gui.messageBox(msg, "Assistance Accessolutions - erreur", wx.OK | wx.ICON_ERROR)
