# -*- coding: utf-8 -*-
VERSION="0.9.1"

import db
import platform
import wx
import locale
import ObjectListView as OLV
import subprocess
import sys
import datetime
import esky
import time
from MyOLV import MyOLV, ColumnDefn
from wx import xrc
from elixir import *
from wx.lib.pubsub import setupkwargs
from wx.lib.pubsub import pub
from controllers import *
import stopwatch
import network
import csvexport
from datetime import date

from twisted.internet import reactor, protocol
from twisted.spread import pb
import twisted
import logging

class App(wx.App):

  def OnInit(self):
    if platform.system() == 'Linux':
      locale.setlocale(locale.LC_ALL, 'cs_CZ.UTF-8')
    elif platform.system() == 'Windows':
      locale.setlocale(locale.LC_ALL, 'czech')
    self.locale = wx.Locale(wx.LANGUAGE_CZECH)

    self.res = xrc.XmlResource('agility.xrc')
    self.frame = self.res.LoadFrame(None, 'mainFrame')
    self.teamDialog = self.res.LoadDialog(self.frame, 'teamDialog')
    self.runDialog = self.res.LoadDialog(self.frame, 'runDialog')
    self.competitionSettingsDialog = self.res.LoadDialog(self.frame, 'competitionSettingsDialog')

    self.twistedThread = network.TwistedThread()
    self.twistedThread.start()

    self.connected = False

    self._initOLV()

    self.startupDialog = self.res.LoadDialog(self.frame, 'startupDialog')
    self.startupDialog.Bind(wx.EVT_BUTTON, self.OnOpenFile, id=xrc.XRCID("openButton"))
    self.startupDialog.Bind(wx.EVT_BUTTON, self.OnNewFile, id=xrc.XRCID("createButton"))
    self.startupDialog.Bind(wx.EVT_BUTTON, self.OnConnect, id=xrc.XRCID("connectButton"))

    network.EVT_RELOAD(self, self.OnReload)
    network.EVT_CALLBACK(self, self.OnCallback)
    network.EVT_WAITING(self, self.OnWaiting)

    self.fireMessages = True
    self.exiting = False
    if self.startupDialog.ShowModal() == wx.ID_CANCEL:
      self.OnClose()
    return True

  def OnAbout(self, evt=None):
    info = wx.AboutDialogInfo()
    info.Name = "Agility"
    info.Version = VERSION
    #info.Copyright = "(C) 2011"
    info.WebSite = ("http://www.kacr.info", "www.kacr.info")
    #info.Developers = []
    #info.License = wordwrap("Completely and totally open source!", 500,
    #                        wx.ClientDC(self.panel))
    wx.AboutBox(info)

  def OnClose(self, evt=None):
    #TODO: have a nice dialog here
    if not self.exiting:
      self.exiting = True
      self.fireMessages = False
      self.frame.Destroy()
      reactor.stop()

  def OnPageChange(self, evt):
    if self.fireMessages:
      wx.CallAfter(pub.sendMessage, "page_changed", id=None)
    evt.Skip()

  def OnReload(self, evt):
    if self.fireMessages:
      pub.sendMessage(evt.what, id=evt.arg)

  def OnCallback(self, evt):
    evt.callback(*evt.args, **evt.kwargs)

  def OnWaiting(self, evt):
    if evt.value:
      wx.BeginBusyCursor()
    else:
      wx.EndBusyCursor()

  def _startServer(self):
    server = network.ServerResponder()
    reactor.listenTCP(8787, pb.PBServerFactory(server))
    reactor.addSystemEventTrigger("before", "shutdown", server.Close)
    self._connect("localhost")

  def _connect(self, addr):
    reactor.callFromThread(Client().Connect, addr, 8787, self, lambda: wx.PostEvent(self, network.CallbackEvent(self.OnConnected)))

  def OnOpenFile(self, evt):
    dlg = wx.FileDialog(None, message=u'Otevřít závod', wildcard=u"Závody agility (*.agi)|*.agi", style=wx.FD_OPEN)
    if dlg.ShowModal() == wx.ID_OK and dlg.GetPath():
      db.OpenFile(dlg.GetPath())
      self._startServer()

  def OnNewFile(self, evt):
    def conv_date(date):
      t = map(lambda x: int(x), date.FormatISODate().split('-'))
      return datetime.date(*t)

    dlg = wx.FileDialog(None, message=u'Vyberte název souboru', wildcard=u"Závody agility (*.agi)|*.agi", style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
    if dlg.ShowModal() == wx.ID_OK and dlg.GetPath():
      name = self.startupDialog.FindWindowByName("competition_name").GetValue()
      date_from = conv_date(self.startupDialog.FindWindowByName("date_from").GetValue())
      date_to = conv_date(self.startupDialog.FindWindowByName("date_to").GetValue())
      params = {"competition_name":name, "date_from":date_from, "date_to":date_to}
      db.OpenFile(dlg.GetPath(), params)
      self._startServer()

  def OnConnected(self, arg = None):
    if not self.connected:
      self._initLocal()
      self.startupDialog.EndModal(wx.ID_OK)
      self.frame.SetSize((900, 600))
      self.connected = True
      self.frame.Show()

  def OnConnect(self, evt = None):
    addr = self.startupDialog.FindWindowByName("clientAddress").GetValue()
    self._connect(addr)

  def _initLocal(self):
    entryPanel = self.frame.FindWindowByName("entryPanel")
    mistakes = floatspin.FloatSpin(entryPanel, -1, min_val=0, max_val=10, increment=1, value=0, digits=0)
    refusals = floatspin.FloatSpin(entryPanel, -1, min_val=0, max_val=10, increment=1, value=0, digits=0)
    self.res.AttachUnknownControl('mistakes', mistakes)
    self.res.AttachUnknownControl('refusals', refusals)

    self.entryController = EntryController(None, entryPanel)
    self.teamController = TeamController(self.teamDialog, self.frame.FindWindowByName("teamPanel"))
    self.resultController = ResultController(None, self.frame.FindWindowByName("resultPanel"))
    self.sumsController = SumsController(None, self.frame.FindWindowByName("sumsPanel"))
    self.startController = StartController(None, self.frame.FindWindowByName("startPanel"), self.res.LoadMenu('startContext'))
    self.runController = RunController(self.runDialog, self.frame.FindWindowByName("runPanel"))
    self.settingsController = SettingsController(self.competitionSettingsDialog)

    self.frame.Bind(wx.EVT_MENU, self.teamController.OnRandomizeStartNums, id=xrc.XRCID("randomizeStartNums"))
    self.frame.Bind(wx.EVT_MENU, self.settingsController.OnCompetitionSettings, id=xrc.XRCID("competitionSettings"))
    self.frame.Bind(wx.EVT_MENU, self.teamController.OnImportTeams, id=xrc.XRCID("importTeams"))
    self.frame.Bind(wx.EVT_MENU, self.entryController.OnConnectSimpleStopwatch, id=xrc.XRCID("connectSimpleStopwatch"))
    self.frame.Bind(wx.EVT_MENU, self.entryController.OnConnectAdvancedStopwatch, id=xrc.XRCID("connectAdvancedStopwatch"))
    self.frame.Bind(wx.EVT_MENU, self.OnAbout, id=xrc.XRCID("aboutMenu"))
    self.frame.Bind(wx.EVT_MENU, self.OnExport, id=xrc.XRCID("csvExport"))
    self.frame.Bind(wx.EVT_CLOSE, self.OnClose)
    self.frame.FindWindowByName("notebook").Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChange)

  def _initOLV(self):
    self.teamList = MyOLV(self.frame, wx.LC_SINGLE_SEL)
    self.res.AttachUnknownControl('teamList', self.teamList)
    self.runList = MyOLV(self.frame, wx.LC_SINGLE_SEL)
    self.res.AttachUnknownControl('runList', self.runList)
    self.startList = MyOLV(self.frame, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('startList', self.startList)
    self.entryList = MyOLV(self.frame, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('entryList', self.entryList)
    self.resultList = MyOLV(self.frame, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('resultList', self.resultList)
    self.sumsChooser = MyOLV(self.frame, 0, sortable=False)
    self.res.AttachUnknownControl('sumsChooser', self.sumsChooser)
    self.sumsList = MyOLV(self.frame, 0, sortable=False)
    self.res.AttachUnknownControl('sumsList', self.sumsList)
    self.runDialogSortList = MyOLV(self.runDialog, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('sort_run_id', self.runDialogSortList, self.runDialog)
    self.runDialogBreedList = MyOLV(self.runDialog, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('breedList', self.runDialogBreedList, self.runDialog)
    self.teamDialogPresentList = MyOLV(self.teamDialog, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('presentList', self.teamDialogPresentList, self.teamDialog)

  @inlineCallbacks
  def OnExport(self, evt):
    dlg = wx.FileDialog(None, message=u'Vyberte soubor', wildcard=u"*.csv", style=wx.FD_SAVE|wx.FD_OVERWRITE_PROMPT)
    if dlg.ShowModal() == wx.ID_OK and dlg.GetPath():
      wx.BeginBusyCursor()
      filename = dlg.GetPath()
      csvexport.CsvExport(filename)
      wx.EndBusyCursor()
    dlg.Destroy()

def main():
  twisted.python.log.startLogging(open('network.log', 'w'), setStdout=False)
  logging.basicConfig(filename="err.log",level=logging.DEBUG, filemode="w")
  try:
    app = App(redirect=False)
    app.MainLoop()
  except:
    logging.exception("Error!")

if __name__ == '__main__':
  main()

