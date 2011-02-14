# -*- coding: utf-8 -*-
import db
import wx
import threading
import time

from twisted.internet import reactor, defer, error, threads, protocol
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.spread import pb
from twisted.python import log

EVT_RELOAD_ID = wx.NewId()
EVT_WAITING_ID = wx.NewId()
EVT_CALLBACK_ID = wx.NewId()

def EVT_RELOAD(win, func):
  win.Connect(-1, -1, EVT_RELOAD_ID, func)

def EVT_CALLBACK(win, func):
  win.Connect(-1, -1, EVT_CALLBACK_ID, func)

def EVT_WAITING(win, func):
  win.Connect(-1, -1, EVT_WAITING_ID, func)

class ReloadEvent(wx.PyEvent):
  def __init__(self, what, arg):
    wx.PyEvent.__init__(self)
    self.SetEventType(EVT_RELOAD_ID)
    self.what = what
    self.arg = arg

class CallbackEvent(wx.PyEvent):
  def __init__(self, callback, *args, **kwargs):
    wx.PyEvent.__init__(self)
    self.SetEventType(EVT_CALLBACK_ID)
    self.callback = callback
    self.args = args
    self.kwargs = kwargs

class WaitingEvent(wx.PyEvent):
  def __init__(self, value):
    wx.PyEvent.__init__(self)
    self.SetEventType(EVT_WAITING_ID)
    self.value = value

class ServerProcessProtocol(protocol.ProcessProtocol):
  def __init__(self, callback):
    self.callback = callback

  def Kill(self):
    self.transport.signalProcess('TERM')

  def connectionMade(self):
    self.transport.closeStdin()

  def outReceived(self, data):
    """
    This just lets us know that the server started
    """
    self.callback()

  def errReceived(self, data):
    print(data)

class ClientResponder(pb.Referenceable):
  def remote_update_cache(self, value):
    reactor.callFromThread(Client().UpdateCache, value)

  def remote_invalidate_cache(self, values):
    reactor.callFromThread(Client().InvalidateCache, values)

  def remote_close(self):
    Client().Disconnect()

class Request(pb.Referenceable):
  def __init__(self, callback):
    self.callback = callback

  def remote_done(self, value):
    self.callback(value)

class Client(object):
  __shared_state = {}

  def __init__(self):
    self.__dict__ = self.__shared_state

  def Connect(self, address, port, notify, callback):
    self.address = address
    self.port = port
    self.notify = notify
    self.server = None
    self.connected_callback = callback
    self.cache = {}
    factory = pb.PBClientFactory()
    reactor.connectTCP(self.address, self.port, factory)
    d = factory.getRootObject()
    d.addCallback(self._gotRootObject)
    d.addErrback(self._connectionError)

  def Disconnect(self):
    wx.PostEvent(self.notify, CallbackEvent(self.notify.OnClose, None))

  def _gotRootObject(self, obj):
    self.server = obj
    self._callRemote("register", [lambda _: self._sentResponder()], ClientResponder())

  def _sentResponder(self):
    wx.PostEvent(self.notify, CallbackEvent(self.connected_callback))

  @inlineCallbacks
  def sGet(self, what):
    if what in self.cache.keys():
      returnValue(self.cache[what])
    else:
      wx.PostEvent(self.notify, WaitingEvent(True))
      result = yield self.server.callRemote("sget", what)
      wx.PostEvent(self.notify, WaitingEvent(False))
      self.cache[result[0]] = result[1]
      returnValue(result[1])

  #obsolete
  def Get(self, what, finished_callback):
    reactor.callFromThread(self._get, what, finished_callback)

  def _get(self, what, finished_callback):
    if what in self.cache.keys():
      wx.PostEvent(self.notify, CallbackEvent(finished_callback, self.cache[what]))
    else:
      wx.PostEvent(self.notify, WaitingEvent(True))
      self._callRemote("get", [], what, Request(lambda result: self._receivedData(result, finished_callback)))

  def _receivedData(self, result, finished_callback):
    self.cache[result[0]] = result[1]
    wx.PostEvent(self.notify, WaitingEvent(False))
    wx.PostEvent(self.notify, CallbackEvent(finished_callback, result[1]))

  def Post(self, what, value, *args, **kwargs):
    reactor.callFromThread(self._post, what, value, *args, **kwargs)

  def _post(self, what, value, *args, **kwargs):
    self._callRemote("post", [], what, value, *args, **kwargs)

  def Delete(self, what, id):
    reactor.callFromThread(self._post, what, {'id':id}, destroy=True)

  def _postedData(self):
    pass

  def RandomizeStartNums(self):
    reactor.callFromThread(self._callRemote, "randomize_start_nums", [])

  def ImportTeams(self, teams):
    reactor.callFromThread(self._callRemote, "import_teams", [], teams)

  def Create(self, what, finished_callback):
    reactor.callFromThread(self._create, what, finished_callback)

  def _create(self, what, finished_callback):
    wx.PostEvent(self.notify, WaitingEvent(True))
    self._callRemote("create", [lambda result: self._receivedCreated(result, finished_callback)], what)

  def _receivedCreated(self, result, finished_callback):
    wx.PostEvent(self.notify, WaitingEvent(False))
    wx.PostEvent(self.notify, CallbackEvent(finished_callback, result))

  def _callRemote(self, func, callbacks, *args, **kwargs):
    d = self.server.callRemote(func, *args, **kwargs)
    for c in callbacks:
      d.addCallback(c)

  def _connectionError(self, f):
    wx.PostEvent(self.notify, WaitingEvent(False))
    wx.PostEvent(self.notify, CallbackEvent(wx.MessageBox, u"Chyba spojení", "Chyba"))

  def UpdateCache(self, value):
    self.cache[value[0]] = value[1]
    wx.PostEvent(self.notify, ReloadEvent(value[0][0], value[0][1]))

  def InvalidateCache(self, values):
    for value in values:
      if value in self.cache.keys():
        del self.cache[value]
        wx.PostEvent(self.notify, ReloadEvent(value[0], value[1]))

