# -*- coding: utf-8 -*-

import db

import wx
import locale
import ObjectListView as OLV
import xmlrpclib
from MyOLV import MyOLV, ColumnDefn
from wx import xrc
from pubsub import pub
from controllers import *
import stopwatch
import network
import socket

class App(wx.App):

  def OnInit(self):
    locale.setlocale(locale.LC_ALL, 'cs_CZ.UTF-8')
    self.locale = wx.Locale(wx.LANGUAGE_CZECH)

    self.res = xrc.XmlResource('agility.xrc')
    self.frame = self.res.LoadFrame(None, 'mainFrame')
    self.teamDialog = self.res.LoadDialog(self.frame, 'teamDialog')
    self.runDialog = self.res.LoadDialog(self.frame, 'runDialog')
    self.competitionSettingsDialog = self.res.LoadDialog(self.frame, 'competitionSettingsDialog')
    self.sortByResultsDialog = self.res.LoadDialog(self.frame, 'sortByResultsDialog')

    self. _initOLV()

    self.startupDialog = self.res.LoadDialog(self.frame, 'startupDialog')
    self.startupDialog.Bind(wx.EVT_BUTTON, self.OnOpenFile, id=xrc.XRCID("openButton"))
    self.startupDialog.Bind(wx.EVT_BUTTON, self.OnConnect, id=xrc.XRCID("connectButton"))
    self.startupDialog.ShowModal()

    self.frame.Bind(wx.EVT_MENU, self.entryController.OnConnectSimpleStopwatch, id=xrc.XRCID("connectSimpleStopwatch"))
    self.frame.Bind(wx.EVT_MENU, self.entryController.OnConnectAdvancedStopwatch, id=xrc.XRCID("connectAdvancedStopwatch"))
    self.frame.Bind(wx.EVT_CLOSE, self.OnClose)

    self.frame.SetSize((900, 600))
    self.frame.Show()

    return True

  def OnClose(self, evt):
    if hasattr(self, 'serverThread'):
      self.serverThread.stop()
    self.Destroy()

  def OnClientUpdate(self, evt):
    pub.sendMessage("run_result_updated", id=evt.runId)
    pub.sendMessage("result_updated")

  def OnOpenFile(self, evt):
    filename = self.startupDialog.FindWindowByName("filePicker").GetPath()
    db.OpenFile(filename)
    if self.startupDialog.FindWindowByName("startServer").GetValue():
      network.EVT_RELOAD(self, self.OnClientUpdate)
      port = self.startupDialog.FindWindowByName("serverPort").GetValue()
      self.serverThread = network.ServerThread(int(port), self)
      self.serverThread.start()
    self._initLocal()
    self.startupDialog.EndModal(wx.ID_OK)

  def OnConnect(self, evt):
    port = self.startupDialog.FindWindowByName("clientPort").GetValue()
    addr = self.startupDialog.FindWindowByName("clientAddress").GetValue()
    self.server = xmlrpclib.Server("http://%s:%s/" % (addr, port), allow_none=True)
    self._initRemote()
    self.startupDialog.EndModal(wx.ID_OK)

  def _initLocal(self):
    self.teamController = TeamController(self.teamDialog, self.frame.FindWindowByName("teamPanel"))
    self.entryController = EntryController(None, self.frame.FindWindowByName("entryPanel"))
    self.resultController = ResultController(None, self.frame.FindWindowByName("resultPanel"))
    self.sumsController = SumsController(None, self.frame.FindWindowByName("sumsPanel"))
    self.startController = StartController(self.sortByResultsDialog, self.frame.FindWindowByName("startPanel"), self.res.LoadMenu('startContext'))
    self.runController = RunController(self.runDialog, self.frame.FindWindowByName("runPanel"))
    self.settingsController = SettingsController(self.competitionSettingsDialog)

    self.frame.Bind(wx.EVT_MENU, self.teamController.OnRandomizeStartNums, id=xrc.XRCID("randomizeStartNums"))
    self.frame.Bind(wx.EVT_MENU, self.settingsController.OnCompetitionSettings, id=xrc.XRCID("competitionSettings"))

    #pub.subscribe(self.HandleUpdateSettings, "settings_updated")

  def _initRemote(self):
    self.entryController = NetworkedEntryController(None, self.frame.FindWindowByName("entryPanel"), self.server)
    self.runController = NetworkedRunController(self.frame.FindWindowByName("runChooser"), self.server)
    nb = self.frame.FindWindowByName("notebook")
    mb = self.frame.GetMenuBar()
    nb.DeletePage(0)
    nb.DeletePage(0)
    nb.DeletePage(0)
    nb.DeletePage(1)
    nb.DeletePage(1)
    mb.Remove(0)

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
    self.sortByResultsList = MyOLV(self.frame, wx.LC_SINGLE_SEL, sortable=False)
    self.res.AttachUnknownControl('sortByResultsList', self.sortByResultsList)


def main():
  app = App(False)
  app.MainLoop()

if __name__ == '__main__':
  main()
