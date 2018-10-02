# *-* coding: utf8 *-*
# Version 2017.09.08

import os
import ui
import api
from logHandler import log
import speech
import wx
import gui
import addonHandler
import urllib 

def compareVersion (version1, version2):
	v1 = version1.split (".")
	v2 = version2.split (".")
	for i in range (0, 4):
		try:
			n1 = int (v1[i])
		except:
			n1 = 0 
		try:
			n2 = int (v2[i])
		except:
			n2 = 0
		if n1 > n2:
			return -1
		if n2 > n1:
			return 1
	return 0
	
def getLatestAddonInfo (name):
	info = {} 
	info["version"] = "2017.09.09"
	info["name"] = name
	info["url"] = "http://accessolutions.fr/nvda/update/%s.nvda-addon" % name
	return info
	
def autoUpdate ():
	wx.CallAfter (checkUpdate)
	
def checkUpdate (): 
	try:
		bundle = addonHandler.getCodeAddon()
	except:
		return
	name =bundle.manifest["name"]
	currentVersion =bundle.manifest["version"]
	latestInfo = getLatestAddonInfo (name)
	if latestInfo is None:
		return
	latestVersion = latestInfo["version"]
	if compareVersion (currentVersion, latestVersion) <= 0:
		return
	fileName = downloadAddon (latestInfo["url"])
	if gui.messageBox(u"Une nouvelle version %s %s est disponible, voulez-vous l'installer ?" % (name, latestVersion),
		u"Nouvelle version %s" % name,
		wx.YES|wx.NO) !=wx.YES:
		os.remove (fileName)
		return
	installAddon (fileName)
	os.remove (fileName)

def downloadAddon (url):
	fileName, header = urllib.urlretrieve (url)
	print ("file : %s" % fileName)
	print ("header : %s" % header)
	return fileName
	
def installAddon (path):
	try:
		bundle = addonHandler.AddonBundle(path)
	except:
		log.info ("Error loading addon : %s" % path)
		return False
	name=bundle.manifest['name']
	prevAddon=None
	for addon in addonHandler.getAvailableAddons():
		if not addon.isPendingRemove and name ==addon.manifest['name']:
			prevAddon=addon
			break
	if prevAddon is not None:
		prevAddon.requestRemove()
	addonHandler.installAddonBundle (bundle)
	return True
	