class TwistedThread(threading.Thread):
  def run(self):
    reactor.run(installSignalHandlers=False)

class ServerResponder(pb.Root):
  def __init__(self):
    self.lock = threading.Lock()
    db.ServerCache().Initialize(self.lock)
    self.clients = []

  def remote_randomize_start_nums(self):
    u = db.RandomizeStartNums()
    self._invalidate_remote_caches(u)

  def remote_import_teams(self, teams):
    u = db.ImportTeams(teams)
    self._invalidate_remote_caches(u)

  def remote_sget(self, what):
    if what[0] == 'teams':
      call = db.GetTeams
    elif what[0] == 'runs':
      call = db.GetRuns
    elif what[0] == 'breeds':
      call = db.GetBreeds
    elif what[0] == 'results':
      call = lambda: db.GetResults(what[1])
    elif what[0] == 'params':
      call = lambda: db.GetParams()
    elif what[0] == 'squads':
      call = lambda: db.GetSquads(what[1])
    elif what[0] == 'squad_results':
      call = lambda: db.GetSquadResults(what[1])
    elif what[0] == 'sums':
      call = lambda: db.GetSums(what[1])
    elif what[0] == 'squad_sums':
      call = lambda: db.GetSquadSums(what[1])
    elif what[0] == 'run_times':
      call = lambda: db.GetRunTimes(what[1])
    elif what[0] == 'start_list':
      call = lambda: db.GetStartList(what[1], False)
    elif what[0] == 'start_list_with_removed':
      call = lambda: db.GetStartList(what[1], True)
    else:
      return (what, None)

    return threads.deferToThread(self._query, what, call)

  def remote_get(self, what, request=None):
    """
    Runs a query on a local database asynchronously.
    Requires a tuple describing the query and a Result object that
    will get called back when the query is done
    """

    if what[0] == 'teams':
      call = db.GetTeams
    elif what[0] == 'runs':
      call = db.GetRuns
    elif what[0] == 'breeds':
      call = db.GetBreeds
    elif what[0] == 'results':
      call = lambda: db.GetResults(what[1])
    elif what[0] == 'params':
      call = lambda: db.GetParams()
    elif what[0] == 'squads':
      call = lambda: db.GetSquads(what[1])
    elif what[0] == 'squad_results':
      call = lambda: db.GetSquadResults(what[1])
    elif what[0] == 'sums':
      call = lambda: db.GetSums(what[1])
    elif what[0] == 'squad_sums':
      call = lambda: db.GetSquadSums(what[1])
    elif what[0] == 'run_times':
      call = lambda: db.GetRunTimes(what[1])
    elif what[0] == 'start_list':
      call = lambda: db.GetStartList(what[1], False)
    elif what[0] == 'start_list_with_removed':
      call = lambda: db.GetStartList(what[1], True)
    else:
      return (what, None)

    if request:
      callback = lambda r: self._send_result(r, request)
    else:
      callback = lambda r: self._update_remote_caches(r)

    self._get_result(what, call).addCallback(callback)

  def _get_result(self, what, call):
    d = threads.deferToThread(self._query, what, call)
    return d

  def _query(self, what, call):
    result = db.ServerCache().Get(what, call)
    return ((what, result))

  def _send_result(self, value, request):
    request.callRemote("done", value)

  def remote_post(self, what, values, *args, **kwargs):
    d = threads.deferToThread(self._update, what, values, *args, **kwargs)
    d.addCallback(self._post_done)

  def _update(self, what, values, *args, **kwargs):
    updated = db.Update(what, values, *args, **kwargs)
    return what, updated

  def _post_done(self, value):
    self._invalidate_remote_caches(value[1])

  def _update_remote_caches(self, value):
    if value[1] is not None:
      self._clientCall('update_cache', value)

  def _invalidate_remote_caches(self, values):
    self._clientCall('invalidate_cache', values)

  def remote_create(self, what):
    return db.Create(what)

  def remote_register(self, reg):
    self.clients.append(reg)
    reg.notifyOnDisconnect(self.clients.remove)

  def _clientCall(self, method, *args, **kwargs):
    l = []
    for c in self.clients[:]:
      l.append(c.callRemote(method, *args, **kwargs))
    return defer.DeferredList(l)

  def Close(self):
    d = defer.Deferred()
    reactor.callLater(0, self._do_closing, d)
    return d

  def _do_closing(self, d):
    db.session.flush()
    self._clientCall("close").addCallback(d.callback)
