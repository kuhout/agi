# -*- coding: utf-8 -*-
import db
import wx
import ObjectAttrValidator2 as OAV
import urllib
import elementtree.ElementTree as ET
import printing
import stopwatch
import csv, codecs
from pubsub import pub
from wx import xrc
from Formatter import *
from ObjectListView import ObjectListView, ListCtrlPrinter, ReportFormat
from functools import partial
from MyOLV import ColumnDefn

class DefaultController:
  def __init__(self, dialog, panel):
    self.update_message = self.objName + "_updated"
    self.delete_message = self.objName + "_deleted"
    self.insert_message = self.objName + "_inserted"
    self.dialog = dialog
    self.panel = panel
    self.obj = None
    self._fieldWidgets = {}
    self.dialog.Bind(wx.EVT_BUTTON, self.OnDialogSave, id=wx.ID_SAVE)
    self.listView.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnEditObject)
    self.listView.Bind(wx.EVT_LIST_KEY_DOWN, self.OnKeyDown)
    self.dialog.SetAffirmativeId(wx.ID_SAVE)
    self.dialog.SetEscapeId(wx.ID_CANCEL)
    pub.subscribe(self.UpdateList, self.delete_message)
    pub.subscribe(self.UpdateList, self.insert_message)
    pub.subscribe(self.UpdateList, self.update_message)

  def OnKeyDown(self, evt):
    keycode = evt.KeyCode
    if keycode == wx.WXK_RETURN or keycode == wx.WXK_NUMPAD_ENTER:
      self.OnEditObject(None)
      evt.Skip()

  def _updateValidators(self):
    for name, wgt in self._fieldWidgets.items():
      validator = wgt.GetValidator()
      validator.SetObject(self.obj)
      validator.TransferToWindow()
      wgt.SetBackgroundColour('Default')
      wgt.SetForegroundColour('Default')

  def OnEditObject(self, evt):
    obj = self.listView.GetSelectedObject()
    if obj:
      self.obj = obj
      self._updateValidators()
      self.dialog.ShowModal()

  def SaveActiveObject(self):
    valid = True
    if self.obj:
      for name, wgt in self._fieldWidgets.items():
        validator = wgt.GetValidator()
        if not validator.Validate(wgt):
          wgt.SetBackgroundColour((255,180,180))
          wgt.SetForegroundColour("Black")
          valid = False
        else:
          wgt.SetBackgroundColour('Default')
          wgt.SetForegroundColour('Default')
      if not valid:
        return False
      for name, wgt in self._fieldWidgets.items():
        wgt.GetValidator().TransferFromWindow()
      db.session.commit()
      pub.sendMessage(self.update_message)
    return True

  def OnDeleteObject(self, evt):
    obj = self.listView.GetSelectedObject()
    if obj and wx.MessageBox(u"Opravdu?", "Kontrola", wx.YES_NO) == wx.YES:
        obj.delete()
        db.session.commit()
        pub.sendMessage(self.delete_message)

  def OnNewObject(self, evt):
    self.obj = self.dbObject()
    db.session.commit()
    self._updateValidators()
    if self.dialog.ShowModal() == wx.ID_CANCEL:
      self.obj.delete()
      db.session.commit()

  def OnDialogSave(self, evt):
    if self.SaveActiveObject():
      self.dialog.EndModal(wx.ID_SAVE)

  def UpdateList(self):
    self.listView.SetObjects(self.dbObject.query.all())
    self.listView.RepopulateList()


