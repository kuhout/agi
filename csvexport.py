# -*- coding: utf-8 -*-

import db
import csv, cStringIO, codecs
from datetime import timedelta
from network import Client
from twisted.internet.defer import inlineCallbacks
from Formatter import *

class UnicodeWriter:
  """
  A CSV writer which will write rows to CSV file "f",
  which is encoded in the given encoding.
  """

  def __init__(self, f, delimiter=";", encoding="utf-8", **kwds):
    # Redirect output to a queue
    self.queue = cStringIO.StringIO()
    self.writer = csv.writer(self.queue, delimiter=delimiter, **kwds)
    self.stream = f
    self.encoder = codecs.getincrementalencoder(encoding)()

  def writerow(self, row):
    self.writer.writerow([unicode(s).encode("utf-8") for s in row])
    # Fetch UTF-8 output from the queue ...
    data = self.queue.getvalue()
    data = data.decode("utf-8")
    # ... and reencode it into the target encoding
    data = self.encoder.encode(data)
    # write to the target stream
    self.stream.write(data)
    # empty queue
    self.queue.truncate(0)

  def writerows(self, rows):
    for row in rows:
      self.writerow(row)


@inlineCallbacks
def CsvExport(filename):
  w = UnicodeWriter(open(filename, "wb"))
  w.writerow(["length", "referee", "standard_time", "hurdle_count", "name", "size", "category", "max_time", "date", "speed", "style"])
  w.writerow(["rank", "handler", "dog", "book", "mistakes", "refusals", "time", "time_penalty", "total_penalty", "rating", "speed"])
  runs = yield Client().sGet(("runs", None))
  params = yield Client().sGet(("params", None))
  for r in runs:
    if r['squads']:
      continue
    time, mtime = yield Client().sGet(("run_times", r['id']))
    date = (params['date_from'] + timedelta(r['day']-1)).strftime("%x")
    speed = r['length']/time if time > 0.0 else 0
    w.writerow(["run", r['length'], r['judge'], time, r['hurdles'], r['nice_name'], GetFormatter("size").format(r['size']), GetFormatter("category").format(r['category']), mtime, date, speed, GetFormatter("run_style_short").format(r['style'])])
    results = yield Client().sGet(("results", r['id']))
    for m in results:
      rating = m['rating'] if r['variant'] == 0 else ""
      w.writerow(["res", m['rank'], m["team_handler"], m["team_dog"], m["team_number"], abs(m["result_mistakes"]), abs(m["result_refusals"]), abs(m["result_time"]), abs(m["time_penalty"]), abs(m["total_penalty"]), rating, abs(m["speed"])])

def SingleRunExport(filename, data):
  w = UnicodeWriter(open(filename, "wb"), ",")
  w.writerow([u"Pořadí", u"Číslo", u"Psovod", u"Pes", u"Chyby", u"Odmítnutí", u"Čas", u"Tr. b. za čas", u"Tr. b.", u"Rychlost"])
  for r in data:
    w.writerow(['DIS' if r['disq'] else r['rank'], r['team_start_num'], r["team_handler"], r["team_dog"], r["result_mistakes"], r["result_refusals"], r['result_time'], r["time_penalty"], r["total_penalty"], r["speed"]])
