# -*- coding: utf-8 -*-

import db
import wx
import ObjectAttrValidator2 as OAV
import urllib
import elementtree.ElementTree as ET
import printing
import stopwatch
import csv, codecs
import locale
import csvexport
from wx import xrc
from wx.lib.pubsub import pub
from Formatter import *
from ObjectListView import ObjectListView, ListCtrlPrinter, ReportFormat
from functools import partial
from MyOLV import ColumnDefn
from network import Client
from wx.lib.agw import floatspin
from twisted.internet.defer import inlineCallbacks, returnValue

class DefaultController:
  def __init__(self, dialog, panel):
    self.dialog = dialog
    self.panel = panel
    self.obj = None
    self._fieldWidgets = {}
    self._reactiveWidgets = []
    self.dialog.Bind(wx.EVT_BUTTON, self.OnDialogSave, id=wx.ID_SAVE)
    self.dialog.Bind(wx.EVT_SHOW, self.OnDialogOpen)
    self.listView.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnEditObject)
    self.listView.Bind(wx.EVT_LIST_KEY_DOWN, self.OnKeyDown)
    self.dialog.SetAffirmativeId(wx.ID_SAVE)
    self.dialog.SetEscapeId(wx.ID_CANCEL)
    pub.subscribe(self.UpdateList, self.query_string)
    pub.subscribe(self.UpdateList, "page_changed")
    pub.subscribe(self.UpdateList, "everything")

  def OnKeyDown(self, evt):
    keycode = evt.KeyCode
    if keycode == wx.WXK_RETURN or keycode == wx.WXK_NUMPAD_ENTER:
      self.OnEditObject(None)
      evt.Skip()

  def _updateValidators(self):
    for name in self._fieldWidgets.keys():
      wgt = self._fieldWidgets[name]
      validator = wgt.GetValidator()
      validator.SetObject(self.obj)
      validator.TransferToWindow()
      wgt.SetBackgroundColour(wx.NullColor)
      wgt.SetForegroundColour(wx.NullColor)
    self._dialogPostUpdate()

  def OnDialogOpen(self, evt):
    #hackish, needed to properly size the OLVs
    w, h = self.dialog.GetSizeTuple()
    self.dialog.SetSize((w+1, h+1))
    self.dialog.SetSize((w, h))

  def OnEditObject(self, evt):
    obj = self.listView.GetSelectedObject()
    if obj:
      self.obj = obj
      self._updateValidators()
      self.dialog.ShowModal()

  def SaveActiveObject(self, extraParams={}):
    valid = True
    if self.obj:
      for name, wgt in self._fieldWidgets.items():
        validator = wgt.GetValidator()
        if not validator.Validate(wgt):
          wgt.SetBackgroundColour((255,180,180))
          wgt.SetForegroundColour("Black")
          valid = False
        else:
          wgt.SetBackgroundColour(wx.NullColor)
          wgt.SetForegroundColour(wx.NullColor)
      if not valid:
        self.dialog.Refresh()
        return False
      for name, wgt in self._fieldWidgets.items():
        wgt.GetValidator().TransferFromWindow()
      Client().Post(self.objName, self.obj, extraParams=extraParams)
    return True

  def OnDeleteObject(self, evt):
    obj = self.listView.GetSelectedObject()
    if obj and wx.MessageBox(u"Opravdu?", "Kontrola", wx.YES_NO) == wx.YES:
      Client().Delete(self.objName, obj['id'])

  def OnNewObject(self, evt):
    Client().Create(self.objName, self._gotNewObject)

  def _gotNewObject(self, obj):
    self.obj = obj
    self._updateValidators()
    if self.dialog.ShowModal() == wx.ID_CANCEL:
      Client().Delete(self.objName, self.obj['id'])

  def OnDialogSave(self, evt):
    if self.SaveActiveObject():
      self.dialog.EndModal(wx.ID_SAVE)

  @inlineCallbacks
  def UpdateList(self, id = None):
    if self.panel.GetParent().GetCurrentPage() == self.panel:
      l = yield Client().sGet((self.query_string, None))
      self.listView.SetObjects(l)
      self.listView.RepopulateList()
    else:
      self._initList()