class TeamController(DefaultController):
  def __init__(self, dialog, panel):
    self.dbObject = db.Team
    self.objName = "team"
    self.listView = panel.FindWindowByName("teamList")
    self._initList()
    DefaultController.__init__(self, dialog, panel)

    for name in ['number', 'handler_name', 'handler_surname', 'dog_name', 'dog_kennel', 'dog_nick', 'category', 'size', 'paid', 'dog_breed', 'squad']:
      self._fieldWidgets[name] = self.dialog.FindWindowByName(name)
    self._setValidators()

    self.dialog.Bind(wx.EVT_BUTTON, self.OnGetTeamFromWeb, id=xrc.XRCID('getTeamFromWeb'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnNewObject, id=xrc.XRCID('newTeam'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnDeleteObject, id=xrc.XRCID('deleteTeam'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printTeams"))

    self.UpdateList()

  def OnPrint(self, evt):
    printing.PrintTeams()

  def OnRandomizeStartNums(self, evt):
    if wx.MessageBox(u"Zamícháním startovních čísel změníte pořadí startovních listin. Opravdu chcete pokračovat?", "Kontrola", wx.YES_NO) == wx.YES:
      db.RandomizeStartNums()
      pub.sendMessage("team_updated")

  def _initList(self):
    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns([
      ColumnDefn(u"Přítomen", fixedWidth=24, checkStateGetter="IsPresent", checkStateSetter=self.SetTeamPresent),
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
    if value and not team.start_num:
      team.start_num = db.GetNextStartNum()
    team.present = BoolFormatter().coerce(value)
    db.session.commit()
    pub.sendMessage("team_updated")


  def _setValidators(self):
    def wgt(name):
      return self.dialog.FindWindowByName(name)

    for name in ['handler_name', 'handler_surname', 'dog_name']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, None, True))
    for name in ['number', 'dog_kennel', 'dog_breed', 'dog_nick', 'paid']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, None, False))

    validator = OAV.ObjectAttrSelectorValidator(None, 'category', GetFormatter('category'), True)
    wgt('category').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'size', GetFormatter('size'), True)
    wgt('size').SetValidator(validator)
    validator = OAV.ObjectAttrComboValidator(None, 'squad', ListFromCallableFormatter(db.GetSquads), False)
    wgt('squad').SetValidator(validator)

  def OnGetTeamFromWeb(self, evt):
    wx.BeginBusyCursor()
    number = self._fieldWidgets['number'].GetValue()
    if len(number) < 6:
      number = "0" * (6 - len(number)) + number
    f = urllib.urlopen("http://kacr.info/books/xml?number=%s" % number)
    wx.EndBusyCursor()
    if f.getcode() == 200:
      xml = ET.XML(f.read())
      self.obj.number = xml.findtext('number')
      self.obj.handler_name = xml.findtext('handler/first-name')
      self.obj.handler_surname = xml.findtext('handler/surname')
      self.obj.dog_name = xml.findtext('dog/name')
      self.obj.dog_kennel = xml.findtext('dog/kennel')
      self.obj.dog_breed = xml.findtext('dog/breed/name')
      self.obj.size = GetFormatter('size').coerce(xml.findtext('dog/size'))
      self.obj.category = None
      self.obj.present = 1
      self._updateValidators()
    else:
      wx.MessageBox("Průkaz nenalezen.\nZkontrolujte, zda jste správně zadali číslo.", "Chyba")

  def CsvImport(self):
    def unicode_csv_reader():
      def utf_8_encoder(unicode_csv_data):
        for line in unicode_csv_data:
          yield line.encode('utf-8')

      csv_reader = csv.reader(utf_8_encoder(codecs.open('registration.csv', 'rb', 'utf-8')), delimiter=',', quotechar='"')
      for row in csv_reader:
        yield [unicode(cell, 'utf-8') for cell in row]

    for r in unicode_csv_reader():
      if r[8] != u'category':
        t = db.Team(number=r[0], handler_name=r[1], handler_surname=r[2], dog_name=r[3], dog_kennel=r[4], dog_breed=r[5], size=GetFormatter("size").coerce(r[6]), category=GetFormatter("category").coerce(r[8]))
    db.session.commit()

class RunController(DefaultController):
  def __init__(self, dialog, panel):
    self.objName = "run"
    self.dbObject = db.Run
    self.listView = panel.FindWindowByName("runList")
    self.runChooser = xrc.XRCCTRL(panel.GetParent().GetParent(), "runChooser")
    self.runChooserSelectedId = None
    self._initList()
    DefaultController.__init__(self, dialog, panel)

    for name in ['name', 'size', 'category', 'variant', 'date', 'length', 'time', 'max_time', 'judge', 'hurdles', 'time_calc', 'min_speed', 'squads']:
      self._fieldWidgets[name] = self.dialog.FindWindowByName(name)
    self._setValidators()

    self.panel.Bind(wx.EVT_BUTTON, self.OnNewObject, id=xrc.XRCID('newRun'))
    self.panel.Bind(wx.EVT_BUTTON, self.OnDeleteObject, id=xrc.XRCID('deleteRun'))
    self.panel.GetParent().GetParent().Bind(wx.EVT_CHOICE, self.OnRunChoice, id=xrc.XRCID('runChooser'))
    self.dialog.Bind(wx.EVT_CHOICE, self.OnDialogTimeCalc, id=xrc.XRCID('time_calc'))
    self.dialog.Bind(wx.EVT_CHOICE, self.OnDialogVariant, id=xrc.XRCID('variant'))
    self.dialog.Bind(wx.EVT_SHOW, self.OnDialogVariant)
    self.dialog.Bind(wx.EVT_SHOW, self.OnDialogTimeCalc)

    pub.subscribe(self.UpdateRunChooser, "run_updated")
    self.UpdateList()
    self.UpdateRunChooser()

  def _initList(self):
    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns([
      ColumnDefn(u"Název", "left", 150, "name", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Velikost", "center", 120, FormatPartial("size", "size")),
      ColumnDefn(u"Kategorie", "center", 150, FormatPartial("category", "category")),
      ColumnDefn(u"Typ", "left", 150, FormatPartial("variant", "run_variant")),
      ColumnDefn(u"Družstva", "left", 150, FormatPartial("squads", "yes_no")),
      ColumnDefn(u"Rozhodčí", "left", 150, "judge"),
    ])
    self.listView.secondarySortColumns = [0, 1, 2]
    self.listView.SetSortColumn(0, True)

  def _setValidators(self):
    def wgt(name):
      return self.dialog.FindWindowByName(name)

    wgt('name').SetValidator(OAV.ObjectAttrTextValidator(None, 'name', None, True))

    for name in ['date', 'judge']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, None, False))
    for name in ['length', 'time', 'max_time', 'min_speed']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, name, FloatFormatter(), False))

    validator = OAV.ObjectAttrSelectorValidator(None, 'category', GetFormatter('category'), False)
    wgt('category').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'size', GetFormatter('size'), False)
    wgt('size').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'variant', GetFormatter('run_variant'), False)
    wgt('variant').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'time_calc', GetFormatter('run_time_calc'), False)
    wgt('time_calc').SetValidator(validator)
    validator = OAV.ObjectAttrTextValidator(None, 'hurdles', IntFormatter(), False)
    wgt('hurdles').SetValidator(validator)
    validator = OAV.ObjectAttrSelectorValidator(None, 'squads', GetFormatter('yes_no'), False)
    wgt('squads').SetValidator(validator)

  def UpdateRunChooser(self):
    self.runChooserItems = db.Run.query.order_by(db.Run.table.c.name, db.Run.table.c.size, db.Run.table.c.category).all()
    items = []
    found = False

    for run in self.runChooserItems:
      items.append(run.NiceName())
      if self.runChooserSelectedId == run.id:
        found = True

    self.runChooser.SetItems(items)

    if items == []:
      self.runChooser.SetSelection(wx.NOT_FOUND)
      self.runChooserSelectedId = None
    elif not found:
      self.runChooser.SetSelection(0)
      self.runChooserSelectedId = self.runChooserItems[0].id
    else:
      for i, e in zip(range(len(self.runChooserItems)), self.runChooserItems):
        if e.id == self.runChooserSelectedId:
          self.runChooser.SetSelection(i)

    pub.sendMessage("run_selection_changed", runId = self.runChooserSelectedId)

  def OnRunChoice(self, evt):
    self.runChooserSelectedId = self.runChooserItems[self.runChooser.GetSelection()].id
    pub.sendMessage("run_selection_changed", runId = self.runChooserSelectedId)

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

  def OnDialogOpen(self, evt):
    pass


