# ObjectAttrValidator.py
#
# ------------------------------------------------------------
# Copyright 2004 by Samuel Reynolds. All rights reserved.
#
# Permission to use, copy, modify, and distribute this software and its
# documentation for any purpose and without fee is hereby granted,
# provided that the above copyright notice appear in all copies and that
# both that copyright notice and this permission notice appear in
# supporting documentation, and that the name of Samuel Reynolds
# not be used in advertising or publicity pertaining to distribution
# of the software without specific, written prior permission.
#
# SAMUEL REYNOLDS DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE,
# INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO
# EVENT SHALL SAMUEL REYNOLDS BE LIABLE FOR ANY SPECIAL, INDIRECT, OR
# CONSEQUENTIAL DAMAGES, OR FOR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
# WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
# ------------------------------------------------------------

import wx

class ObjectAttrValidator( wx.PyValidator ):
  """
  Base class for validators that validate *attributes* of
  objects and provide two-way data transfer between those
  attributes and UI controls.
  
  ObjectAttrValidator has no knowledge of the specific
  type of widget to be validated. Responsibility for
  interacting with specific types of widgets is delegated
  to subclasses.
  
  Subclasses must implement the following methods:
    * _setControlValue( self, value )
        Set the value of control to the value provided.
    * _getControlValue( self )
        Return the value of control.
  Remaining logic is implemented in ObjectAttrValidator.
  
  
  CHAMELEON POWERS:
  
  To simplify use in an object-editor context (in which
  a single editor GUI is used to edit multiple objects
  of the same type), ObjectAttrValidator allows changing
  objects on the fly.
  
  For example, if references to field widgets are stored
  in a list self._fieldWidgets, the editor class could
  implement the following methods:
    
    def SetObject( self, editObject ):
      'Set object for editing.'
      self._editObject = editObject
      self._updateValidators()
      self.TransferDataToWindow()
    
    def _updateValidators( self ):
      for wgt in self._fieldWidgets:
        validator = wgt.GetValidator()
        validator.SetObject( self._editObject )
  
  
  FORMATTERS
  
  ObjectAttrValidator uses Formatters for validation and
  two-way reformatting. A Formatter is aware of source data type,
  and handles translation between presentation representation and
  storage representation.
  
  A Formatter must provide the following interface methods:
    * format( stored_value )
        Format a value for presentation.
    * coerce( presentation_value )
        Convert a presentation-formatted value
        to a storage-formatted value (may include
        type conversion such as string->integer).
    * validate( presentation_value )
        Validate a presentation-formatted value.
        Return True if valid or False if invalid.
  
  If a formatter is assigned, the ObjectAttrValidator
  will call the formatter's format, coerce, and validate
  methods at appropriate points in its processing.
  
  With a formatter, there is no need of, for example,
  integer-aware entry fields. The formatter handles
  validation and conversion of the input value.
  """
  
  def __init__( self, obj, attrName, formatter=None, flRequired=True, validationCB=None ):
    super(ObjectAttrValidator,self).__init__()
    
    self.obj          = obj
    self.attrName     = attrName
    self.flRequired   = flRequired
    self.formatter    = formatter
    self.validationCB = validationCB
  
  
  def Clone( self ):
    """
    Return a new validator for the same field of the same object.
    """
    return self.__class__( self.obj, self.attrName, self.formatter,
        self.flRequired, self.validationCB )
  
  
  def SetObject( self, obj ):
    """
    Set or change the object with which the validator interacts.
    
    Useful for changing objects when a single panel is used
    to edit a number of identical objects.
    """
    self.obj = obj
  
  
  def TransferToWindow( self ):
    """
    Transfer data from validator to window.
    
    Delegates actual writing to destination widget to subclass
    via _setControlValue method.
    """
    if self.obj:
      # Copy object attribute value to widget
      val = self._munge( self.obj, self.attrName )
      if val == None:
        val = ''
      if self.formatter:
        val = self.formatter.format( val )
    else:
      val = None

    self._setControlValue( val )
    
    return True
  
  
  def TransferFromWindow( self ):
    """
    Transfer data from window to validator.
    
    Delegates actual reading from destination widget to subclass
    via _getControlValue method.
    
    Only copies data if value is actually changed from attribute value.
    """
    if not self.obj:
      # Nothing to do
      return True
    
    # Get widget value
    val = self._getControlValue()
    
    # Check widget value against attribute value; only copy if changed
    # Get object attribute value
    oldVal = self._munge( self.obj, self.attrName )
    if self.formatter:
      oldVal = self.formatter.format( oldVal )
    if val != oldVal:
      if self.formatter:
        val = self.formatter.coerce( val )
      self._mungeSet( self.obj, val, self.attrName )
    
    return True
  
  
  def Validate( self, win ):
    """
    Validate the contents of the given control.
    
    Default behavior: Anything goes.
    """
    flValid = True
    val = self._getControlValue()
    if self.flRequired and val == '':
      flValid = False
    if flValid and self.formatter:
      flValid = self.formatter.validate( val )
    if self.validationCB:
      self.validationCB( self.obj, self.attrName, val, self.flRequired, flValid )
    return flValid
  
  def _munge(self, modelObject, munger):
      """
      Wrest some value from the given modelObject using the munger.
      With a description like that, you know this method is going to be obscure :-)

      'munger' can be:

      1) a callable.
         This method will return the result of executing 'munger' with 'modelObject' as its parameter.

      2) the name of an attribute of the modelObject.
         If that attribute is callable, this method will return the result of executing that attribute.
         Otherwise, this method will return the value of that attribute.

      3) an index (string or integer) onto the modelObject.
         This allows dictionary-like objects and list-like objects to be used directly.
      """
      if munger is None:
          return None

      # THINK: The following code treats an instance variable with the value of None
      # as if it doesn't exist. Is that best?

      # Try attribute access
      try:
          attr = getattr(modelObject, munger, None)
          if attr is not None:
              try:
                  return attr()
              except TypeError:
                  return attr
      except TypeError:
          # Happens when munger is not a string
          pass

      # Use the callable directly, if possible.
      # In accordance with Guido's rules for Python 3, we just call it and catch the
      # exception
      try:
          return munger(modelObject)
      except TypeError:
          pass

      # Try dictionary-like indexing
      try:
          return modelObject[munger]
      except:
          return None

  def _mungeSet(self, modelObject, value, munger):
      # If there isn't a munger, we can't do anything
      if munger is None:
          return

      # Try indexed access for dictionary or list like objects
      try:
          modelObject[munger] = value
          return
      except:
          pass

      # Is munger the name of some slot in the modelObject?
      try:
          attr = getattr(modelObject, munger)
      except TypeError:
          return
      except AttributeError:
          return

      # If we get to here, it seems that munger is the name of an attribute or
      # property on modelObject. Try to set, realising that many things could still go wrong.
      try:
          setattr(modelObject, munger, value)
      except:
          pass

  def _setControlValue( self, value ):
    """
    Set the value of the target control.
    
    Subclass must implement.
    """
    raise NotImplementedError, 'Subclass must implement _setControlValue'
  
  
  def _getControlValue( self ):
    """
    Return the value from the target control.
    
    Subclass must implement.
    """
    raise NotImplementedError, 'Subclass must implement _getControlValue'


