# -*- coding: utf-8 -*-

class EnumType( object ):
    """
    Enumerated-values class.
    
    Allows reference to enumerated values by name
    or by index (i.e., bidirectional mapping).
    """
    def __init__( self, *names ):
        # Remember names list for reference by index
        self._names = list(names)
    
    def __contains__( self, item ):
        try:
            trans = self[item]
            return True
        except:
            return False
    
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
                for idx in range(0, len(self._names) ) ]
    
    
    def names( self ):
        return self._names[:]

    def get(self, key):
      return self.__getitem__(key)
    
    def _nameToEnum( self, name ):
      for _i, _s in enumerate( self._names ):
        if _s == name:
          return _i
      raise ValueError
