# coding=utf-8

from elixir import *
import random
import os
import shutil
import csv, codecs
from math import ceil
from Formatter import *
from sqlalchemy.sql import and_, or_, not_, text
from sqlalchemy.sql.expression import distinct, alias, label
from sqlalchemy.orm import aliased
from sqlalchemy import select, func, UniqueConstraint

class Param(Entity):
  competition_name = Field(Unicode(100), default=u"")
  date_from = Field(Date())
  date_to = Field(Date())

class Team(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  start_num = Field(Integer, default=0)
  number = Field(Unicode(6), default=u"")
  handler_name = Field(Unicode(50), default=u"")
  handler_surname = Field(Unicode(50), default=u"")
  dog_name = Field(Unicode(50), default=u"")
  dog_kennel = Field(Unicode(50), default=u"")
  dog_breed = ManyToOne('Breed')
  dog_nick = Field(Unicode(50), default=u"")
  squad = Field(Unicode(50), default=u"")
  osa = Field(Unicode(50), default=u"")
  category = Field(Integer, default=0)
  size = Field(Integer, default=0)
  present = Field(Integer, default=0)
  paid = Field(Unicode(50), default=u"")
  registered = Field(Integer, default=0)
  confirmed = Field(Integer, default=0)
  def_sort = Field(Integer, default=0)
  results = OneToMany('Result')
  sorts = OneToMany('Sort')

  def handlerFullName(self):
    return self.handler_name + ' ' + self.handler_surname

  def dogFullName(self):
    return (self.dog_name + ' ' + self.dog_kennel).strip()

  def IsPresent(self):
    return self.present == 1

  def SetBreed(self, breed):
    b = Breed.get_by(name=breed)
    self.dog_breed_id = b.id

  def IsBlank(self):
    d = self.to_dict()
    del d["id"]
    for val in d.itervalues():
      if val:
        return False
    return True

class Breed(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  name = Field(Unicode(100), default=u"")
  dogs = OneToMany('Team')

class BreedFilter(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  breed = ManyToOne('Breed', ondelete="cascade", column_kwargs={'index':True})
  run = ManyToOne('Run', ondelete="cascade", column_kwargs={'index':True})

class Result(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  team = ManyToOne('Team', ondelete="cascade", column_kwargs={'index':True})
  run = ManyToOne('Run', ondelete="cascade", column_kwargs={'index':True})
  time = Field(Float, default=0.0)
  refusals = Field(Integer, default=0)
  mistakes = Field(Integer, default=0)
  disqualified = Field(Integer, default=0)
  using_table_options(UniqueConstraint('run_id', 'team_id'))

class Run(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  name = Field(Unicode(50), default=u"")
  day = Field(Integer, default=1)
  category = Field(Integer, default=0)
  size = Field(Integer, default=0)
  variant = Field(Integer, default=0)
  style = Field(Integer, default=0)
  time_calc = Field(Integer, default=0)
  squads = Field(Integer, default=0)
  length = Field(Float, default=0.0)
  time = Field(Float, default=0.0)
  max_time = Field(Float, default=0.0)
  min_speed = Field(Float, default=0.0)
  judge = Field(Unicode(50), default=u"")
  hurdles = Field(Integer, default=0)
  sort_run_id = Field(Integer, default=0)
  results = OneToMany('Result')
  sorts = OneToMany('Sort')

  def NiceName(self):
    cat = GetFormatter('category').format(self.category)
    size = GetFormatter('size').format(self.size)
    return "%s %s%s" % (self.name, size, cat)


class Sort(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  team = ManyToOne('Team', ondelete="cascade", column_kwargs={'index':True})
  run = ManyToOne('Run', ondelete="cascade", column_kwargs={'index':True})
  value = Field(Integer, default=0)
  using_table_options(UniqueConstraint('run_id', 'team_id'))


class ServerCache():
  __shared_state = {}
  def __init__(self):
    self.__dict__ = self.__shared_state

  def Initialize(self, lock):
    self.lock = lock
    self.Clear()

  def Clear(self):
    self.cache = {}

  def Get(self, what, call):
    self.lock.acquire()
    if what in self.cache.keys():
      res = self.cache[what]
      self.lock.release()
    else:
      self.lock.release()
      res = call()
      self.lock.acquire()
      self.cache[what] = res
      self.lock.release()
    return res

  def Invalidate(self, what):
    self.lock.acquire()
    for w in what:
      if w in self.cache.keys():
        del self.cache[w]
    self.lock.release()
    return what

  def InvalidateRun(self, id, except_runs=False):
    invalidate = [('squad_results', id), ('run_times', id), ('results', id), ('start_list', id), ('start_list_with_removed', id)]
    if not except_runs:
      invalidate.append(('runs', None))
    for r in Run.query.filter(Run.table.c.sort_run_id == id).all():
      invalidate.append(('start_list', r.id))
      invalidate.append(('start_list_with_removed', r.id))
    self.lock.acquire()
    for k in self.cache.keys():
      if k[0] == 'sums' and id in k[1]:
        invalidate.append(k)
    self.lock.release()
    return self.Invalidate(invalidate)

  def InvalidateAll(self, exc=[]):
    self.lock.acquire()
    inv = []
    for k in self.cache.keys():
      if not k in exc:
        del self.cache[k]
        inv.append(k)
    self.lock.release()
    return inv

def Update(classname, values, extraParams={}, *args, **kwargs):
  if classname == 'params':
    return SetParams(values)

  id = values['id']
  del values['id']
  c = globals()[classname.capitalize()]

  obj = c.get_by(id=id)
  if 'destroy' in kwargs.keys():
    obj.delete()
  else:
    for col in c.table.columns:
      if col.name in values.keys():
        setattr(obj, col.name, values[col.name])
    if 'grab_start_num' in kwargs.keys():
      #teams
      setattr(obj, 'start_num', GetNextStartNum())
    if classname == 'run':
      BreedFilter.query.filter_by(run_id=obj.id).delete()
      for b in values['breeds']:
        f = BreedFilter(breed_id=b, run_id=obj.id)
  session.commit()

  if classname == 'result':
    return ServerCache().InvalidateRun(obj.run_id, except_runs=True)
  if classname == 'run':
    if "generate_runs" in extraParams:
      GenerateRuns(obj)
    return ServerCache().InvalidateRun(obj.id)
  if classname == 'sort':
    return ServerCache().InvalidateRun(obj.run_id)
  if classname == 'team':
    return ServerCache().InvalidateAll(exc=[('runs', None)])

def Create(classname):
  c = globals()[classname.capitalize()]
  obj = c()
  session.commit()
  r = obj.to_dict()
  if classname == 'run':
    r['breeds'] = []
  return r

def GenerateRuns(run):
  def clone(a,b):
    for c in a.table.c:
      if not c.name.endswith('id'):
        setattr(b, c.name, getattr(a, c.name))

  sizes = [0,1,2]
  if run.variant == 1:
    categories = [None]
  else:
    categories = [0,1,2]

  for s in sizes:
    for c in categories:
      if not (run.category == c and run.size == s):
        n = Run()
        clone(run, n)
        n.category = c
        n.size = s

  session.commit()
  return True

def GetTeams():
  res = []
  for t in Team.query.order_by(Team.table.c.handler_surname, Team.table.c.handler_name, Team.table.c.dog_name).outerjoin(Breed.table).add_entity(Breed).all():
    team = t[0].to_dict()
    if t[1]:
      team['dog_breed'] = t[1].name
    else:
      team['dog_breed'] = ""
    res.append(team)
  return res

def GetBreeds():
  return map(lambda t: t.to_dict(), Breed.query.order_by(Breed.table.c.name).all())

def GetRuns():
  res = []
  for r in Run.query.order_by(Run.table.c.day, Run.table.c.name, Run.table.c.size, Run.table.c.category).all():
    d = r.to_dict()
    d['nice_name'] = r.NiceName()
    d['breeds'] = []
    for b in BreedFilter.query.filter_by(run_id=r.id).all():
      d['breeds'].append(b.breed_id)
    res.append(d)
  return res

def OpenFile(filename, params=None):
  if not os.path.isfile(filename):
    shutil.copy("default.db", filename)
  metadata.bind = "sqlite:///" + filename
  setup_all()
  session.configure(autocommit=False, autoflush=True)
  if params:
    p = Param.get_by()
    for col in Param.table.columns:
      if col.name in params.keys():
        setattr(p, col.name, params[col.name])
    session.commit()
  #expire_on_commit=False)
  #metadata.bind.engine.connect().execute("PRAGMA synchronous = OFF")


def GetRowsAsDicts(selectable):
  t = session.execute(selectable).fetchall()
  return map(dict, t)

def RandomizeStartNums(cats = False):
  query = Team.query
  if cats:
    query = query.order_by(Team.table.c.size, Team.table.c.category)
  teams = query.order_by(func.random()).all()

  for i in range(len(teams)):
    teams[i].start_num = i+1

  session.commit()
  return ServerCache().InvalidateAll(exc=[('runs', None)])

def GetNextStartNum():
  n = session.query(select([func.max(Team.table.c.start_num)])).one()[0]
  if n is None:
    n = 1
  else:
    n = n+1
  return n

def GetParams():
  p = Param.get_by()
  return p.to_dict()

def SetParams(obj):
  p = Param.get_by()
  for col in Param.table.columns:
    if col.name in obj.keys():
      setattr(p, col.name, obj[col.name])
  session.commit()
  return ServerCache().Invalidate([('params', None)])

def DoSpacing(a, space=7):
  #ensures proper spacing of handlers in start lists
  def app(k):
    res.append(k)
    last.append(k['handler_name'] + k['handler_surname'])
    if len(last) > space:
      last.pop(0)

  stack, last, res, c = [], [], [], 1

  for e in a:
    for k in stack:
      if k['handler_name'] + k['handler_surname'] not in last:
        stack.remove(k)
        app(k)
    if e['handler_name'] + e['handler_surname'] not in last:
      app(e)
    else:
      stack.append(e)

  if len(stack):
    res.extend(stack)
  return res, len(stack) > 0

def GetSquads(run_id=None):
  conditions = (Team.table.c.present > 0)
  if run_id:
    run = Run.get_by(id=run_id)
    conditions = conditions & (Team.table.c.size==run.size) & (Team.table.c.present.op('&')(1 << (run.day - 1)))
  res = session.execute(select([distinct(Team.table.c.squad)], conditions)).fetchall()
  squads = [item for sublist in res for item in sublist]
  for s in squads[:]:
    if not s:
      squads.remove(s)
  return squads

def GetStartList(run_id, includeRemoved=False):
  run = Run.get_by(id=run_id)
  if run:
    breeds = BreedFilter.query.filter_by(run=run).all()
    sq = aliased(Result, Result.query.filter_by(run=run).subquery())
    sort = aliased(Sort, Sort.query.filter_by(run=run).subquery())
    query = Team.query.filter_by(size=run.size).filter(Team.table.c.present.op('&')(1 << (run.day - 1)))
    if len(breeds):
      query = query.filter(Team.table.c.dog_breed_id.in_([b.breed_id for b in breeds]))
    if run.variant == 0:
      query = query.filter_by(category=run.category)
    else:
      query = query.filter(Team.table.c.category!=3)

    if run.squads:
      query = query.filter(func.ifnull(Team.table.c.squad, "") != "")
      #magic numbers ahoy! these are actually random
      order = [func.length(Team.table.c.squad) * 133 % 204, Team.table.c.squad, Team.table.c.start_num]
    else:
      #beginning, end, start number
      order = [func.ifnull(sort.value, 0) != 1, func.ifnull(sort.value, 0) == 2, Team.table.c.start_num]

    s = ((func.ifnull(sort.value, 0) == 0) & (Team.table.c.def_sort == 1)) | ((func.ifnull(sort.value, 0) == 3) & (Team.table.c.def_sort == 0))
    if includeRemoved:
      #put removed teams at the end
      order.insert(0, s)
    else:
      #or don't get them at all
      query = query.filter(s != 1)

    query = query.add_entity(sq).add_entity(sort).outerjoin(sq).outerjoin(sort).add_entity(Breed).outerjoin(Breed.table).order_by(*order)
    query = query.all()

    result = []
    new_entries = False
    for t in query:
      team = t[0].to_dict()
      if t[1]:
        res = t[1]
      else:
        res = Result(team_id=team['id'], run_id=run.id)
        new_entries = True
      if t[2]:
        sort = t[2]
      else:
        sort = Sort(team_id=team['id'], run_id=run.id)
        new_entries = True
      team['result'] = res.to_dict()
      team['sort'] = sort.to_dict()
      team['breed'] = t[3].to_dict()
      if team['def_sort']:
        #def_sorts of one get special sorting messages, see enum definitons
        team['sort']['value'] += 4
      result.append(team)

    if new_entries:
      session.commit()
      return GetStartList(run_id, includeRemoved)

    if not run.squads and not run.sort_run_id:
      spacing = 8
      while spacing > 0:
        result, r = DoSpacing(result)
        result.reverse()
        result, r = DoSpacing(result)
        result.reverse()
        if not r:
          break
        spacing -= 1
    elif run.sort_run_id:
      sort = []
      if run.squads:
        squad_results = ServerCache().Get(('squad_results', run.sort_run_id), lambda: GetSquadResults(run.sort_run_id))
        for r in squad_results:
          for m in r['members']:
            sort.append(m['team_id'])

      else:
        indiv_results = ServerCache().Get(('results', run.sort_run_id), lambda: GetResults(run.sort_run_id))
        for r in indiv_results:
          sort.append(r['team_id'])

      for r in result[:]:
        if not r['id'] in sort:
          result.remove(r)
      result.sort(key=lambda t: sort.index(t['id']), reverse=True)


    order = 0
    for t in result:
      order += 1
      t['order'] = order

    return result
  else:
    return []


def GetRunTimes(run_id):
  run = Run.get_by(id=run_id)
  if run:
    if run.time_calc:
      query, aliases = ResultQuery(run_id, 999, 999)
      prelim = session.execute(query).fetchall()
      if not len(prelim) or prelim[0]['speed'] < run.min_speed:
        if not run.min_speed:
          time = 0
        else:
          time = run.length / run.min_speed * run.time
      else:
        time = prelim[0]['result_time'] * run.time
      max_time = time * run.max_time
      return (ceil(time), ceil(max_time))
    else:
      return (run.time, run.max_time)
  else:
    return (0, 0)


def GetSquadSums(runs):
  if runs:
    run_results = []
    for run_id in runs:
      res = ServerCache().Get(('squad_results', run_id), lambda: GetSquadResults(run_id))
      res = dict(map(lambda x: (x['name'], x), res))
      run_results.append(res)

    sums = run_results[0].values()
    for run in run_results[1:]:
      for squad in sums[:]:
        if squad['name'] in run.keys():
          add = run[squad['name']]
          for attr in ['penalty', 'time_pen', 'total_penalty', 'result_time', 'disq', 'disq_count']:
            squad[attr] += add[attr]

    sums.sort(key=lambda s: (s['disq']*s['disq_count'], s['total_penalty'], s['penalty'], s['result_time']))
  else:
    sums = []

  num = 0
  for s in sums:
    num += 1
    s['rank'] = num
    s['members'].sort(key=lambda m: m['team_start_num'])
    for m in s['members']:
      del m['total_penalty']
      del m['result_time']
  return sums


def GetSquadResults(run_id):
  squads = []
  run = Run.get_by(id=run_id)
  if run:
    query, aliases = ResultQuery(run_id, include_absent=True)
    squad_list = ServerCache().Get(('squads', run_id), lambda: GetSquads(run_id))
    time, max_time = ServerCache().Get(('run_times', run_id), lambda: GetRunTimes(run_id))
    if None in squad_list:
      squad_list.remove(None)
    if "" in squad_list:
      squad_list.remove("")

    for s in squad_list:
      squery = query.filter(func.ifnull(aliases['team'].c.squad, "") == s)
      rows = session.execute(squery).fetchall()

      results = []
      for r in rows:
        r = dict(zip(r.keys(), r.values()))
        results.append(r)

      squad = {"name": s,
        "penalty": reduce(lambda x,y: x + y['penalty'], results[0:3], 0),
        "time_pen": reduce(lambda x,y: x + y['time_penalty'], results[0:3], 0),
        "total_penalty": reduce(lambda x,y: x + y['time_penalty'] + y['penalty'], results[0:3], 0),
        "result_time": reduce(lambda x,y: x + y['result_time'], results[0:3], 0),
        "disq_count": reduce(lambda x,y: x + y['disq'], results, 0),
        "disq": len(results) - reduce(lambda x,y: x + y['disq'], results, 0) < 3,
        'members': results
        }

      squads.append(squad)

    squads.sort(key=lambda s: (s['disq']* s['disq_count'], s['total_penalty'], s['penalty'], s['result_time']))

    rank = 0
    for s in squads:
      rank += 1
      s['rank'] = rank

  return squads


def ResultQuery(run_id, max_time=None, time=None, include_absent=False, results_from_id=None):
  if max_time == None and time == None:
    time, max_time = ServerCache().Get(('run_times', run_id), lambda: GetRunTimes(run_id))

  run = Run.get_by(id=run_id)
  if run:
    r = session.query()
    team = alias(select([Team.table], Team.table.c.present.op('&')(1 << (run.day - 1))), alias="team")
    sort = alias(select([Sort.table], Sort.table.c.run_id==run_id), alias="sort")
    breed = alias(select([Breed.table]), alias="breed")
    res = alias(select([Result.table], Result.table.c.run_id==run_id), alias="result")
    r = r.add_entity(Team, alias=team)
    if results_from_id:
      res_from = alias(select([Result.table], Result.table.c.run_id==results_from_id), alias="result_from")
      r = r.add_entity(Result, alias=res_from)
      r = r.add_entity(Result, alias=res)
      r = r.outerjoin(res).outerjoin(res_from)
    else:
      r = r.add_entity(Result, alias=res)
      r = r.outerjoin(res)
    r = r.add_entity(Breed, alias=breed)
    r = r.add_entity(Sort, alias=sort)
    r = r.outerjoin(sort).outerjoin(breed)
    r = r.add_columns((team.c.handler_name + ' ' + team.c.handler_surname).label("team_handler"))
    r = r.add_columns((team.c.dog_name + ' ' + team.c.dog_kennel).label("team_dog"))
    r = r.add_columns((res.c.mistakes*5 + res.c.refusals*5).label("penalty"))
    r = r.add_columns(((res.c.time - time)*(res.c.time > time)).label("time_penalty"))
    r = r.add_columns(((res.c.time - time)*(res.c.time > time) + res.c.mistakes*5 + res.c.refusals*5).label("total_penalty"))
    r = r.add_columns(func.ifnull(run.length/res.c.time, 0).label('speed'))


    disq = (res.c.time > max_time) | (res.c.disqualified) | (res.c.refusals >= 3)
    if include_absent:
      disq = disq | (res.c.time == 0)
    r = r.add_columns(disq.label("disq"))

    if run.variant == 0:
      r = r.filter(team.c.category == run.category)
    else:
      r = r.filter(team.c.category != 3)

    s = ((func.ifnull(sort.c.value, 0) == 0) & (team.c.def_sort == 1)) | ((func.ifnull(sort.c.value, 0) == 3) & (team.c.def_sort == 0))
    r = r.filter((s != 1) & ((res.c.time > 0) | 'disq'))
    r = r.order_by("disq, total_penalty, penalty, result_time")

    return r, {'team': team, 'result': res, 'sort': sort}
  else:
    return None, None

def GetResults(run_id):
  run = Run.get_by(id=run_id)
  if run:
    query, aliases = ResultQuery(run_id)
    rows = session.execute(query).fetchall()

    num = 0
    lastorder = ()
    result = []
    for r in rows:
      r = dict(zip(r.keys(), r.values()))
      order = (r['total_penalty'], r['penalty'], r['result_time'])
      if order != lastorder:
        num += 1
      lastorder = order
      if not r['disq'] and r['total_penalty'] < 26:
        if r['total_penalty'] < 16:
          if r['total_penalty'] < 6:
            r['rating'] = "V"
          else:
            r['rating'] = "VD"
        else:
          r['rating'] = "D"
      else:
        r['rating'] = "BO"

      if r['disq']:
        r['rank'] = 0
      else:
        r['rank'] = num
      result.append(r)

    return result
  else:
    return []

def GetSums(runs):
  if runs:
    run_objs = []
    presence_mask = 0
    for run_id in runs:
      run = Run.get_by(id=run_id)
      run_objs.append(run)
      presence_mask = presence_mask | (1 << (run.day - 1))
    team = alias(select([Team.table], Team.table.c.present.op('&')(presence_mask)), alias="team")
    breed = alias(select([Breed.table]), alias="breed")
    r = session.query()
    r = r.add_entity(Team, alias=team)
    r = r.outerjoin(breed)
    r = r.add_entity(Breed, alias=breed)
    pen = []
    time_pen = []
    time = []
    sorts = []
    disq = []
    ran = []
    lengths = 0

    for run in run_objs:
      run_time, run_max_time = ServerCache().Get(('run_times', run.id), lambda: GetRunTimes(run.id))
      res = alias(select([Result.table], Result.table.c.run_id==run.id))
      sort = alias(select([Sort.table], Sort.table.c.run_id==run.id))
      pen.append(res.c.mistakes*5 + res.c.refusals*5)
      time_pen.append((res.c.time - run_time)*(res.c.time > run_time))
      time.append(res.c.time)
      s = ((func.ifnull(sort.c.value, 0) == 0) & (team.c.def_sort == 1)) | ((func.ifnull(sort.c.value, 0) == 3) & (team.c.def_sort == 0))
      sorts.append(s)
      lengths = lengths + run.length
      dis = ((res.c.time > run_max_time) | (res.c.disqualified) | (res.c.refusals >= 3))
      disq.append(dis)
      ran.append((res.c.time > 0) | dis)
      r = r.outerjoin(res).outerjoin(sort)

    r = r.add_columns(reduce(lambda x,y: x+y, pen).label("penalty"))
    r = r.add_columns(reduce(lambda x,y: x+y, time_pen).label("time_penalty"))
    r = r.add_columns(reduce(lambda x,y: x+y, pen+time_pen).label("total_penalty"))
    r = r.add_columns(reduce(lambda x,y: x*y, time).label("time_fac"))
    r = r.add_columns(reduce(lambda x,y: x+y, ran).label("ran_all"))
    r = r.add_columns(reduce(lambda x,y: x+y, disq).label("disq"))
    r = r.add_columns(reduce(lambda x,y: max(x, y), sorts).label("sort"))
    r = r.add_columns("(team.handler_name || ' '  || team.handler_surname) team_handler")
    r = r.add_columns("(team.dog_name || ' '  || team.dog_kennel) team_dog")
    result_time = reduce(lambda x,y: x+y, time).label("result_time")
    r = r.add_columns(result_time)
    r = r.add_columns(func.ifnull(lengths/result_time, 0).label("speed"))

    r = r.filter("sort == 0 AND ran_all == %d" % len(runs))
    r = r.order_by("disq, total_penalty, penalty, result_time")

    rows = session.execute(r).fetchall()

    num = 0
    sums = []
    for r in rows:
      r = dict(zip(r.keys(), r.values()))
      num += 1
      r['rank'] = num
      sums.append(r)
  else:
    sums = []

  return sums

def ImportTeams(data):
  for r in data:
    registered = 0
    for d in r[15].split(", "):
      a = 1 << int(d) - 1
      registered = registered | a
    t = Team(number=r[0],
             handler_name=r[1],
             handler_surname=r[2],
             dog_name=r[3],
             dog_kennel=r[4],
             size=GetFormatter("size").coerce(r[6]),
             osa=r[7],
             dog_nick=r[9],
             category=GetFormatter("category").coerce(r[10]),
             confirmed=GetFormatter("yes_no").coerce(r[13]),
             paid=FloatFormatter().coerce(r[14]),
             registered=registered)
    t.SetBreed(r[5])
  session.commit()
  return ServerCache().InvalidateAll(exc=[('runs', None)])

