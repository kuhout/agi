# -*- coding: utf-8 -*-
import db
import network
import sys
from twisted.internet import reactor
from twisted.spread import pb


def _printPort():
  print "8787"
  sys.stdout.flush()

db.OpenFile(sys.argv[1])
server = network.ServerResponder()
reactor.listenTCP(8787, pb.PBServerFactory(server))
reactor.addSystemEventTrigger("before", "shutdown", server.Close)
reactor.addSystemEventTrigger("after", "startup", _printPort)
reactor.run()
