# coding=utf-8

import wx
import locale
import copy
from ObjectListView import FastObjectListView, ColumnDefn, EVT_CELL_EDIT_FINISHED, OLVEvent, ObjectListView

class MyOLV(FastObjectListView):
  def __init__(self, parent, style=0, sortable=True):
    FastObjectListView.__init__(self, parent, -1, style=wx.LC_REPORT|wx.SUNKEN_BORDER|style, sortable=sortable)
    self.parent = parent
    self.SetEmptyListMsg(u"Žádné položky")
    if self.smallImageList == None:
      self.SetImageLists()


  def _ReSort(self):
    self.SortBy(self.sortColumnIndex, self.sortAscending)
    self._FormatAllRows()


  def GetSecondarySortColumns(self):
    if hasattr(self, 'secondarySortColumns'):
      cols = copy.copy(self.secondarySortColumns)
    else:
      cols = []
    if cols.count(self.sortColumnIndex):
      cols.remove(self.sortColumnIndex)
    return [self.columns[c] for c in cols]


  def _SortObjects(self, modelObjects=None, sortColumn=None, secondarySortColumns=None):
    """
    Sort the given modelObjects in place.

    This does not change the information shown in the control itself.
    """
    if modelObjects is None:
      modelObjects = self.modelObjects
    if sortColumn is None:
      sortColumn = self.GetSortColumn()
    if secondarySortColumns is None:
      secondarySortColumns = self.GetSecondarySortColumns()

    # If we don't have a sort column, we can't sort -- duhh
    if sortColumn is None:
      return

    # Let the world have a chance to sort the model objects
    evt = OLVEvent.SortEvent(self, self.sortColumnIndex, self.sortAscending, True)
    self.GetEventHandler().ProcessEvent(evt)
    if evt.IsVetoed() or evt.wasHandled:
      return

    # When sorting large groups, this is called a lot. Make it efficent.
    # It is more efficient (by about 30%) to try to call lower() and catch the
    # exception than it is to test for the class
    def _getSortValue(x):
      primary = sortColumn.GetValue(x)
      try:
        primary = locale.strxfrm(primary.lower().encode('utf-8'))
      except AttributeError:
        pass
      result = [primary]
      for col in secondarySortColumns:
        secondary = col.GetValue(x)
        try:
          secondary = locale.strxfrm(secondary.lower().encode('utf-8'))
        except AttributeError:
          pass
        result.append(secondary)
      return tuple(result)

    modelObjects.sort(key=_getSortValue, reverse=(not self.sortAscending))

    # Sorting invalidates our object map
    self.objectToIndexMap = None

class ColumnDefn(ColumnDefn):
    def _StringToValue(self, value, converter):
      """
      Convert the given value to a string, using the given converter
      """
      try:
        return converter(value)
      except TypeError:
        pass

      if converter and isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.strftime(self.stringConverter)

      # By default, None is changed to an empty string.
      if not converter and not value and value != 0:
        return ""

      fmt = converter or "%s"
      try:
        return fmt % value
      except UnicodeError:
        return unicode(fmt) % value