class TeamController(DefaultController):
  def __init__(self, dialog, panel):
    self.objName = "team"
    self.query_string = "teams"
    self.listView = panel.FindWindowByName("teamList")
    self.presentList = dialog.FindWindowByName("presentList")
    self._initList()
    self._initPresentList()
    DefaultController.__init__(self, dialog, panel)

    for name in ['number', 'osa', 'handler_name', 'handler_surname', 'dog_name', 'dog_kennel', 'dog_nick', 'category', 'size', 'paid', 'dog_breed_id', 'squad', 'def_sort']:
      self._fieldWidgets[name] = self.dialog.FindWindowByName(name)

    self.dialog.Bind(wx.EVT_BUTTON, self.OnGetTeamFromWeb, id=xrc.XRCID('getTeamFromWeb'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnNewObject, id=xrc.XRCID('newTeam'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnDeleteObject, id=xrc.XRCID('deleteTeam'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printTeams"))
    self.panel.Bind(wx.EVT_CHOICE, self.OnDayChoice, id=xrc.XRCID('teamDaySelect'))

    self.UpdateBreeds()
    self.UpdateList()

  def OnDayChoice(self, evt):
    self.listView.RepopulateList()

  def _dialogPostUpdate(self):
    self.presentList.RepopulateList()

  def UpdateBreeds(self):
    Client().Get(("breeds", None), self._gotBreeds)

  def _gotBreeds(self, l):
    self.breeds = [(b['id'], b['name']) for b in l]
    self.breeds.sort(key=lambda b: locale.strxfrm(b[1].encode('utf-8')))
    self._setValidators()

  def OnPrint(self, evt):
    Client().Get(("teams", None), self._gotPrint)

  def _gotPrint(self, l):
    printing.PrintTeams(l)

  def OnRandomizeStartNums(self, evt):
    if wx.MessageBox(u"Zamícháním startovních čísel změníte pořadí startovních listin. Opravdu chcete pokračovat?", "Kontrola", wx.YES_NO) == wx.YES:
      Client().RandomizeStartNums()

  def OnImportTeams(self, evt):
    def utf_8_encoder(unicode_csv_data):
      for line in unicode_csv_data:
        yield line.encode('utf-8')

    dlg = wx.FileDialog(self.panel.GetParent().GetParent(), "Vyberte soubor", "", "", "*.csv", wx.OPEN)
    if dlg.ShowModal() == wx.ID_OK and dlg.GetPath():
      filename = dlg.GetPath()
      teams = []
      csv_reader = csv.reader(utf_8_encoder(codecs.open(filename, 'rb', 'utf-8')), delimiter=',', quotechar='"')
      for row in csv_reader:
        teams.append([unicode(cell, 'utf-8') for cell in row])
      teams.pop(0)
      Client().ImportTeams(teams)
    dlg.Destroy()

  def SetPresence(self, day, state):
    if self.obj:
      a = 1 << day['day'] - 1
      if not state:
        self.obj['present'] = self.obj['present'] & ~(a)
      else:
        self.obj['present'] = self.obj['present'] | a

  def GetPresence(self, day):
    if self.obj:
      return bool(self.obj['present'] & (1<<(day['day'] - 1)))
    else:
      return False

  def SetPresenceFromList(self, team, state):
      kwargs = {}
      if state and not team['start_num']:
        kwargs['grab_start_num'] = True
      day = self.panel.FindWindowByName("teamDaySelect").GetSelection()
      a = 1 << day
      if not state:
        team['present'] = team['present'] & ~(a)
      else:
        team['present'] = team['present'] | a
      Client().Post(self.objName, team, **kwargs)

  def GetPresenceFromList(self, team):
    day = self.panel.FindWindowByName("teamDaySelect").GetSelection()
    return bool(team['present'] & (1<<day))

  @inlineCallbacks
  def _initPresentList(self):
    columns = [
      ColumnDefn(u"", fixedWidth=24, checkStateGetter=self.GetPresence, checkStateSetter=self.SetPresence),
      ColumnDefn(u"Den", "left", 100, "day", isSpaceFilling=True),
    ]
    self.presentList.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.presentList.SetColumns(columns)
    self.presentList.SetSortColumn(1, True)
    params = yield Client().sGet(("params", None))
    days = range(1, abs((params['date_to'] - params['date_from']).days) + 2)
    daylist = map(lambda x: {'day':x}, days)
    self.presentList.SetObjects(daylist)
    dayselect = self.panel.FindWindowByName("teamDaySelect")
    dayselect.SetItems(map(lambda x: str(x), days))
    dayselect.SetSelection(0)

  def _initList(self):
    def rowFormatter(item, team):
      day = self.panel.FindWindowByName("teamDaySelect").GetSelection()
      if not (team['registered'] & (1<<day)) or not team['confirmed']:
        item.SetBackgroundColour((255, 150, 150))

    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.rowFormatter = rowFormatter
    self.listView.SetColumns([
      ColumnDefn(u"Přítomen", fixedWidth=24, checkStateGetter=self.GetPresenceFromList, checkStateSetter=self.SetPresenceFromList),
      ColumnDefn(u"Číslo", "center", 60, "start_num"),
      ColumnDefn(u"Číslo průkazu", "center", 100, "number"),
      ColumnDefn(u"Příjmení", "left", 100, "handler_surname"),
      ColumnDefn(u"Jméno", "left", 100, "handler_name"),
      ColumnDefn(u"Pes", "left", 100, "dog_name"),
      ColumnDefn(u"Chovná stanice", "left", 100, "dog_kennel"),
      ColumnDefn(u"Družstvo", "left", 100, "squad"),
      ColumnDefn(u"Plemeno", "left", 150, "dog_breed"),
      ColumnDefn(u"Kategorie", "center", 70, FormatPartial("category", "category")),
      ColumnDefn(u"Velikost", "center", 60, FormatPartial("size", "size"), minimumWidth=60, isSpaceFilling=True),
    ])
    self.listView.secondarySortColumns = [3, 4, 5, 6]
    self.listView.SetSortColumn(3, True)

  def SetTeamPresent(self, team, value):
    kwargs = {}
    if value and not team['start_num']:
      kwargs['grab_start_num'] = True
    team['present'] = BoolFormatter().coerce(value)
    Client().Post(self.objName, team, **kwargs)

  def _setValidators(self):
    def wgt(name):
      return self.dialog.FindWindowByName(name)

    for name in ['handler_name', 'handler_surname', 'dog_name']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, None, True))
    for name in ['osa', 'number', 'dog_kennel', 'dog_nick']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, None, False))

    validator = OAV.ObjectAttrTextValidator(None, 'paid', FloatFormatter(), False)
    wgt('paid').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'category', GetFormatter('category'), True)
    wgt('category').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'size', GetFormatter('size'), True)
    wgt('size').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'def_sort', GetFormatter('yes_no'), True)
    wgt('def_sort').SetValidator(validator)
    #TODO: fix for network
    #validator = OAV.ObjectAttrComboValidator(None, 'squad', ListFromCallableFormatter(db.GetSquads), False)
    validator = OAV.ObjectAttrTextValidator(None, 'squad', None, False)
    wgt('squad').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'dog_breed_id', EnumFormatter(EnumType(self.breeds)), True)
    wgt('dog_breed_id').SetValidator(validator)

  def OnGetTeamFromWeb(self, evt):
    wx.BeginBusyCursor()
    number = self._fieldWidgets['number'].GetValue()
    if len(number) < 6:
      number = "0" * (6 - len(number)) + number
    f = urllib.urlopen("http://kacr.info/books/xml?number=%s" % number)
    wx.EndBusyCursor()
    if f.getcode() == 200:
      xml = ET.XML(f.read())
      self.obj['number'] = xml.findtext('number')
      self.obj['handler_name'] = xml.findtext('handler/first-name')
      self.obj['handler_surname'] = xml.findtext('handler/surname')
      self.obj['dog_name'] = xml.findtext('dog/name')
      self.obj['dog_kennel'] = xml.findtext('dog/kennel')
      self.obj['dog_breed_id'] = int(xml.findtext('dog/breed/id'))
      self.obj['size'] = GetFormatter('size').coerce(xml.findtext('dog/size'))
      self.obj['category'] = None
      self._updateValidators()
    else:
      wx.MessageBox(u"Průkaz nenalezen.\nZkontrolujte, zda jste správně zadali číslo.", "Chyba")

