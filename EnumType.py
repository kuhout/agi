# -*- coding: utf-8 -*-
import copy

class EnumType( object ):
    """
    Enumerated-values class.
    
    Allows reference to enumerated values by name
    or by index (i.e., bidirectional mapping).
    """
    def __init__( self, d ):
        # Remember names list for reference by index
        self._names = dict(d)
    
    def __contains__( self, item ):
        return item in self._names.values()
    
    def __iter__( self ):
        return enumerate( self._names )
    
    def __getitem__( self, key ):
        if type(key) == type(0):
            return self._names[key]
        else:
            return self._nameToEnum( key )
    
    def __len__( self ):
        return len(self._names)
    
    def items( self ):
        return [ (idx, self._names[idx])
                for idx in self._names.keys() ]

    def names( self ):
        return copy.copy(self._names)

    def get(self, key):
      return self.__getitem__(key)
    
    def _nameToEnum( self, name ):
      for i in self.items():
        if i[1] == name:
          return i[0]
      raise ValueError