class ObjectAttrTextValidator( ObjectAttrValidator ):
  """
  Validator for TextCtrl widgets.
  """
  def __init__( self, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrTextValidator,self).__init__( *args, **kwargs )
  
  
  def TransferToWindow( self ):
    """
    Transfer data from validator to window.
    
    Delegates actual writing to destination widget to subclass
    via _setControlValue method.
    """
    if not self.obj:
      # Clear the widget
      wgt = self.GetWindow()
      wgt.Clear()
      return True
    
    # Default behavior otherwise
    return super(ObjectAttrTextValidator,self).TransferToWindow()
  
  
  def _setControlValue( self, value ):
    """
    Set the value of the TextCtrl.
    """
    wgt = self.GetWindow()
    wgt.SetValue( value )
  
  
  def _getControlValue( self ):
    """
    Return the value from the TextCtrl.
    """
    wgt = self.GetWindow()
    return wgt.GetValue()


class ObjectAttrSelectorValidator( ObjectAttrValidator ):
  """
  Validator for ControlWithItems widgets (ListBox, Choice).
  
  For wx.ListBox, assumes single-selection mode (wx.LB_SINGLE).
  """
  def __init__( self, obj, attrName, formatter, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrSelectorValidator,self).__init__(
        obj, attrName, formatter, *args, **kwargs )
  
  
  def _getFieldOptions( self, name ):
    """
    Return list of (id,label) pairs.
    """
    return self.formatter.validValues()
  
  
  def _setControlValue( self, value ):
    """
    Set the value *and the options* of the control.
    By the time this is called, the value is already mapped for display.
    """
    wgt = self.GetWindow()
    
    # Get options (list of (id,value) pairs)
    options = self._getFieldOptions( self.attrName )
    # Replace selector contents
    wgt.Clear()
    for id, label in options:
      wgt.Append( label, id )
    
    # Set selection
    if value:
      wgt.SetStringSelection( value )
  
  
  def _getControlValue( self ):
    """
    Return the value from the TextCtrl.
    """
    wgt = self.GetWindow()
    return wgt.GetStringSelection()