class RunController(DefaultController):
  def __init__(self, dialog, panel):
    self.query_string = "runs"
    self.objName = "run"
    self.listView = panel.FindWindowByName("runList")
    self.breedList = dialog.FindWindowByName("breedList")
    self.runChooser = xrc.XRCCTRL(panel.GetParent().GetParent(), "runChooser")
    self.runInfo = panel.GetParent().GetParent().FindWindowByName("runInfo")
    self.runChooserSelected = None
    DefaultController.__init__(self, dialog, panel)

    self._reactiveWidgets = ['time_calc', 'variant']
    for name in ['time_calc', 'name', 'size', 'category', 'variant', 'style', 'day', 'length', 'time', 'max_time', 'judge', 'hurdles', 'min_speed', 'squads', 'sort_run_id']:
      self._fieldWidgets[name] = self.dialog.FindWindowByName(name)
    self._setValidators()

    self._initList()

    self.panel.Bind(wx.EVT_BUTTON, self.OnNewObject, id=xrc.XRCID('newRun'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnDeleteObject, id=xrc.XRCID('deleteRun'))
    self.panel.GetParent().GetParent().Bind(wx.EVT_CHOICE, self.OnRunChoice, id=xrc.XRCID('runChooser'))
    self.dialog.Bind(wx.EVT_CHOICE, self.OnDialogTimeCalc, id=xrc.XRCID('time_calc'))
    self.dialog.Bind(wx.EVT_SHOW, self.OnDialogOpen)
    self.dialog.Bind(wx.EVT_CHOICE, self.OnDialogVariant, id=xrc.XRCID('variant'))

    pub.subscribe(self.UpdateRunChooser, "runs")
    pub.subscribe(self.UpdateRunChooser, "everything")
    pub.subscribe(self.UpdateDialogSortList, "runs")
    pub.subscribe(self.UpdateDialogSortList, "everything")
    pub.subscribe(self.UpdateRunInfo, "run_selection_changed")
    pub.subscribe(self.UpdateRunInfoWrapper, "run_times")
    pub.subscribe(self.UpdateRunInfoWrapper, "everything")
    self.UpdateList()
    self.UpdateDialogBreedList()
    self.UpdateRunChooser()
    self.UpdateDialogSortList()

  def _dialogPostUpdate(self):
    self.breedList.RepopulateList()

  def _initList(self):
    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns([
      ColumnDefn(u"Název", "left", 150, "name", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Velikost", "center", 120, FormatPartial("size", "size")),
      ColumnDefn(u"Kategorie", "center", 150, FormatPartial("category", "category")),
      ColumnDefn(u"Typ", "left", 150, FormatPartial("variant", "run_variant")),
      ColumnDefn(u"Den", "left", 150, "day"),
      ColumnDefn(u"Družstva", "left", 150, FormatPartial("squads", "yes_no")),
      ColumnDefn(u"Rozhodčí", "left", 150, "judge"),
    ])
    self.listView.secondarySortColumns = [0, 1, 2]
    self.listView.SetSortColumn(0, True)

    self._fieldWidgets['sort_run_id'].cellEditMode = ObjectListView.CELLEDIT_NONE
    self._fieldWidgets['sort_run_id'].SetColumns([ColumnDefn(u"Běh", "left", 150, "name", minimumWidth=150, isSpaceFilling=True)])

  def UpdateDialogBreedList(self):
    self._initBreedList()
    Client().Get(("breeds", None), self._gotBreeds)

  def _gotBreeds(self, l):
    self.breedList.SetObjects(l)

  def SetBreedFilter(self, breed, state):
    if self.obj:
      if not state and breed['id'] in self.obj['breeds']:
        self.obj['breeds'].remove(breed['id'])
      elif state and breed['id'] not in self.obj['breeds']:
        self.obj['breeds'].append(breed['id'])

  def GetBreedFilter(self, breed):
    if self.obj:
      return breed['id'] in self.obj['breeds']
    else:
      return False

  def _initBreedList(self):
    columns = [
      ColumnDefn(u"", fixedWidth=24, checkStateGetter=self.GetBreedFilter, checkStateSetter=self.SetBreedFilter),
      ColumnDefn(u"Plemeno", "left", 100, "name", isSpaceFilling=True),
    ]
    self.breedList.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.breedList.SetColumns(columns)
    self.breedList.SetSortColumn(1, True)
    self.breedList.GetContainingSizer().Layout()

  @inlineCallbacks
  def _setValidators(self):
    params = yield Client().sGet(("params", None))
    daylist = dict(map(lambda x: (x,str(x)), range(1, abs((params['date_to'] - params['date_from']).days) + 2)))

    def wgt(name):
      return self.dialog.FindWindowByName(name)

    wgt('name').SetValidator(OAV.ObjectAttrTextValidator(None, 'name', None, True))

    for name in ['judge']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, None, False))
    for name in ['length', 'time', 'max_time', 'min_speed']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, FloatFormatter(), False))

    validator = OAV.ObjectAttrSelectorValidator(None, 'category', GetFormatter('category'), False)
    wgt('category').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'size', GetFormatter('size'), False)
    wgt('size').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'day', EnumFormatter(EnumType(daylist)), False)
    wgt('day').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'variant', GetFormatter('run_variant'), False)
    wgt('variant').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'style', GetFormatter('run_style'), False)
    wgt('style').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'time_calc', GetFormatter('run_time_calc'), False)
    wgt('time_calc').SetValidator(validator)
    validator = OAV.ObjectAttrTextValidator(None, 'hurdles', IntFormatter(), False)
    wgt('hurdles').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'squads', GetFormatter('yes_no'), False)
    wgt('squads').SetValidator(validator)
    validator = OAV.ObjectAttrOLVValidator(None, 'sort_run_id', None, False)
    wgt('sort_run_id').SetValidator(validator)

  def UpdateRunInfoWrapper(self, id = None):
    self.UpdateRunInfo()

  def UpdateRunInfo(self, run = None):
    if self.runChooserSelected:
      Client().Get(("run_times", self.runChooserSelected['id']), self._gotRunTimes)
    else:
      self.runInfo.SetLabel("")

  def _gotRunTimes(self, times):
    self.runInfo.SetLabel(u"SČ: %.2f, MČ: %.2f" % times)

  def UpdateRunChooser(self, id = None):
    Client().Get(("runs", None), self._gotChooserItems)

  def _gotChooserItems(self, l):
    self.runChooserItems = l
    items = []
    found = False

    for run in self.runChooserItems:
      items.append(run['nice_name'])
      if self.runChooserSelected and self.runChooserSelected['id'] == run['id']:
        found = True

    self.runChooser.Freeze()
    self.runChooser.Clear()
    self.runChooser.AppendItems(items)
    self.runChooser.Thaw()

    if items == []:
      self.runChooser.SetSelection(wx.NOT_FOUND)
      self.runChooserSelected = None
    elif not found:
      self.runChooser.SetSelection(0)
      self.runChooserSelected = self.runChooserItems[0]
    else:
      for i, e in zip(range(len(self.runChooserItems)), self.runChooserItems):
        if e['id'] == self.runChooserSelected['id']:
          self.runChooser.SetSelection(i)

    pub.sendMessage("run_selection_changed", run = self.runChooserSelected)

  def UpdateDialogSortList(self, id = None):
    Client().Get(("runs", None), self._gotSortListItems)

  def _gotSortListItems(self, l):
    runs = l
    objs = []
    for r in runs:
      r = {"id":r['id'], "name":r['nice_name']}
      objs.append(r)
    objs.insert(0, {"id": 0, "name":u"[řadit normálně]"})
    self._fieldWidgets['sort_run_id'].SetObjects(objs)
    self._fieldWidgets['sort_run_id'].RepopulateList()
    self._fieldWidgets['sort_run_id'].DeselectAll()

  def OnRunChoice(self, evt):
    self.runChooserSelected = self.runChooserItems[self.runChooser.GetSelection()]
    pub.sendMessage("run_selection_changed", run = self.runChooserSelected)

  def OnDialogTimeCalc(self, evt):
    wgt = self.dialog.FindWindowByName("time_calc")
    self._fieldWidgets['time'].SetValue("0.00")
    self._fieldWidgets['max_time'].SetValue("0.00")
    self._fieldWidgets['min_speed'].SetValue("0.00")
    if wgt.GetSelection() == 0:
      self.dialog.FindWindowByName("time_suffix").SetLabel("s")
      self.dialog.FindWindowByName("max_time_suffix").SetLabel("s")
      self.dialog.FindWindowByName("min_speed").Disable()
    else:
      self.dialog.FindWindowByName("time_suffix").SetLabel("x")
      self.dialog.FindWindowByName("max_time_suffix").SetLabel("x")
      self.dialog.FindWindowByName("min_speed").Enable()

  def OnDialogVariant(self, evt):
    wgt = self.dialog.FindWindowByName("variant")
    category = self._fieldWidgets['category']
    if wgt.GetSelection() == 0:
      category.Enable()
      category.SetSelection(0)
    else:
      category.Disable()
      category.SetSelection(wx.NOT_FOUND)

  def OnEditObject(self, evt):
    gen = self.dialog.FindWindowByName("generateRuns")
    gen.SetValue(False)
    gen.Disable()
    DefaultController.OnEditObject(self, evt)

  def _gotNewObject(self, obj):
    self.dialog.FindWindowByName("generateRuns").Enable()
    DefaultController._gotNewObject(self, obj)

  def OnDialogSave(self, evt):
    if self.dialog.FindWindowByName("generateRuns").GetValue():
      p = {"generate_runs":True}
    else:
      p = {}
    if self.SaveActiveObject(p):
      self.dialog.EndModal(wx.ID_SAVE)

