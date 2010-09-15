import db
import wx
import threading

from twisted.internet import reactor
from twisted.web import xmlrpc, server

EVT_RELOAD_ID = wx.NewId()

def EVT_RELOAD(win, func):
  win.Connect(-1, -1, EVT_RELOAD_ID, func)

class ReloadResultsEvent(wx.PyEvent):
  def __init__(self, runId):
    wx.PyEvent.__init__(self)
    self.SetEventType(EVT_RELOAD_ID)
    self.runId = runId

class Server(xmlrpc.XMLRPC):
  def __init__(self, notify=None):
    self.notify = notify
    xmlrpc.XMLRPC.__init__(self, allowNone=True)

  def xmlrpc_post_result(self, result):
    db.UpdateResultFromDict(result)
    wx.PostEvent(self.notify, ReloadResultsEvent(result['run_id']))

  def xmlrpc_get_runs(self):
    runs = db.Run.query.order_by(db.Run.table.c.name, db.Run.table.c.size, db.Run.table.c.category).all()
    run_list = []
    for r in runs:
      r = {'id': r.id, 'name':r.NiceName()}
      run_list.append(r)
    return run_list

  def xmlrpc_get_run(self, id):
    run = db.Run.get_by(id=id)
    return run.to_dict()

  def xmlrpc_get_start_list(self, run_id):
    run = db.Run.get_by(id=run_id)
    start_list = db.GetStartList(run)
    dicts = []
    for s in start_list:
      t = s.to_dict()
      t['order'] = s.order
      t['result'] = s.result.to_dict()
      t['sort'] = s.sort.to_dict()
      dicts.append(t)
    return dicts

class ServerThread(threading.Thread):
  def __init__(self, port, notify):
    self.port = port
    self.notify = notify
    threading.Thread.__init__(self)

  def run(self):
    reactor.listenTCP(self.port, server.Site(Server(self.notify)))
    reactor.run(installSignalHandlers=0)

  def stop(self):
    print "stopping"
    #reactor.stop()