class StartController():
  def __init__(self, dialog=None, panel=None, contextMenu=None):
    self.panel = panel
    self.currentRun = None
    self.dialog = dialog
    self.contextMenu = contextMenu
    self.runChooser = dialog.FindWindowByName("sortByResultsList")
    self.listView = panel.FindWindowByName("startList")
    self._initList()

    pub.subscribe(self.UpdateList, "run_updated")
    pub.subscribe(self.UpdateList, "run_inserted")
    pub.subscribe(self.UpdateList, "run_deleted")
    pub.subscribe(self.UpdateList, "team_updated")
    pub.subscribe(self.UpdateList, "team_inserted")
    pub.subscribe(self.UpdateList, "team_deleted")
    pub.subscribe(self.UpdateRunId, "run_selection_changed")

    self.listView.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
    self.contextMenu.Bind(wx.EVT_MENU, self.SortBeginning, id=xrc.XRCID("startSortBeginning"))
    self.contextMenu.Bind(wx.EVT_MENU, self.SortEnd, id=xrc.XRCID("startSortEnd"))
    self.contextMenu.Bind(wx.EVT_MENU, self.SortReset, id=xrc.XRCID("startSortReset"))
    self.contextMenu.Bind(wx.EVT_MENU, self.SortRemove, id=xrc.XRCID("startSortRemove"))

    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printStart"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnSortByResults, id=xrc.XRCID("sortByResults"))

    self.dialog.SetAffirmativeId(wx.ID_SAVE)

  def OnSortByResults(self, evt):
    if self.currentRun:
      runs = db.Run.query.order_by(db.Run.table.c.name, db.Run.table.c.size, db.Run.table.c.category).all()
      objs = []
      for r in runs:
        r = {"id":r.id, "name":r.NiceName()}
        objs.append(r)
      objs.insert(0, {"id": 0, "name":u"[řadit normálně]"})
      self.runChooser.SetObjects(objs)
      self.runChooser.RepopulateList()
      self.runChooser.DeselectAll()
      for o in objs:
        if o['id'] == self.currentRun.sort_run_id:
          self.runChooser.SelectObject(o)
      if self.dialog.ShowModal() == wx.ID_SAVE:
        selected = self.runChooser.GetSelectedObject()
        if selected:
          self.currentRun.sort_run_id = selected['id']
        else:
          self.currentRun.sort_run_id = 0
        db.session.commit()
        pub.sendMessage("run_updated")

  def OnPrint(self, evt):
    if self.currentRun:
      printing.PrintStart(self.currentRun)

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
      o.sort.value = where
      db.session.commit()
      pub.sendMessage("team_updated")

  def OnRightDown(self, evt):
    if self.currentRun and not self.currentRun.squads and not self.currentRun.sort_run_id:
      i, w = self.listView.HitTest(evt.GetPosition())
      if i != wx.NOT_FOUND:
        self.listView.Select(i)
        self.listView.PopupMenu(self.contextMenu, evt.GetPosition())

  def UpdateRunId(self, runId = None):
    self.currentRun = db.Run.get_by(id=runId)
    self.UpdateList()

  def UpdateList(self):
    if self.currentRun:
      self._initList()
      self.listView.SetObjects(db.GetStartList(self.currentRun, includeRemoved=True))
      self.listView.RepopulateList()

  def _initList(self):
    columns = [
      ColumnDefn(u"Pořadí", "center", 60, "order"),
      ColumnDefn(u"Číslo", "center", 60, "start_num"),
      ColumnDefn(u"Psovod", "left", 150, "handlerFullName", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 150, "dogFullName"),
      ColumnDefn(u"Plemeno", "left", 100, "dog_breed"),
      ColumnDefn(u"Kategorie", "center", 150, FormatPartial("category", "category")),
      ColumnDefn(u"Řazení", "center", 80, valueGetter=lambda t: GetFormatter("start_sort").format(t.sort.value)),
    ]
    if self.currentRun and self.currentRun.squads:
      columns.insert(2, ColumnDefn(u"Družstvo", "left", 100, "squad"))
    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns(columns)
    self.listView.secondarySortColumns = [0]
    self.listView.SetSortColumn(0, True)

    self.runChooser.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.runChooser.SetColumns([ColumnDefn(u"Název", "left", 100, "name")])