class StartController():
  def __init__(self, dialog=None, panel=None, contextMenu=None):
    self.panel = panel
    self.currentRun = None
    self.dialog = dialog
    self.contextMenu = contextMenu
    self.listView = panel.FindWindowByName("startList")
    self._initList()

    pub.subscribe(self.UpdateList, "runs")
    pub.subscribe(self.UpdateList, "teams")
    pub.subscribe(self.UpdateList, "start_list_with_removed")
    pub.subscribe(self.UpdateList, "everything")
    pub.subscribe(self.UpdateList, "page_changed")
    pub.subscribe(self.UpdateRun, "run_selection_changed")

    self.listView.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
    self.contextMenu.Bind(wx.EVT_MENU, self.SortBeginning, id=xrc.XRCID("startSortBeginning"))
    self.contextMenu.Bind(wx.EVT_MENU, self.SortEnd, id=xrc.XRCID("startSortEnd"))
    self.contextMenu.Bind(wx.EVT_MENU, self.SortReset, id=xrc.XRCID("startSortReset"))
    self.contextMenu.Bind(wx.EVT_MENU, self.SortRemove, id=xrc.XRCID("startSortRemove"))

    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printStart"))

  def OnPrint(self, evt):
    if self.currentRun:
      Client().Get(("start_list", self.currentRun['id']), self._gotPrint)

  def _gotPrint(self, l):
    printing.PrintStart(l, self.currentRun)

  def SortBeginning(self, evt):
    self.SetSort(1)

  def SortEnd(self, evt):
    self.SetSort(2)

  def SortRemove(self, evt):
    self.SetSort(3)

  def SortReset(self, evt):
    self.SetSort(0)

  def SetSort(self, where):
    o = self.listView.GetSelectedObject()
    if o:
      o['sort']['value'] = where
      Client().Post('sort', o['sort'])

  def OnRightDown(self, evt):
    if self.currentRun and not self.currentRun['squads'] and not self.currentRun['sort_run_id']:
      i, w = self.listView.HitTest(evt.GetPosition())
      if i != wx.NOT_FOUND:
        self.listView.Select(i)
        items = self.contextMenu.GetMenuItems()
        val = self.listView.GetSelectedObject()['sort']['value']
        if val >= 4:
          val -= 4
          items[2].SetItemLabel(u"Zařadit")
          items[4].SetItemLabel(u"Zrušit výjimku")
        else:
          items[2].SetItemLabel(u"Vyřadit")
          items[4].SetItemLabel(u"Zrušit ruční řazení")

        disable = (val - 1 if val else 4)
        for i in [0,1,2,4]:
          items[i].Enable(i != disable)

        self.listView.PopupMenu(self.contextMenu, evt.GetPosition())

  def UpdateRun(self, run = None):
    self.currentRun = run
    self._initList()
    self.UpdateList()

  def UpdateList(self, id = None):
    if self.panel.GetParent().GetCurrentPage() == self.panel and \
       self.currentRun and (not id or self.currentRun['id'] == id):
      Client().Get(("start_list_with_removed", self.currentRun['id']), self._gotList)
    else:
      self._initList()

  def _gotList(self, l):
    self.listView.SetObjects(l)
    self.listView.RepopulateList()

  def _initList(self):
    columns = [
      ColumnDefn(u"Pořadí", "center", 60, "order"),
      ColumnDefn(u"Číslo", "center", 60, "start_num"),
      ColumnDefn(u"Psovod", "left", 150, lambda t: t['handler_name'] + ' ' + t['handler_surname'], minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 150, lambda t: t['dog_name'] + ' ' + t['dog_kennel']),
      ColumnDefn(u"Plemeno", "left", 100, lambda t: t['breed']['name']),
      ColumnDefn(u"Kategorie", "center", 150, FormatPartial("category", "category")),
      ColumnDefn(u"Řazení", "center", 140, valueGetter=lambda t: GetFormatter("start_sort").format(t['sort']['value'])),
    ]
    if self.currentRun and self.currentRun['squads']:
      columns.insert(2, ColumnDefn(u"Družstvo", "left", 100, "squad"))
    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns(columns)
    self.listView.secondarySortColumns = [0]
    self.listView.SetSortColumn(0, True)

