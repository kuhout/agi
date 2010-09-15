# coding=utf-8
from elixir import *
from pubsub import pub
import random
import os
from math import ceil
from Formatter import *
from sqlalchemy.sql import and_, or_, not_, text
from sqlalchemy.sql.expression import distinct, alias, label
from sqlalchemy.orm import aliased
from sqlalchemy import select, func, UniqueConstraint

class Param(Entity):
  name = Field(Unicode(50), unique=True, primary_key=True, index=True)
  value = Field(Unicode(50), default=u"")

class Team(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  start_num = Field(Integer, default=0)
  number = Field(Unicode(6), default=u"")
  handler_name = Field(Unicode(50), default=u"")
  handler_surname = Field(Unicode(50), default=u"")
  dog_name = Field(Unicode(50), default=u"")
  dog_kennel = Field(Unicode(50), default=u"")
  dog_breed = Field(Unicode(50), default=u"")
  dog_nick = Field(Unicode(50), default=u"")
  squad = Field(Unicode(50), default=u"")
  category = Field(Integer, default=0)
  size = Field(Integer, default=0)
  present = Field(Integer, default=0)
  paid = Field(Unicode(50), default=u"")
  results = OneToMany('Result')
  sorts = OneToMany('Sort')

  def handlerFullName(self):
    return self.handler_name + ' ' + self.handler_surname

  def dogFullName(self):
    return (self.dog_name + ' ' + self.dog_kennel).strip()

  def IsPresent(self):
    return self.present == 1

  def IsBlank(self):
    d = self.to_dict()
    del d["id"]
    for val in d.itervalues():
      if val:
        return False
    return True


class Result(Entity):
  time = Field(Float, default=0.0)
  refusals = Field(Integer, default=0)
  mistakes = Field(Integer, default=0)
  disqualified = Field(Integer, default=0)
  team = ManyToOne('Team', ondelete="cascade", column_kwargs={'primary_key':True, 'index':True})
  run = ManyToOne('Run', ondelete="cascade", column_kwargs={'primary_key':True, 'index':True})
  using_table_options(UniqueConstraint('run_id', 'team_id'))


class Run(Entity):
  id = Field(Integer, autoincrement=True, unique=True, primary_key=True, index=True)
  name = Field(Unicode(50), default=u"")
  date = Field(Unicode(50), default=u"")
  category = Field(Integer, default=0)
  size = Field(Integer, default=0)
  variant = Field(Integer, default=0)
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
  team = ManyToOne('Team', ondelete="cascade", column_kwargs={'primary_key':True, 'index':True})
  run = ManyToOne('Run', ondelete="cascade", column_kwargs={'primary_key':True, 'index':True})
  value = Field(Integer, default=0)
  using_table_options(UniqueConstraint('run_id', 'team_id'))



def UpdateResultFromDict(result):
  if result:
    obj = Result.get_by(team_id=result['team_id'], run_id=result['run_id'])
    for a in ['refusals', 'mistakes', 'time', 'disqualified']:
      setattr(obj, a, result[a])
    session.commit()

def OpenFile(filename):
  metadata.bind = "sqlite:///" + filename
  #metadata.bind.echo = True
  setup_all()
  if not os.path.isfile(filename):
    create_all()
  session.configure(autocommit=False, autoflush=True)
  #expire_on_commit=False)
  metadata.bind.engine.connect().execute("PRAGMA synchronous = OFF")


def GetResultsAsDicts(selectable):
  t = session.execute(selectable).fetchall()
  results = []
  for r in t:
    r = dict(zip(r.keys(), r.values()))
    results.append(r)
  return results

def RandomizeStartNums():
  teams = Team.query.all()
  random.shuffle(teams)

  for i in range(len(teams)):
    teams[i].start_num = i+1

  session.commit()

def GetNextStartNum():
  n = session.query(select([func.max(Team.table.c.start_num)])).one()[0]
  if n == None:
    n = 1
  else:
    n = n+1
  return n

def GetParamObject(name):
  p = Param.get_by(name=name)
  if p:
    return p
  else:
    return Param(name=name)

def GetParam(name):
  p = GetParamObject(name)
  if p:
    return p.value
  else:
    return ""

def SetParam(name, value):
  p = Param.get_by(name=name)
  if p:
    p.value = value
  else:
    p = Param(name=name, value=value)
  session.commit()

def DoSpacing(a, space=7):
  #ensures proper spacing of handlers
  def app(k):
    res.append(k)
    last.append(k.handlerFullName())
    if len(last) > space:
      last.pop(0)

  stack, last, res, c = [], [], [], 1

  for e in a:
    for k in stack:
      if k.handlerFullName() not in last:
        stack.remove(k)
        app(k)
    if e.handlerFullName() not in last:
      app(e)
    else:
      stack.append(e)

  if len(stack):
    res.extend(stack)
  return res, len(stack) > 0

def GetSquads(run=None):
  conditions = (Team.table.c.present == 1)
  if run:
    conditions = conditions & (Team.table.c.size==run.size)
  res = session.execute(select([distinct(Team.table.c.squad)], conditions)).fetchall()
  squads = [item for sublist in res for item in sublist]
  for s in squads[:]:
    if not s:
      squads.remove(s)
  return squads

def GetStartList(run, includeRemoved=False):
  if run:
    if not run.sort_run_id:
      sq = aliased(Result, Result.query.filter_by(run=run).subquery())
      sort = aliased(Sort, Sort.query.filter_by(run=run).subquery())
      query = Team.query.filter_by(size=run.size).filter_by(present=1)
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

      if includeRemoved:
        #put removed teams at the end
        order.insert(0, func.ifnull(sort.value, 0) == 3)
      else:
        #or don't get them at all
        query = query.filter(func.ifnull(sort.value, 1) != 3)

      query = query.add_entity(sq).add_entity(sort).outerjoin(sq).outerjoin(sort).order_by(*order)
      query = query.all()
    else:
      if run.squads:
        query = []
        squad_results = GetSquadResults(Run.get_by(id=run.sort_run_id))
        for r in squad_results:
          for m in r['members']:
            query.append((Team.get_by(id=m['team_id']), Result.get_by(team_id=m['team_id'], run_id=run.id), Sort.get_by(team_id=m['team_id'], run_id=run.id)))

      else:
        query, aliases = ResultQuery(Run.get_by(id=run.sort_run_id), resultsFrom=run)
        query = query.all()

      query.reverse()

    result = []
    new_entries = False
    for t in query:
      team = t[0]
      if t[1]:
        res = t[1]
      else:
        res = Result(team=team, run=run)
        new_entries = True
      if t[2]:
        sort = t[2]
      else:
        sort = Sort(team=team, run=run)
        new_entries = True
      setattr(team, 'result', res)
      setattr(team, 'sort', sort)
      result.append(team)

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

    order = 0
    for t in result:
      order += 1
      setattr(t, 'order', order)

    if new_entries:
      session.commit()

    return result
  else:
    return []


def GetRunTimes(run):
  if run.time_calc:
    query, aliases = ResultQuery(run, 999, 999)
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


def GetSquadSums(runs):
  if runs:
    run_results = []
    for r in runs:
      res = GetSquadResults(r, keyed=True)
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


def GetSquadResults(run, keyed=False):
  squads = []
  squad_list = GetSquads(run)
  time, max_time = GetRunTimes(run)
  if None in squad_list:
    squad_list.remove(None)

  for s in squad_list:
    query, aliases = ResultQuery(run, includeAbsent=True)

    query = query.filter(func.ifnull(aliases['team'].c.squad, "") == s)
    rows = session.execute(query).fetchall()

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

    if keyed:
      squads.append((squad['name'], squad))
    else:
      squads.append(squad)

  if keyed:
    return dict(squads)
  else:
    squads.sort(key=lambda s: (s['disq']* s['disq_count'], s['total_penalty'], s['penalty'], s['result_time']))

    rank = 0
    for s in squads:
      rank += 1
      s['rank'] = rank

    return squads


def ResultQuery(run, max_time=None, time=None, includeAbsent=False, resultsFrom=None):
  if max_time == None and time == None:
    time, max_time = GetRunTimes(run)

  r = session.query()
  team = alias(select([Team.table], Team.table.c.present==1), alias="team")
  sort = alias(select([Sort.table], Sort.table.c.run_id==run.id), alias="sort")
  res = alias(select([Result.table], Result.table.c.run_id==run.id), alias="result")
  r = r.add_entity(Team, alias=team)
  if resultsFrom:
    res_from = alias(select([Result.table], Result.table.c.run_id==resultsFrom.id), alias="result_from")
    r = r.add_entity(Result, alias=res_from)
    r = r.add_entity(Sort, alias=sort)
    r = r.add_entity(Result, alias=res)
    r = r.outerjoin(res).outerjoin(sort).outerjoin(res_from)
  else:
    r = r.add_entity(Result, alias=res)
    r = r.add_entity(Sort, alias=sort)
    r = r.outerjoin(res).outerjoin(sort)
  r = r.add_columns((team.c.handler_name + ' ' + team.c.handler_surname).label("team_handler"))
  r = r.add_columns((team.c.dog_name + ' ' + team.c.dog_kennel).label("team_dog"))
  r = r.add_columns((res.c.mistakes*5 + res.c.refusals*5).label("penalty"))
  r = r.add_columns(((res.c.time - time)*(res.c.time > time)).label("time_penalty"))
  r = r.add_columns(((res.c.time - time)*(res.c.time > time) + res.c.mistakes*5 + res.c.refusals*5).label("total_penalty"))
  r = r.add_columns(func.ifnull(run.length/res.c.time, 0).label('speed'))


  disq = (res.c.time > max_time) | (res.c.disqualified) | (res.c.refusals >= 3)
  if includeAbsent:
    disq = disq | (res.c.time == 0)
  r = r.add_columns(disq.label("disq"))

  r = r.filter((func.ifnull(sort.c.value, 1) != 3) & ((res.c.time > 0) | 'disq'))
  r = r.order_by("disq, total_penalty, penalty, result_time")

  return r, {'team': team, 'result': res, 'sort': sort}

def GetResults(run):

  query, aliases = ResultQuery(run)
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
    if not r['disq'] and r['penalty'] < 26:
      if r['penalty'] < 16:
        if r['penalty'] < 6:
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

def GetSums(runs):
  if runs:
    team = alias(select([Team.table], Team.table.c.present==1), alias="team")
    r = session.query()
    r = r.add_entity(Team, alias=team)
    pen = []
    time_pen = []
    time = []
    sorts = []
    disq = []
    ran = []
    lengths = 0

    for run in runs:
      run_time, run_max_time = GetRunTimes(run)
      res = alias(select([Result.table], Result.table.c.run_id==run.id))
      sort = alias(select([Sort.table], Sort.table.c.run_id==run.id))
      pen.append(res.c.mistakes*5 + res.c.refusals*5)
      time_pen.append((res.c.time - run_time)*(res.c.time > run_time))
      time.append(res.c.time)
      sorts.append(func.ifnull(sort.c.value, 0))
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

    r = r.filter("sort < 3 AND ran_all == %d" % len(runs))
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
