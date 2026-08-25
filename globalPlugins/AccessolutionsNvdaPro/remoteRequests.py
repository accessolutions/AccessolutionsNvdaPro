# -*- coding: utf-8 -*-

import os
from urllib.parse import urlencode

import addonHandler
import gui
import ui
import wx
from logHandler import log

addonHandler.initTranslation()

REMOTE_ENDPOINT = "nvdaremote://nvdaremote.accessolutions.fr/"


def _ask_for_access_key():
	dialog = wx.Dialog(
		gui.mainFrame,
		title=_("Assistance à distance Accessolutions"),
	)
	sizer = wx.BoxSizer(wx.VERTICAL)
	label = wx.StaticText(
		dialog,
		label=_("Merci de saisir la clé d'accès du support Accessolutions :"),
	)
	sizer.Add(label, 0, wx.ALL, 10)
	key_control = wx.TextCtrl(
		dialog,
		size=(400, -1),
		style=wx.TE_PROCESS_ENTER,
	)
	key_control.SetName(_("Clé d'accès du support Accessolutions"))
	sizer.Add(key_control, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

	button_sizer = wx.BoxSizer(wx.HORIZONTAL)
	cancel_button = wx.Button(dialog, wx.ID_CANCEL, _("Annuler"))
	ok_button = wx.Button(dialog, wx.ID_OK, _("OK"))
	button_sizer.Add(cancel_button, 0, wx.ALL, 5)
	button_sizer.Add(ok_button, 0, wx.ALL, 5)
	sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

	def accept_key(event):
		if not key_control.GetValue().strip():
			ui.message(_("La clé d'accès est obligatoire."))
			key_control.SetFocus()
			return
		dialog.EndModal(wx.ID_OK)

	ok_button.Bind(wx.EVT_BUTTON, accept_key)
	key_control.Bind(wx.EVT_TEXT_ENTER, accept_key)
	cancel_button.Bind(wx.EVT_BUTTON, lambda event: dialog.EndModal(wx.ID_CANCEL))
	dialog.SetEscapeId(wx.ID_CANCEL)
	ok_button.SetDefault()
	dialog.SetSizerAndFit(sizer)
	key_control.SetFocus()

	gui.mainFrame.prePopup()
	try:
		with dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return None
			return key_control.GetValue().strip()
	finally:
		gui.mainFrame.postPopup()


def _build_remote_url(access_key):
	query = urlencode({"mode": "slave", "key": access_key})
	return "%s?%s" % (REMOTE_ENDPOINT, query)


def runRemote():
	"""Demande la clé du support puis lance NVDA Remote."""
	access_key = _ask_for_access_key()
	if not access_key:
		return
	try:
		os.startfile(_build_remote_url(access_key))
	except (AttributeError, OSError) as error:
		log.exception("Impossible de lancer NVDA Remote")
		ui.message(_("Impossible de lancer NVDA Remote : %s") % error)