class EntryController(DefaultController):
  def __init__(self, dialog=None, panel=None):
    self.panel = panel
    self.currentRun = None
    self.obj = None
    self.team = None
    self.listView = panel.FindWindowByName("entryList")
    self.update_message = 'results'
    self.objName = 'result'
    self.stopwatch = None
    self.updating = False
    self._initList()
    self.listView._SelectAndFocus(-1)

    self._fieldWidgets = {}
    for name in ['mistakes', 'refusals', 'time', 'disqualified']:
      wgt = self.panel.FindWindowByName(name)
      self._fieldWidgets[name] = wgt
      if name in ['mistakes', 'refusals']:
        #floatspins need special treatment
        wgt._textctrl.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
      else:
        wgt.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
    self._setValidators()

    pub.subscribe(self.UpdateList, "runs")
    pub.subscribe(self.UpdateList, "teams")
    pub.subscribe(self.UpdateList, "everything")
    pub.subscribe(self.UpdateList, "start_list")
    pub.subscribe(self.UpdateList, "page_changed")
    pub.subscribe(self.UpdateRun, "run_selection_changed")

    self.listView.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelectionChange, id=xrc.XRCID("entryList"))
    self.listView.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printEntry"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnGetTime, id=xrc.XRCID("getTime"))

    self.panel.Bind(wx.EVT_TIMER, self.OnTick)

    self.timer = wx.Timer(self.panel)
    self.timer.Start(100)

  def _dialogPostUpdate(self):
    pass

  def OnConnectAdvancedStopwatch(self, evt):
    self.ConnectStopwatch(stopwatch.AdvancedStopwatchThread)

  def OnConnectSimpleStopwatch(self, evt):
    self.ConnectStopwatch(stopwatch.SimpleStopwatchThread)

  def ConnectStopwatch(self, stopwatch):
    try:
      self.stopwatch = stopwatch()
      self.stopwatch.Test()
      self.stopwatch.start()
      self.panel.GetParent().GetParent().GetSizer().Layout()
      self.panel.FindWindowByName("getTime").Enable()
      wx.MessageBox(u"Stopky připojeny", "Stopky")
    except:
      self.stopwatch = None
      wx.MessageBox(u"Stopky se nepodařilo připojit", "Stopky")

  def OnTick(self, evt):
    if self.stopwatch:
      self.panel.GetParent().GetParent().FindWindowByName('stopwatchTime').SetLabel(self.stopwatch.GetText())

  def OnGetTime(self, evt):
    if self.currentRun:
      for c in ['mistakes', 'refusals']:
        if c in self.stopwatch.GetCapabilities():
          self._fieldWidgets[c].SetValue(int(self.stopwatch.Get(c)))

      time = FloatFormatter().format(self.stopwatch.GetTime())
      self._fieldWidgets['time'].SetValue(time)
      self._fieldWidgets['time'].SetFocus()
      self._fieldWidgets['time'].SetSelection(0,6)

  def OnPrint(self, evt):
    if self.currentRun:
      Client().Get(("start_list", self.currentRun['id']), self._gotPrint)

  def _gotPrint(self, l):
    printing.PrintEntry(l, self.currentRun)

  def UpdateRun(self, run = None):
    self.currentRun = run
    self._initList()
    self.ClearSelection()
    self.UpdateList()

  def UpdateList(self, id = None):
    if self.panel.GetParent().GetCurrentPage() == self.panel and \
       self.currentRun and (not id or self.currentRun['id'] == id):
      Client().Get(("start_list", self.currentRun['id']), self._gotList)
    else:
      self._initList()

  def _gotList(self, l):
    sel = self.listView.GetSelectedObject()
    self.listView.SetObjects(l)
    self.listView.RepopulateList()
    newsel = self.listView.GetSelectedObject()
    if sel and (not newsel or sel['id'] != newsel['id']):
      for i in self.listView.GetObjects():
        if i['id'] == sel['id']:
          self.listView.SelectObject(i)
          return

  def _initList(self):
    def GetFromResult(attr, formatter, model):
      val = model['result'][attr]
      if formatter:
        val = formatter.format(val)
      return val

    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    columns = [
      ColumnDefn(u"Pořadí", "center", 60, "order"),
      ColumnDefn(u"Číslo", "center", 60, "start_num"),
      ColumnDefn(u"Psovod", "left", 150, lambda t: t['handler_name'] + ' ' + t['handler_surname'], minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 220, lambda t: t['dog_name'] + ' ' + t['dog_kennel']),
      ColumnDefn(u"Kategorie", "center", 70, FormatPartial("category", "category")),
      ColumnDefn(u"Chyby", "center", 80, partial(GetFromResult, "mistakes", IntFormatter())),
      ColumnDefn(u"Odmítnutí", "center", 80, partial(GetFromResult, "refusals", IntFormatter())),
      ColumnDefn(u"Čas", "right", 60, partial(GetFromResult, "time", FloatFormatter())),
      ColumnDefn(u"Diskvalifikován", "center", 100, partial(GetFromResult, "disqualified", GetFormatter("disqualified"))),
      ]
    if self.currentRun and self.currentRun['squads']:
      columns.insert(2, ColumnDefn(u"Družstvo", "left", 100, "squad"))
    self.listView.SetColumns(columns)
    self.listView.secondarySortColumns = [0]
    self.listView.SetSortColumn(0, True)

  def OnSelectionChange(self, evt=None):
    index = self.listView.GetFirstSelected()
    oldindex = self.listView.GetIndexOf(self.team)
    self.SaveActiveObject()
    if self.team and oldindex >= 0:
      old = self.listView.GetObjectAt(oldindex)
      if old['id'] == self.team['id']:
        old.update(self.team)
        self.listView.RefreshObject(old)
    if index != wx.NOT_FOUND and index != -1:
      for w in self._fieldWidgets.values():
        w.Enable()
      team = self.listView.GetObjectAt(index)
      self.panel.FindWindowByName("handler").SetLabel(team['handler_name'] + ' ' + team['handler_surname'])
      self.panel.FindWindowByName("dog").SetLabel(team['dog_name'] + ' ' + team['dog_kennel'])
      self.obj = team['result']
      self.team = team
    else:
      self.ClearSelection()
    self._updateValidators()

  def ClearSelection(self):
    for w in self._fieldWidgets.values():
      w.Disable()
    self.panel.FindWindowByName("handler").SetLabel("")
    self.panel.FindWindowByName("dog").SetLabel("")
    self.obj = None
    self.team = None

  def SelectNext(self):
    index = self.listView.GetFirstSelected()
    self.listView._SelectAndFocus(index+1)
    if index+1 >= self.listView.GetItemCount():
      self.OnSelectionChange()
    else:
      self._fieldWidgets['mistakes'].SetFocus()
      self._fieldWidgets['mistakes']._textctrl.SetSelection(0,2)

  def _setValidators(self):
    def wgt(name):
      return self.panel.FindWindowByName(name)

    for name in ['mistakes', 'refusals']:
      wgt(name).SetValidator(OAV.ObjectAttrSpinValidator(None, name, IntFormatter(), False))

    validator = OAV.ObjectAttrTextValidator(None, 'time', FloatFormatter(), False)
    wgt('time').SetValidator(validator)
    validator = OAV.ObjectAttrCheckBoxValidator(None, 'disqualified', BoolFormatter(), False)
    wgt('disqualified').SetValidator(validator)

  def OnKeyDown(self, evt):
    keycode = evt.KeyCode
    if keycode == wx.WXK_RETURN or keycode == wx.WXK_NUMPAD_ENTER:
      self.SelectNext()
    elif keycode == wx.WXK_ESCAPE:
      self._updateValidators()
    else:
      evt.Skip()
    #elif evt.GetUnicodeKey() == 81:
    #  self._fieldWidgets['mistakes'].SetValue(self._fieldWidgets['mistakes'].GetValue())