class EntryController(DefaultController):
  def __init__(self, dialog=None, panel=None):
    self.panel = panel
    self.currentRun = None
    self.obj = None
    self.listView = panel.FindWindowByName("entryList")
    self.update_message = 'result_updated'
    self.stopwatch = None
    self._initList()
    self.listView._SelectAndFocus(-1)

    self._fieldWidgets = {}
    for name in ['mistakes', 'refusals', 'time', 'disqualified']:
      wgt = self.panel.FindWindowByName(name)
      self._fieldWidgets[name] = wgt
      wgt.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
    self._setValidators()

    pub.subscribe(self.UpdateList, "run_updated")
    pub.subscribe(self.UpdateList, "run_inserted")
    pub.subscribe(self.UpdateList, "run_deleted")
    pub.subscribe(self.UpdateList, "team_updated")
    pub.subscribe(self.UpdateList, "team_inserted")
    pub.subscribe(self.UpdateList, "team_deleted")
    pub.subscribe(self.UpdateListIfCurrent, "run_result_updated")
    pub.subscribe(self.UpdateRunId, "run_selection_changed")

    self.listView.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelectionChange, id=xrc.XRCID("entryList"))
    self.listView.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)

    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printEntry"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnGetTime, id=xrc.XRCID("getTime"))

    self.panel.Bind(wx.EVT_TIMER, self.OnTick)

    self.timer = wx.Timer(self.panel)
    self.timer.Start(100)

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
      printing.PrintEntry(self.currentRun)

  def UpdateRunId(self, runId = None):
    self.currentRun = db.Run.get_by(id=runId)
    self.UpdateList()

  def UpdateListIfCurrent(self, id=None):
    if self.currentRun.id == id:
      self.listView.SetObjects([])
      self.UpdateList()

  def UpdateList(self):
    if self.currentRun:
      self._initList()
      self.listView.SetObjects(db.GetStartList(self.currentRun))
      self.listView.RepopulateList()

  def _initList(self):
    def GetFromResult(attr, formatter, model):
      val = getattr(model.result, attr)
      if formatter:
        val = formatter.format(val)
      return val

    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    columns = [
      ColumnDefn(u"Pořadí", "center", 60, "order"),
      ColumnDefn(u"Číslo", "center", 60, "start_num"),
      ColumnDefn(u"Psovod", "left", 150, "handlerFullName", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 220, "dogFullName"),
      ColumnDefn(u"Kategorie", "center", 70, FormatPartial("category", "category")),
      ColumnDefn(u"Chyby", "center", 80, partial(GetFromResult, "mistakes", IntFormatter())),
      ColumnDefn(u"Odmítnutí", "center", 80, partial(GetFromResult, "refusals", IntFormatter())),
      ColumnDefn(u"Čas", "right", 60, partial(GetFromResult, "time", FloatFormatter())),
      ColumnDefn(u"Diskvalifikován", "center", 100, partial(GetFromResult, "disqualified", GetFormatter("disqualified"))),
      ]
    if self.currentRun and self.currentRun.squads:
      columns.insert(2, ColumnDefn(u"Družstvo", "left", 100, "squad"))
    self.listView.SetColumns(columns)
    self.listView.secondarySortColumns = [0]
    self.listView.SetSortColumn(0, True)

  def OnSelectionChange(self, evt=None):
    index = self.listView.GetFirstSelected()
    self.SaveActiveObject()
    if index != wx.NOT_FOUND or index != -1:
      for w in self._fieldWidgets.values():
        w.Enable()
      team = self.listView.GetObjectAt(index)
      self.panel.FindWindowByName("handler").SetLabel(team.handlerFullName())
      self.panel.FindWindowByName("dog").SetLabel(team.dogFullName())
      self.obj = team.result
    else:
      for w in self._fieldWidgets.values():
        w.Disable()
      self.panel.FindWindowByName("handler").SetLabel("")
      self.panel.FindWindowByName("dog").SetLabel("")
      self.obj = None
    self._updateValidators()

  def SelectNext(self):
    index = self.listView.GetFirstSelected()
    self.listView._SelectAndFocus(index+1)
    if index+2 > self.listView.GetItemCount():
      self.OnSelectionChange()
    else:
      self._fieldWidgets['mistakes'].SetFocus()
      self._fieldWidgets['mistakes'].SetSelection(0,2)

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
    if keycode == wx.WXK_ESCAPE:
      self._updateValidators()
    #elif evt.GetUnicodeKey() == 81:
    #  self._fieldWidgets['mistakes'].SetValue(self._fieldWidgets['mistakes'].GetValue())
    evt.Skip()


