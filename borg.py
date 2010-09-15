class Borg:
  __shared_state = {}
  def __init__(self):
    self.__dict__ = self.__shared_state

class Singleton:
  instance = {}
  def __init__(self):
    if self.__class__ not in Singleton.instance:
      Singleton.instance[self.__class__] = Singleton.__OnlyOne()
      return True
    else :
      print 'warning : trying to recreate a singleton'
      return False

  def __getattr__(self, name):
    return getattr(self.instance[self.__class__], name)

  def __setattr__(self, name, value):
    return setattr(self.instance[self.__class__], name, value)
