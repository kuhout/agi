# -*- coding: utf-8 -*-

import re, time, copy
from EnumType import *
from functools import partial

def GetFormatter(name):
  enums = {
      'size': {0: "S",1:"M",2:"L"},
      'start_sort': {0:"", 1:u"Začátek", 2:u"Konec", 3:u"Vyřazen", 4:u"Standardně vyřazen", 5:u"Výjimka, začátek", 6:u"Výjimka, konec", 7:u"Výjimka"},
      'category': {0:"A1",1:"A2",2:"A3",3:'V'},
      'run_style': {0:u"Agility",1:u"Zkoušky Agility",2:u"Jumping",3:u"Zkoušky Jumping", 4:u"Speciální"},
      'run_style_short': {0:u"A",1:u"ZkA",2:u"J",3:u"ZkJ", 4:u"Spec"},
      'run_variant': {0:u"Zkoušky", 1:u"Open"},
      'run_time_calc': {0:u"Ruční", 1:u"Podle času nejlepšího"},
      'yes_no': {0:"Ne", 1:"Ano"},
      'disqualified': {0:"", 1:"DIS"}
    }

  return EnumFormatter(EnumType(enums[name]), False)


def FormatPartial(attr, formatter):
  return partial(FormatAttribute, attr, formatter)

def FormatAttribute(attr, formatter, obj):
  if type(formatter) == type(""):
    formatter = GetFormatter(formatter)
  try:
    val = getattr(obj, attr)
  except:
    val = obj[attr]
  return formatter.format(val)


class Formatter( object ):
    """
    Formatter/validator for data values.
    """
    def __init__( self, *args, **kwargs ):
        pass

    def validate( self, value ):
        """
        Return true if value is valid for the field.
        value is a string from the UI.
        """
        return True

    def format( self, value ):
        """Format a value for presentation in the UI."""
        if value == None:
            return ''
        return unicode(value)

    def coerce( self, value ):
        """Convert a string from the UI into a storable value."""
        return value


class FormatterMeta( type ):
    def __new__( cls, classname, bases, classdict ):
        newdict = copy.copy( classdict )

        # Generate __init__ method
        # Direct descendants of Formatter automatically get __init__.
        # Indirect descendants don't automatically get one.
        if Formatter in bases:
            def __init__( self, *args, **kwargs ):
                Formatter.__init__( self, *args, **kwargs )
                initialize = getattr( self, 'initialize', None )
                if initialize:
                    initialize()
            newdict['__init__'] = __init__
        else:
            def __init__( self, *args, **kwargs ):
                super(self.__class__,self).__init__( *args, **kwargs)
                initialize = getattr( self, 'initialize', None )
                if initialize:
                    initialize()
            newdict['__init__'] = __init__

        # Generate validate-by-RE method if specified
        re_validation = newdict.get( 're_validation', None )
        if re_validation:
            # Override validate method
            re_validation_flags = newdict.get( 're_validation_flags', 0 )
            newdict['_re_validation'] = re.compile( re_validation, re_validation_flags )
            def validate( self, value ):
                return ( self._re_validation.match( value ) != None )
            newdict['validate'] = validate

        # Delegate class creation to the expert
        return type.__new__( cls, classname, bases, newdict )


class EnumFormatter( Formatter ):
    """
    Formatter for enumerated (EnumType) data values.
    """
    def __init__( self, enumeration, *args, **kwargs ):

        super(EnumFormatter,self).__init__( *args, **kwargs )

        self.enumeration = enumeration


    def validValues( self ):
        """
        Return list of valid value (id,label) pairs.
        """
        return copy.copy( self.enumeration.items() )


    def validate( self, value ):
        """
        Return true if value is valid for the field.
        value is a string from the UI.
        """
        if value == "":
          return True
        else:
          vv = [ s for i, s in self.validValues() ]
          return ( value in vv )


    def format( self, value ):
        """Format a value for presentation in the UI."""
        if value == None or value == "":
          return ""
        else:
          return self.enumeration[value]


    def coerce( self, value ):
        """Convert a string from the UI into a storable value."""
        if not self.validate(value):
          print value
        if value == "":
          return None
        else:
          return self.enumeration.get(value)


class FloatFormatter( Formatter ):
    """
    Formatter for floating point data values.
    """
    def __init__( self, *args, **kwargs ):
        super(FloatFormatter,self).__init__( *args, **kwargs )


    def validate( self, value ):
        """
        Return true if value is valid for the field.
        value is a string from the UI.
        """
        try:
          value = float(re.sub(r',', '.', value))
        except:
          return False
        if value != value:
          return False
        return True


    def format( self, value ):
        """Format a value for presentation in the UI."""
        if value == "" or value == None:
          return ""
        if not value:
          value = 0.0
        return re.sub(r'\.', ',', "%.2f" % float(value))


    def coerce( self, value ):
        """Convert a string from the UI into a storable value."""
        return float(re.sub(r'\,', '.', value) or 0)


class BoolFormatter( Formatter ):
    """
    Formatter for boolean data values.
    """
    def __init__( self, *args, **kwargs ):
        super(BoolFormatter,self).__init__( *args, **kwargs )


    def validate( self, value ):
        """
        Return true if value is valid for the field.
        value is a string from the UI.
        """
        return type(value) == type(True)

    def format( self, value ):
        """Format a value for presentation in the UI."""
        return value == 1

    def coerce( self, value ):
        """Convert a string from the UI into a storable value."""
        if value:
          return 1
        else:
          return 0


class IntFormatter( Formatter ):
    """
    Formatter for integers.
    """
    def __init__( self, *args, **kwargs ):
        super(IntFormatter,self).__init__( *args, **kwargs )


    def validate( self, value ):
        """
        Return true if value is valid for the field.
        value is a string from the UI.
        """
        if value == "":
          return True
        try:
          value = int(value)
        except:
          return False
        if value != value:
          return False
        return True


    def format( self, value ):
        """Format a value for presentation in the UI."""
        if value == '' or value == None:
          return "0"
        else:
          return str(value)

    def coerce( self, value ):
        """Convert a string from the UI into a storable value."""
        if value == '' or value == None:
          return 0
        else:
          return int(value)


class ListFromCallableFormatter( Formatter ):
    """
    Formatter providing a list of values and no validation
    """
    def __init__( self, func, *args, **kwargs ):

        super(ListFromCallableFormatter,self).__init__( *args, **kwargs )
        self.func = func


    def values( self ):
        """
        Return list of values
        """
        res = self.func()
        return map(lambda x: "" if x == None else unicode(x), res)

class ListFormatter( Formatter ):
    """
    Formatter providing a list of values and no validation
    """
    def __init__( self, l, *args, **kwargs ):

        super(ListFormatter,self).__init__( *args, **kwargs )
        self.l = l


    def values( self ):
        """
        Return list of values
        """
        return self.l