class ResultController():
  def __init__(self, dialog=None, panel=None):
    self.panel = panel
    self.currentRun = None
    self.listView = panel.FindWindowByName("resultList")
    self._initList()

    pub.subscribe(self.UpdateList, "run_updated")
    pub.subscribe(self.UpdateList, "run_inserted")
    pub.subscribe(self.UpdateList, "run_deleted")
    pub.subscribe(self.UpdateList, "team_updated")
    pub.subscribe(self.UpdateList, "team_inserted")
    pub.subscribe(self.UpdateList, "team_deleted")
    pub.subscribe(self.UpdateList, "result_updated")
    pub.subscribe(self.UpdateRunId, "run_selection_changed")

    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printResults"))

  def OnPrint(self, evt):
    if self.currentRun:
      printing.PrintResults(self.currentRun)


  def UpdateRunId(self, runId = None):
    self.currentRun = db.Run.get_by(id=runId)
    self.UpdateList()

  def UpdateList(self):
    if self.currentRun:
      if self.currentRun.squads:
        results = db.GetSquadResults(self.currentRun)
        objects = []
        for r in results:
          squad_line = {'rank': r['rank'], 'team_start_num':"", "team_handler":r['name'], "team_dog": "", "team_dog_breed": "", "team_category": "", "result_mistakes":"", "result_refusals":"", "result_time":r['result_time'], "total_penalty":r["total_penalty"], "speed":"", "disq": r["disq"], "squad_line": True}
          objects.append(squad_line)
          for t in r['members']:
            objects.append(t)
      else:
        objects = db.GetResults(self.currentRun)
      self.listView.SetObjects(objects)
      self.listView.RepopulateList()

  def _initList(self):
    def _ifDis(a, fl=False):
      if fl:
        return lambda y: 'DIS' if y['disq'] else FloatFormatter().format(y[a])
      else:
        return lambda y: 'DIS' if y['disq'] else y[a]

    def _ifNotSquad(a, fl=False):
      return lambda y: _ifDis(a, fl)(y) if (not "squad_line" in y.keys() or not self.currentRun.squads) else None

    def _ifSquad(a, fl=False):
      return lambda y: _ifDis(a, fl)(y) if ("squad_line" in y.keys() or not self.currentRun.squads) else None

    def rowFormatter(listItem, obj):
      if "squad_line" in obj.keys():
        listItem.SetBackgroundColour((170, 230, 170))

    columns = [
      ColumnDefn(u"Pořadí", "center", 60, _ifSquad('rank')),
      ColumnDefn(u"Číslo", "center", 60, "team_start_num"),
      ColumnDefn(u"Psovod", "left", 150, "team_handler", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 150, "team_dog"),
      ColumnDefn(u"Plemeno", "left", 100, "team_dog_breed"),
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

    pub.subscribe(self.UpdateList, "run_updated")
    pub.subscribe(self.UpdateList, "run_inserted")
    pub.subscribe(self.UpdateList, "run_deleted")
    pub.subscribe(self.UpdateList, "team_updated")
    pub.subscribe(self.UpdateList, "team_inserted")
    pub.subscribe(self.UpdateList, "team_deleted")
    pub.subscribe(self.UpdateList, "result_updated")

    pub.subscribe(self.UpdateChooser, "run_updated")
    pub.subscribe(self.UpdateChooser, "run_inserted")
    pub.subscribe(self.UpdateChooser, "run_deleted")

    self.chooser.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnSelectionChange, id=xrc.XRCID("sumsChooser"))
    self.panel.Bind(wx.EVT_BUTTON, self.OnPrint, id=xrc.XRCID("printSums"))

  def OnPrint(self, evt):
    if self.runs:
      printing.PrintSums(self.runs)

  def OnSelectionChange(self, evt):
    self.runs = self.chooser.GetSelectedObjects()
    self.UpdateList()

  def UpdateChooser(self):
    self.chooser.SetObjects(db.Run.query.order_by(db.Run.table.c.name, db.Run.table.c.size, db.Run.table.c.category).all())
    self.chooser.RepopulateList()

  def UpdateList(self):
    if self.runs:
      squads = self.runs[0].squads
      for r in self.runs:
        if r.squads != squads:
          wx.MessageBox(u"Nelze vytvářet součty z běhů týmů a jednotlivců zároveň.", u"Chyba")
          self.runs = []
          self.chooser.Select(-1)

    if self.runs:
      if squads:
        sums = db.GetSquadSums(self.runs)
        objects = []
        for s in sums:
          squad_line = {'rank': s['rank'], 'team_start_num':"", "team_handler":s['name'], "team_dog": "", "team_dog_breed": "", "team_category": "", "result_time":s['result_time'], "total_penalty":s["total_penalty"], "speed":"", "disq":s['disq'], "squad_line": True}
          objects.append(squad_line)
          for t in s['members']:
            objects.append(t)
      else:
        objects = db.GetSums(self.runs)
    else:
      objects = []

    self.listView.SetObjects(objects)
    self.listView.RepopulateList()

  def _initLists(self):
    def _ifDis(a, fl=False):
      if fl:
        return lambda y: 'DIS' if y['disq'] else FloatFormatter().format(y[a])
      else:
        return lambda y: 'DIS' if y['disq'] else y[a]

    def _ifSquad(a, fl=False):
      return lambda y: _ifDis(a, fl)(y) if ("squad_line" in y.keys() or not self.runs[0].squads) else None

    def rowFormatter(listItem, obj):
      if "squad_line" in obj.keys():
        listItem.SetBackgroundColour((170, 230, 170))

    self.listView.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.listView.SetColumns([
      ColumnDefn(u"Pořadí", "center", 60, _ifSquad("rank")),
      ColumnDefn(u"Číslo", "center", 60, "team_start_num"),
      ColumnDefn(u"Psovod", "left", 150, "team_handler", minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 150, "team_dog"),
      ColumnDefn(u"Plemeno", "left", 100, "team_dog_breed"),
      ColumnDefn(u"Kategorie", "center", 150, FormatPartial("team_category", "category")),
      ColumnDefn(u"Čas", "right", 60, _ifSquad("result_time", True)),
      ColumnDefn(u"Tr. b.", "right", 60, _ifSquad('total_penalty', True)),
      ColumnDefn(u"Rychlost", "right", 60, _ifSquad("speed", True)),
    ])
    self.listView.rowFormatter = rowFormatter

    self.chooser.cellEditMode = ObjectListView.CELLEDIT_NONE
    self.chooser.SetColumns([
      ColumnDefn(u"Běh", "left", 60, "NiceName", minimumWidth=150, isSpaceFilling=True)
    ])