class ResultController():
  def __init__(self, dialog=None, panel=None):
    self.panel = panel
    self.currentRun = None
    self.listView = panel.FindWindowByName("resultList")
    self._initList()

    pub.subscribe(self.UpdateRun, "run_selection_changed")
    pub.subscribe(self.UpdateList, "results")
    pub.subscribe(self.UpdateList, "everything")
    pub.subscribe(self.UpdateList, "page_changed")
    pub.subscribe(self.UpdateList, "squad_results")

    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printResults"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnPrintCerts, id=xrc.XRCID("printCerts"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnExport, id=xrc.XRCID("exportResults"))

  def OnPrint(self, evt):
    if self.currentRun:
      if self.currentRun['squads']:
        Client().Get(("squad_results", self.currentRun['id']), self._gotPrint)
      else:
        Client().Get(("results", self.currentRun['id']), self._gotPrint)

  def _gotPrint(self, l):
    Client().Get(("run_times", self.currentRun['id']), lambda t: self._gotTimes(l, t))

  def OnPrintCerts(self, evt):
    if self.currentRun and not self.currentRun['squads']:
      Client().Get(("results", self.currentRun['id']), self._gotPrintCerts)

  def _gotPrintCerts(self, l):
    count = self.panel.FindWindowByName("certCount").GetValue()
    printing.PrintCerts(l, self.currentRun['nice_name'], count)

  def OnExport(self, evt):
    if self.currentRun and not self.currentRun['squads']:
      Client().Get(("results", self.currentRun['id']), self._gotExport)

  def _gotExport(self, l):
    dlg = wx.FileDialog(self.panel.GetParent().GetParent(), "Vyberte soubor", "", "", "*.csv", wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
    if dlg.ShowModal() == wx.ID_OK and dlg.GetPath():
      filename = dlg.GetPath()
      csvexport.SingleRunExport(filename, l)
    dlg.Destroy()

  def _gotTimes(self, l, t):
    self.currentRun['time'] = t[0]
    self.currentRun['max_time'] = t[1]
    printing.PrintResults(l, self.currentRun)

  def UpdateRun(self, run = None):
    self.currentRun = run
    self._initList()
    self.UpdateList()
    enable = bool(self.currentRun) and not self.currentRun['squads']
    self.panel.FindWindowByName("printCerts").Enable(enable)
    self.panel.FindWindowByName("certCount").Enable(enable)

  def UpdateList(self, id = None):
    if self.panel.GetParent().GetCurrentPage() == self.panel and \
       self.currentRun and (not id or self.currentRun['id'] == id):
      if self.currentRun['squads']:
        Client().Get(("squad_results", self.currentRun['id']), self._gotSquadResults)
      else:
        Client().Get(("results", self.currentRun['id']), self._gotResults)
    else:
      self._initList()

  def _gotResults(self, l):
    self.listView.SetObjects(l)
    self.listView.RepopulateList()

  def _gotSquadResults(self, l):
    objects = []
    for r in l:
      squad_line = {'rank': r['rank'], 'team_start_num':"", "team_handler":r['name'], "team_dog": "", "breed_name": "", "team_category": "", "result_mistakes":"", "result_refusals":"", "result_time":r['result_time'], "total_penalty":r["total_penalty"], "speed":"", "disq": r["disq"], "squad_line": True}
      objects.append(squad_line)
      for t in r['members']:
        objects.append(t)
    self.listView.SetObjects(objects)
    self.listView.RepopulateList()

  def _initList(self):
    def _ifDis(a, fl=False):
      if fl:
        return lambda y: 'DIS' if y['disq'] else FloatFormatter().format(y[a])
      else:
        return lambda y: 'DIS' if y['disq'] else y[a]

    def _ifNotSquad(a, fl=False):
      return lambda y: _ifDis(a, fl)(y) if (not "squad_line" in y.keys() or not self.currentRun['squads']) else None

    def _ifSquad(a, fl=False):
      return lambda y: _ifDis(a, fl)(y) if ("squad_line" in y.keys() or not self.currentRun['squads']) else None

    def rowFormatter(listItem, obj):
      if "squad_line" in obj.keys():
        listItem.SetBackgroundColour((170, 230, 170))

    columns = [
      ColumnDefn(u"Pořadí", "center", 60, _ifSquad('rank')),
      ColumnDefn(u"Číslo", "center", 60, "team_start_num"),
      ColumnDefn(u"Psovod", "left", 150, "team_handler", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 150, "team_dog"),
      ColumnDefn(u"Plemeno", "left", 100, "breed_name"),
      ColumnDefn(u"Kategorie", "center", 150, FormatPartial("team_category", "category")),
      ColumnDefn(u"Chyby", "center", 80, _ifNotSquad("result_mistakes")),
      ColumnDefn(u"Odmítnutí", "center", 80, _ifNotSquad("result_refusals")),
      ColumnDefn(u"Čas", "right", 60, _ifDis("result_time", True)),
      ColumnDefn(u"Tr. b.", "right", 60, _ifDis("total_penalty", True)),
      ColumnDefn(u"Rychlost", "right", 60, _ifNotSquad('speed', True)),
    ]
    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns(columns)
    self.listView.rowFormatter = rowFormatter

class SumsController():
  def __init__(self, dialog=None, panel=None):
    self.panel = panel
    self.listView = panel.FindWindowByName("sumsList")
    self.chooser = panel.FindWindowByName("sumsChooser")
    self.runs = []
    self._initLists()
    self.UpdateChooser()

    pub.subscribe(self.UpdateList, "sums")
    pub.subscribe(self.UpdateList, "squad_sums")
    pub.subscribe(self.UpdateList, "everything")
    pub.subscribe(self.UpdateChooser, "runs")
    pub.subscribe(self.UpdateChooser, "everything")

    self.chooser.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelectionChange, id=xrc.XRCID("sumsChooser"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printSums"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnPrintCerts, id=xrc.XRCID("printSumsCerts"))

  def OnPrint(self, evt):
    if self.runs:
      run_ids = tuple([x['id'] for x in self.runs])
      if self.runs[0]['squads']:
        Client().Get(("squad_sums", run_ids), self._gotPrint)
      else:
        Client().Get(("sums", run_ids), self._gotPrint)

  def _gotPrint(self, l):
    printing.PrintSums(l, self.runs)

  def OnPrintCerts(self, evt):
    if self.runs:
      run_ids = tuple([x['id'] for x in self.runs])
      if not self.runs[0]['squads']:
        Client().Get(("sums", run_ids), self._gotPrintCerts)

  def _gotPrintCerts(self, l):
    count = self.panel.FindWindowByName("sumsCertCount").GetValue()
    printing.PrintSumsCerts(l, self.runs, count)

  def OnSelectionChange(self, evt):
    self.runs = self.chooser.GetSelectedObjects()
    self.UpdateList()
    enable = bool(self.runs) and not self.runs[0]['squads']
    self.panel.FindWindowByName("printSumsCerts").Enable(enable)
    self.panel.FindWindowByName("sumsCertCount").Enable(enable)

  def UpdateChooser(self, id = None):
    Client().Get(("runs", None), self._gotChooserItems)

  def _gotChooserItems(self, l):
    self.chooser.SetObjects(l)
    self.chooser.RepopulateList()

  def UpdateList(self, id = None):
    if self.panel.GetParent().GetCurrentPage() == self.panel and self.runs:
      squads = self.runs[0]['squads']
      for r in self.runs:
        if r['squads'] != squads:
          wx.MessageBox(u"Nelze vytvářet součty z běhů týmů a jednotlivců zároveň.", u"Chyba")
          self.runs = []
          self.chooser.DeselectAll()

      if self.runs:
        run_ids = tuple([x['id'] for x in self.runs])
        if squads:
          Client().Get(("squad_sums", run_ids), self._gotSquadSums)
        else:
          Client().Get(("sums", run_ids), self._gotSums)
        return

    self.listView.SetObjects([])
    self.listView.RepopulateList()

  def _gotSquadSums(self, l):
    objects = []
    for s in l:
      squad_line = {'rank': s['rank'], 'team_start_num':"", "team_handler":s['name'], "team_dog": "", "team_dog_breed": "", "team_category": "", "result_time":s['result_time'], "total_penalty":s["total_penalty"], "speed":"", "disq":s['disq'], "squad_line": True}
      objects.append(squad_line)
      for t in s['members']:
        objects.append(t)
    self.listView.SetObjects(objects)
    self.listView.RepopulateList()

  def _gotSums(self, l):
    self.listView.SetObjects(l)
    self.listView.RepopulateList()

  def _initLists(self):
    def _ifDis(a, fl=False):
      if fl:
        return lambda y: 'DIS' if y['disq'] else FloatFormatter().format(y[a])
      else:
        return lambda y: 'DIS' if y['disq'] else y[a]

    def _ifSquad(a, fl=False):
      return lambda y: _ifDis(a, fl)(y) if ("squad_line" in y.keys() or not self.runs[0]['squads']) else None

    def rowFormatter(listItem, obj):
      if "squad_line" in obj.keys():
        listItem.SetBackgroundColour((170, 230, 170))

    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns([
      ColumnDefn(u"Pořadí", "center", 60, _ifSquad("rank")),
      ColumnDefn(u"Číslo", "center", 60, "team_start_num"),
      ColumnDefn(u"Psovod", "left", 150, "team_handler", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 150, "team_dog"),
      ColumnDefn(u"Plemeno", "left", 100, "breed_name"),
      ColumnDefn(u"Kategorie", "center", 150, FormatPartial("team_category", "category")),
      ColumnDefn(u"Čas", "right", 60, _ifSquad("result_time", True)),
      ColumnDefn(u"Tr. b.", "right", 60, _ifSquad('total_penalty', True)),
      ColumnDefn(u"Rychlost", "right", 60, _ifSquad("speed", True)),
    ])
    self.listView.rowFormatter = rowFormatter

    self.chooser.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.chooser.SetColumns([
      ColumnDefn(u"Běh", "left", 60, "nice_name", minimumWidth=150, isSpaceFilling=True)
    ])

class SettingsController:
  def __init__(self, dialog):
    self.dialog = dialog
    self.obj = None
    self._fieldWidgets = {}
    for name in ['competition_name']:
      self._fieldWidgets[name] = self.dialog.FindWindowByName(name)
    self._setValidators()
    self.dialog.Bind(wx.EVT_BUTTON, self.OnDialogSave, id=wx.ID_SAVE)

  def _updateValidators(self):
    for name, wgt in self._fieldWidgets.items():
      validator = wgt.GetValidator()
      validator.SetObject(self.obj)
      validator.TransferToWindow()
      wgt.SetBackgroundColour(wx.NullColor)
      wgt.SetForegroundColour(wx.NullColor)

  def SaveObjects(self):
    valid = True
    for name, wgt in self._fieldWidgets.items():
      validator = wgt.GetValidator()
      if not validator.Validate(wgt):
        wgt.SetBackgroundColour((255,180,180))
        wgt.SetForegroundColour("Black")
        valid = False
      else:
        wgt.SetBackgroundColour(wx.NullColor)
        wgt.SetForegroundColour(wx.NullColor)
    if not valid:
      return False
    for name, wgt in self._fieldWidgets.items():
      wgt.GetValidator().TransferFromWindow()
    Client().Post("params", self.obj)
    return True

  def OnDialogSave(self, evt):
    if self.SaveObjects():
      self.dialog.EndModal(wx.ID_SAVE)

  @inlineCallbacks
  def OnCompetitionSettings(self, evt):
    self.obj = yield Client().sGet(("params", None))
    self._updateValidators()
    self.dialog.ShowModal()

  def _setValidators(self):
    def wgt(name):
      return self.dialog.FindWindowByName(name)

    for name in ['competition_name']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, None, True))

