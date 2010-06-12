from elixir import *


class Book(Entity):
  number = Field(Unicode(6), default=u"")
  handler_name = Field(Unicode(50), default=u"")
  handler_surname = Field(Unicode(50), default=u"")
  dog_name = Field(Unicode(50), default=u"")
  dog_kennel = Field(Unicode(50), default=u"")
  dog_breed = Field(Unicode(50), default=u"")
  category = Field(Unicode(2), default=u"")
  size = Field(Unicode(1), default=u"")
  present = Field(Boolean, default=False)
  paid = Field(Unicode(50), default=u"")
  results = OneToMany('Result')
  sorts = OneToMany('Sort')

  def handlerFullName(self):
    return self.handler_name + ' ' + self.handler_surname

  def dogFullName(self):
    return (self.dog_name + ' ' + self.dog_kennel).strip()

  def IsBlank(self):
    d = self.to_dict()
    del d["id"]
    for val in d.itervalues():
      if val:
        return False
    return True


class Result(Entity):
  time = Field(Float)
  faults = Field(Integer)
  mistakes = Field(Integer)
  disqualified = Field(Boolean)
  run = ManyToOne('Run')
  book = ManyToOne('Book')


class Run(Entity):
  name = Field(Unicode(50), default=u"")
  size = Field(Unicode(1), default=u"")
  category = Field(Unicode(2), default=u"")
  variant = Field(Integer)
  length = Field(Float)
  time = Field(Float)
  max_time = Field(Float)
  judge = Field(Unicode(50), default=u"")
  hurdles = Field(Integer)
  results = OneToMany('Result')
  sorts = OneToMany('Sort')


class Sort(Entity):
  book = ManyToOne('Book')
  run = ManyToOne('Run')
  value = Field(Integer)


metadata.bind = "sqlite:///test.sqlite"
metadata.bind.echo = True
setup_all()
session.configure(autocommit=False, autoflush=True)


def GetStartList(runId):
  return session.execute("select books.dog_name + ' ' + books.dog_kennel as dog, '1' as handler, 1 as order from books left join sorts on books.id = sorts.book_id")

def GetBooks():
  return Book.query.all()
