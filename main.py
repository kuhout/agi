# coding=utf-8

import db

import wx
import locale
import ObjectListView
from MyOLV import MyOLV
from wx import xrc
from pubsub import pub
from ObjectListView import ObjectListView, ColumnDefn, EVT_CELL_EDIT_FINISHED


class App(wx.App):

  def OnInit(self):
    locale.setlocale(locale.LC_ALL, 'cs_CZ.utf8')
    self.locale = wx.Locale(wx.LANGUAGE_CZECH)
    self.res = xrc.XmlResource('agility.xrc')
    self.frame = self.res.LoadFrame(None, 'mainFrame')
    self. _initOLV()
    self.frame.Bind(wx.EVT_BUTTON, self.NewBook, id=xrc.XRCID('newBook'))
    self.frame.Show()
    return True

  def _initOLV(self):
    self.bookList = TeamList(self.frame)
    self.res.AttachUnknownControl('bookList', self.bookList)

  def NewBook(self, evt):
    book = db.Book()
    db.session.commit()
    pub.sendMessage("books_updated")
    self.bookList.Edit(book)


class TeamList(MyOLV):
  def __init__(self, parent):
    MyOLV.__init__(self, parent)
    self.queryFunction = db.GetBooks
    self.cellEditMode = ObjectListView.CELLEDIT_DOUBLECLICK
    self.SetColumns([
      ColumnDefn(u"Příjmení", "left", 150, "handler_surname"),
      ColumnDefn(u"Jméno", "left", 120, "handler_name"),
      ColumnDefn(u"Pes", "left", 150, "dog_name"),
      ColumnDefn(u"Chovná stanice", "left", 150, "dog_kennel"),
      ColumnDefn(u"Plemeno", "left", 150, "dog_breed"),
      ColumnDefn(u"Kategorie", "left", 150, "category"),
      ColumnDefn(u"Velikost", "left", 150, "size"),
      ColumnDefn(u"Číslo průkazu", "left", 150, "number"),
    ])
    self.secondarySortColumns = [0, 1, 2, 3]
    self.SetSortColumn(0, True)
    self.OnDataUpdate()
    self.Bind(wx.EVT_RIGHT_DOWN, self.OnRightDown)
    self.Bind(EVT_CELL_EDIT_FINISHED, self.OnCellChange)
    pub.subscribe(self.OnDataUpdate, "books_updated")

  def OnCellChange(self, evt):
    if not self.tabbing:
      if evt.rowModel.IsBlank():
        self.DeselectAll()
        evt.rowModel.delete()
      db.session.commit()
      evt.Skip()
      pub.sendMessage("books_updated")

  def OnRightDown(self, evt):
    print self.GetSelectedObjects()


if __name__ == '__main__':
  app = App(False)
  app.MainLoop()