class SettingsController:
  def __init__(self, dialog):
    self.dialog = dialog
    self._fieldWidgets = {}
    for name in ['competition_name']:
      self._fieldWidgets[name] = self.dialog.FindWindowByName(name)
    self._setValidators()
    self.dialog.Bind(wx.EVT_BUTTON, self.OnDialogSave, id=wx.ID_SAVE)

  def _updateValidators(self):
    for name, wgt in self._fieldWidgets.items():
      obj = db.GetParamObject(name)
      validator = wgt.GetValidator()
      validator.SetObject(obj)
      validator.TransferToWindow()
      wgt.SetBackgroundColour('Default')
      wgt.SetForegroundColour('Default')

  def SaveObjects(self):
    valid = True
    for name, wgt in self._fieldWidgets.items():
      validator = wgt.GetValidator()
      if not validator.Validate(wgt):
        wgt.SetBackgroundColour((255,180,180))
        wgt.SetForegroundColour("Black")
        valid = False
      else:
        wgt.SetBackgroundColour('Default')
        wgt.SetForegroundColour('Default')
    if not valid:
      return False
    for name, wgt in self._fieldWidgets.items():
      wgt.GetValidator().TransferFromWindow()
    db.session.commit()
    pub.sendMessage("settings_updated")
    return True

  def OnDialogSave(self, evt):
    if self.SaveObjects():
      self.dialog.EndModal(wx.ID_SAVE)


  def OnCompetitionSettings(self, evt):
    self._updateValidators()
    self.dialog.ShowModal()

  def _setValidators(self):
    def wgt(name):
      return self.dialog.FindWindowByName(name)

    for name in ['competition_name']:
      wgt(name).SetValidator(OAV.ObjectAttrTextValidator(None, 'value', None, True))