class ObjectAttrCheckListBoxValidator( ObjectAttrValidator ):
  """
  Validator for CheckListBox widgets.
  """
  def __init__( self, obj, attrName, formatter, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrCheckListBoxValidator,self).__init__(
        obj, attrName, formatter, *args, **kwargs )
  
  
  ########## REQUIRED INTERFACE ##########
  
  def _getFieldOptions( self, name ):
    """
    Return list of (id,label) pairs.
    """
    return self.formatter.validValues()
  
  
  def _setControlValue( self, value ):
    """
    Set the value *and the options* of the control.
    By the time this is called, the value is already mapped for display.
    
    @param value: Sequence of (value, label) pairs.
    """
    wgt = self.GetWindow()
    
    # Get options (list of (id,value) pairs)
    options = self._getFieldOptions( self.attrName )
    # Sort alphabetically
    options = [ (opt[1], opt) for opt in options ]
    options.sort()
    options = [ opt[1] for opt in options ]
    # Replace selector contents
    self._setControlOptions( options )
    
    # Set selection
    wgt._setControlSelections( value )
  
  
  def _getControlValue( self ):
    """
    Return the value from the TextCtrl.
    
    Returns a list of client data values (not row indices).
    """
    wgt = self.GetWindow()
    selections = wgt.GetStringSelections()
    value = [ wgt.GetClientData( idx ) for idx in selections ]
    return value
  
  
  ########## END REQUIRED INTERFACE ##########
  
  
  def _setControlOptions( self, options ):
    """
    Set up or update control options.
    
    @param options: Sequence of (id,label) pairs.
    """
    wgt = self.GetWindow()
    wgt.Clear()
    for id, label in options:
      wgt.Append( label, id )
  
  
  def _setControlSelections( self, value ):
    """
    Select the specified items in the control, and unselect others.
    
    @param value: Integer or sequence of integers representing
            the data value(s) of item(s) to be selected.
            
            If None or empty sequence, all currently-selected
            items will be deselected.
            
            Any items in value that are not found in the
            control have no effect.
    """
    if value == None:
      value = tuple()
    elif not isinstance(value,(list,tuple)):
      value = ( value, )
    
    numItems = wgt.GetCount()
    for idx in xrange( 0, numItems ):
      itemData = wgt.GetClientData( idx )
      if itemData in value:
        if not wgt.IsChecked( idx ):
          wgt.Check( idx, True )
      else:
        if wgt.IsChecked( idx ):
          wgt.Check( idx, False )


