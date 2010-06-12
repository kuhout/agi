# coding=utf-8

import wx
import locale
from ObjectListView import ObjectListView, ColumnDefn, EVT_CELL_EDIT_FINISHED, OLVEvent

class MyOLV(ObjectListView):
  def __init__(self, parent):
    ObjectListView.__init__(self, parent, -1, style=wx.LC_REPORT|wx.SUNKEN_BORDER)
    self.tabbing = False
    self.parent = parent
    self.SetEmptyListMsg(u"Žádné položky")

  def Edit(self, model):
    self.SelectObject(model, True, True)
    self.StartCellEdit(self.GetIndexOf(model), 0)

  def OnDataUpdate(self):
    obj = self.GetSelectedObject()
    self.SetObjects(self.queryFunction())
    self._ReSort()
    if obj:
      self._SelectAndFocus(self.GetIndexOf(obj))


  def _ReSort(self):
    self.SortBy(self.sortColumnIndex, self.sortAscending)
    self._FormatAllRows()

  def _SortItemsNow(self):
    sortColumn = self.GetSortColumn()
    if not sortColumn:
      return

    secondary = self.GetSecondarySortColumns()

    def _singleObjectComparer(col, object1, object2):
      value1 = col.GetValue(object1)
      value2 = col.GetValue(object2)
      try:
        return locale.strcoll(value1.lower(), value2.lower())
      except:
        return cmp(value1, value2)

    def _objectComparer(object1, object2):
      result = _singleObjectComparer(sortColumn, object1, object2)
      for col in secondary:
        if result == 0:
          result = _singleObjectComparer(col, object1, object2)
        else:
          break
      return result

    self.SortListItemsBy(_objectComparer)

  def _HandleTabKey(self, isShiftDown):
    (rowBeingEdited, subItem) = self.cellBeingEdited

    self.tabbing = True
    shadowSelection = self.selectionBeforeCellEdit
    self.selectionBeforeCellEdit = []
    self.FinishCellEdit()
    self.tabbing = False

    if self.HasFlag(wx.LC_REPORT):
      columnCount = self.GetColumnCount()
      for ignored in range(columnCount-1):
        if isShiftDown:
          subItem = (columnCount + subItem - 1) % columnCount
        else:
          subItem = (subItem + 1) % columnCount
        if self.columns[subItem].isEditable and self.GetColumnWidth(subItem) > 0:
          self.StartCellEdit(rowBeingEdited, subItem)
          break

    self.selectionBeforeCellEdit = shadowSelection

  def FinishCellEdit(self):
    """
    Finish and commit an edit operation on the given cell.
    """
    (rowIndex, subItemIndex) = self.cellBeingEdited

    # Give the world the chance to veto the edit, or to change its characteristics
    rowModel = self.GetObjectAt(rowIndex)
    evt = OLVEvent.CellEditFinishingEvent(self, rowIndex, subItemIndex, rowModel,
                                          self.cellEditor.GetValue(), self.cellEditor, False)
    self.GetEventHandler().ProcessEvent(evt)
    if not evt.IsVetoed() and evt.cellValue is not None:
        self.columns[subItemIndex].SetValue(rowModel, evt.cellValue)
        self.RefreshIndex(rowIndex, rowModel)

    self._CleanupCellEdit()

    evt = OLVEvent.CellEditFinishedEvent(self, rowIndex, subItemIndex, rowModel, False)
    self.GetEventHandler().ProcessEvent(evt)


  def CancelCellEdit(self):
    """
    Cancel an edit operation on the given cell.
    """
    # Tell the world that the user cancelled the edit
    (rowIndex, subItemIndex) = self.cellBeingEdited
    evt = OLVEvent.CellEditFinishingEvent(self, rowIndex, subItemIndex,
                                          self.GetObjectAt(rowIndex),
                                          self.cellEditor.GetValue(),
                                          self.cellEditor,
                                          True)
    self.GetEventHandler().ProcessEvent(evt)

    self._CleanupCellEdit()

    evt = OLVEvent.CellEditFinishedEvent(self, rowIndex, subItemIndex, rowModel, True)
    self.GetEventHandler().ProcessEvent(evt)

  def GetSecondarySortColumns(self):
    cols = [0,1,2]
    if cols.count(self.sortColumnIndex):
      cols.remove(self.sortColumnIndex)
    return [self.columns[c] for c in cols]