class NetworkedEntryController(EntryController):
  def __init__(self, dialog=None, panel=None, server=None):
    EntryController.__init__(self, dialog, panel)
    self.server = server

  def OnPrint(self, evt):
    wx.MessageBox("Vzdálený tisk není podporován!", "Chyba")

  def UpdateRunId(self, runId = None):
    if runId:
      self.currentRun = self.server.get_run(runId)
    else:
      self.currentRun = None
    self.UpdateList()

  def UpdateList(self):
    if self.currentRun:
      new = self.server.get_start_list(self.currentRun['id'])
      old = self.listView.GetObjects()
      if not old or len(new) != len(old):
        self._initList()
        self.listView.SetObjects(new)
        self.listView.RepopulateList()
        return
      for a, b in zip(new, old):
        if a['id'] != b['id'] or b['result']['run_id'] != self.currentRun['id']:
          self._initList()
          self.listView.SetObjects(new)
          self.listView.RepopulateList()
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
      ColumnDefn(u"Psovod", "left", 150, lambda x: x['handler_name'] + ' ' + x['handler_surname'], minimumWidth=150, isSpaceFilling=True),
      ColumnDefn(u"Pes", "left", 220, lambda x: x['dog_name'] + ' ' + x['dog_kennel']),
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

  def SaveActiveObject(self):
    if self.obj:
      for name, wgt in self._fieldWidgets.items():
        wgt.GetValidator().TransferFromWindow()
      self.server.post_result(self.obj)
      self.UpdateList()

  def OnSelectionChange(self, evt=None):
    index = self.listView.GetFirstSelected()
    self.SaveActiveObject()
    if index != wx.NOT_FOUND or index != -1:
      for w in self._fieldWidgets.values():
        w.Enable()
      team = self.listView.GetObjectAt(index)
      self.panel.FindWindowByName("handler").SetLabel(team['handler_name'] + ' ' + team['handler_surname'])
      self.panel.FindWindowByName("dog").SetLabel(team['dog_name'] + ' ' + team['dog_kennel'])
      self.obj = team['result']
    else:
      for w in self._fieldWidgets.values():
        w.Disable()
      self.panel.FindWindowByName("handler").SetLabel("")
      self.panel.FindWindowByName("dog").SetLabel("")
      self.obj = None
    self._updateValidators()