class ObjectAttrRadioBoxValidator( ObjectAttrValidator ):
  """
  Validator for RadioBox widgets.
  """
  def __init__( self, obj, attrName, formatter, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrRadioBoxValidator,self).__init__(
        obj, attrName, formatter, *args, **kwargs )
  
  
  def _setControlValue( self, value ):
    """
    Set the value *and the options* of the control.
    By the time this is called, the value is already mapped for display.
    """
    wgt = self.GetWindow()
    wgt.SetStringSelection( value )
  
  
  def _getControlValue( self ):
    """
    Return the value from the TextCtrl.
    """
    wgt = self.GetWindow()
    return wgt.GetStringSelection()


class ObjectAttrLabelValidator( ObjectAttrValidator ):
  """
  Validator for StaticText widgets.
  """
  def __init__( self, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrLabelValidator,self).__init__( *args, **kwargs )
  
  
  def TransferToWindow( self ):
    """
    Transfer data from validator to window.
    
    Delegates actual writing to destination widget to subclass
    via _setControlValue method.
    """
    if self.obj == None:
      # Clear the widget
      wgt = self.GetWindow()
      wgt.SetLabel("")
      return True
    
    # Default behavior otherwise
    return super(ObjectAttrLabelValidator,self).TransferToWindow()
  
  
  def _setControlValue( self, value ):
    """
    Set the value of the TextCtrl.
    """
    wgt = self.GetWindow()
    wgt.SetLabel( value )
  
  
  def _getControlValue( self ):
    """
    Return the value from the TextCtrl.
    """
    wgt = self.GetWindow()
    return wgt.GetLabel()


class ObjectAttrCheckBoxValidator( ObjectAttrValidator ):
  """
  Validator for CheckBox widgets.
  """
  def __init__( self, obj, attrName, formatter, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrCheckBoxValidator,self).__init__(
        obj, attrName, formatter, *args, **kwargs )
  
  
  def _setControlValue( self, value ):
    """
    Set the value *and the options* of the control.
    By the time this is called, the value is already mapped for display.
    """
    wgt = self.GetWindow()
    if not type(value) == type(True):
      value = False
    wgt.SetValue(value)
    
  def _getControlValue( self ):
    """
    Return the value from the TextCtrl.
    """
    wgt = self.GetWindow()
    return wgt.GetValue()

class ObjectAttrSpinValidator( ObjectAttrValidator ):
  """
  Validator for SpinCtrl widgets.
  """
  def __init__( self, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrSpinValidator,self).__init__( *args, **kwargs )
  
  
  def TransferToWindow( self ):
    """
    Transfer data from validator to window.
    
    Delegates actual writing to destination widget to subclass
    via _setControlValue method.
    """
    if not self.obj:
      # Clear the widget
      wgt = self.GetWindow()
      wgt.SetValue(0)
      return True
    
    # Default behavior otherwise
    return super(ObjectAttrSpinValidator,self).TransferToWindow()
  
  
  def _setControlValue( self, value ):
    """
    Set the value of the SpinCtrl.
    """
    wgt = self.GetWindow()
    wgt.SetValue( int(value) )
  
  
  def _getControlValue( self ):
    """
    Return the value from the SpinCtrl.
    """
    wgt = self.GetWindow()
    return wgt.GetValue()


class ObjectAttrComboValidator( ObjectAttrValidator ):
  """
  Validator for ComboBox widgets
  """
  def __init__( self, obj, attrName, formatter, *args, **kwargs ):
    """ Standard constructor. """
    super(ObjectAttrComboValidator,self).__init__(
        obj, attrName, formatter, *args, **kwargs )


  def _getFieldOptions( self, name ):
    """
    Return list of (id,label) pairs.
    """
    return self.formatter.values()


  def _setControlValue( self, value ):
    """
    Set the value *and the options* of the control.
    By the time this is called, the value is already mapped for display.
    """
    wgt = self.GetWindow()

    # Get options (list of (id,value) pairs)
    options = self._getFieldOptions( self.attrName )
    # Replace combo contents
    wgt.Clear()
    for label in options:
      wgt.Append( label )

    # Set selection
    wgt.SetValue( value )


  def _getControlValue( self ):
    """
    Return the value from the TextCtrl.
    """
    wgt = self.GetWindow()
    return wgt.GetValue()

