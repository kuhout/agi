# -*- coding: utf-8 -*-

import db
import platform
import wx
import locale
import ObjectListView as OLV
import subprocess
from MyOLV import MyOLV, ColumnDefn
from wx import xrc
from elixir import *
from pubsub import pub
from controllers import *
import stopwatch
import network
import socket
from twisted.internet import reactor, protocol
from twisted.spread import pb

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
    self.startupDialog.Bind(wx.EVT_BUTTON, self.OnConnect, id=xrc.XRCID("connectButton"))

    network.EVT_RELOAD(self, self.OnReload)
    network.EVT_CALLBACK(self, self.OnCallback)
    network.EVT_WAITING(self, self.OnWaiting)

    self.fireMessages = True
    self.startupDialog.ShowModal()

    return True

  def OnClose(self, evt):
    if hasattr(self, 'server') and evt is not None:
      self.server.Kill()
    else:
      #TODO: have a nice dialog here
      self.fireMessages = False
      reactor.callFromThread(reactor.stop)
      self.frame.Destroy()

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

  def OnOpenFile(self, evt):
    filename = self.startupDialog.FindWindowByName("filePicker").GetPath()
    #port = int(self.startupDialog.FindWindowByName("serverPort").GetValue())
    self.server = network.ServerProcessProtocol(lambda: wx.PostEvent(self, network.CallbackEvent(lambda: self.OnConnect(addr="localhost"))))
    reactor.callFromThread(reactor.spawnProcess, self.server, "/usr/bin/env", ["/usr/bin/env", "python2", "server.py", filename])

  def OnConnected(self, arg = None):
    if not self.connected:
      self._initLocal()
      self.startupDialog.EndModal(wx.ID_OK)
      self.frame.SetSize((900, 600))
      self.connected = True
      self.frame.Show()

  def OnConnect(self, evt = None, addr = None):
    #port = int(port or self.startupDialog.FindWindowByName("clientPort").GetValue())
    addr = addr or self.startupDialog.FindWindowByName("clientAddress").GetValue()
    reactor.callFromThread(Client().Connect, addr, 8787, self, lambda: wx.PostEvent(self, network.CallbackEvent(self.OnConnected)))

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
    self.res.AttachUnknownControl('sort_run_id', self.runDialogSortList)
    self.runDialogBreedList = MyOLV(self.runDialog, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('breedList', self.runDialogBreedList)


def main():
  app = App(False)
  app.MainLoop()

if __name__ == '__main__':
  main()