class NetworkedRunController():
  def __init__(self, chooser, server):
    self.server = server
    self.runChooser = chooser
    self.runChooserSelectedId = None

    self.runChooser.Bind(wx.EVT_CHOICE, self.OnRunChoice, id=xrc.XRCID('runChooser'))

    self.UpdateRunChooser()


  def UpdateRunChooser(self):
    self.runChooserItems = self.server.get_runs()
    items = []
    found = False

    for run in self.runChooserItems:
      items.append(run['name'])
      if self.runChooserSelectedId == run['id']:
        found = True

    self.runChooser.SetItems(items)

    if items == []:
      self.runChooser.SetSelection(wx.NOT_FOUND)
      self.runChooserSelectedId = None
    elif not found:
      self.runChooser.SetSelection(0)
      self.runChooserSelectedId = self.runChooserItems[0]['id']
    else:
      for i, e in zip(range(len(self.runChooserItems)), self.runChooserItems):
        if e['id'] == self.runChooserSelectedId:
          self.runChooser.SetSelection(i)

    pub.sendMessage("run_selection_changed", runId = self.runChooserSelectedId)

  def OnRunChoice(self, evt):
    self.runChooserSelectedId = self.runChooserItems[self.runChooser.GetSelection()]['id']
    pub.sendMessage("run_selection_changed", runId = self.runChooserSelectedId)
