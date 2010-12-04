import wx
# coding: utf-8

import db
import locale
from network import Client
from time import strftime
from Formatter import *
from reportlab.platypus import Spacer, SimpleDocTemplate, Table, TableStyle, BaseDocTemplate, PageTemplate, Frame, PageBreak
from reportlab.platypus.paragraph import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors, pagesizes
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import subprocess



pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans-BoldOblique', 'DejaVuSans-BoldOblique.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans-Oblique', 'DejaVuSans-Oblique.ttf'))
pdfmetrics.registerFontFamily('DejaVuSans',normal='DejaVuSans',bold='DejaVuSans-Bold',italic='DejaVuSans-Oblique',boldItalic='DejaVuSans-BoldOblique')

normalStyle = ParagraphStyle(name='Normal', fontSize=8, fontName='DejaVuSans')
boldStyle = ParagraphStyle(name='Bold', fontSize=10, fontName='DejaVuSans-Bold')
normalCenterStyle = ParagraphStyle(name='NormalCenter', fontSize=10, fontName='DejaVuSans', alignment=1)
headingStyle = ParagraphStyle(name='Heading', fontSize=19, fontName='DejaVuSans-Bold', alignment=1, leading=22, spaceAfter=6)
subHeadingStyle = ParagraphStyle(name='Subheading', fontSize=16, fontName='DejaVuSans-Bold', alignment=1, leading=22, spaceAfter=6)
certNormalStyle = ParagraphStyle(name='certNormal', fontSize=22, fontName='DejaVuSans', alignment = 1)
certSmallStyle = ParagraphStyle(name='certSmall', fontSize=14, fontName='DejaVuSans', alignment = 1)
certLargeStyle = ParagraphStyle(name='certLarge', fontSize=42, fontName='DejaVuSans', alignment = 1)


def GetTeamsTable(teams):
  style = TableStyle([
    ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ('FONT', (0,0), (-1,-1), "DejaVuSans"),
    ('FONTSIZE', (0,1), (-1,-1), 8),
    ('FONT', (0,0), (-1, 0), "DejaVuSans-Bold"),
    ('ALIGN', (0,0), (-1,0), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ])

  table = []

  headers = ["Přít", "Číslo", "Jméno", "Příjmení", "Pes", "Chovná stanice", "Plemeno", "Kat", "Vel", "Průkaz"]
  widths = [1.2*cm, 1.4*cm, 2.6*cm, 4*cm, 4*cm, 5*cm, 4*cm, 1.2*cm, 1.2*cm, 2*cm]
  table.append(headers)

  for r in teams:
    row = []
    if r['present']:
      row.append(u"\u2713")
    else:
      row.append("")
    row.append(str(r['start_num']))
    row.append(r['handler_name'])
    row.append(r['handler_surname'])
    row.append(r['dog_name'])
    row.append(r['dog_kennel'])
    row.append(r['dog_breed'])
    row.append(GetFormatter("category").format(r['category']))
    row.append(GetFormatter("size").format(r['size']))
    row.append(r['number'])

    row = map(lambda x: Paragraph(x, normalStyle), row)
    table.append(row)

  return Table(table, style=style, colWidths=widths, repeatRows=1)

def PrintTeams(data):
  lst = []
  teams = GetTeamsTable(data)
  lst.append(Paragraph(u"Seznam účastníků", headingStyle))
  lst.append(teams)

  Print(lst)

def GetEntryTable(entry, run):
  table = []

  headers = ["Pořadí", "Číslo", "Psovod", "Pes", "Přezdívka", "Chyby", "Odmítnutí", "Čas"]
  if run['squads']:
    headers.insert(2, "Družstvo")
  table.append(headers)

  for r in entry:
    row = []
    row.append(r['order'])
    row.append(r['start_num'])
    if run['squads']:
      row.append(r['squad'])
    row.append(r['handler_name'] + ' ' + r['handler_surname'])
    row.append(r['dog_name'] + ' ' + r['dog_kennel'])
    row.append(r['dog_nick'])
    row.append("")
    row.append("")
    row.append("")

    table.append(row)

  return table

def PrintEntry(data, run):
  lst = []
  entry = GetEntryTable(data, run)
  style = TableStyle([
    ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ('FONT', (0,0), (-1,-1), "DejaVuSans"),
    ('FONTSIZE', (0,1), (-1,-1), 8),
    ('FONT', (0,0), (-1, 0), "DejaVuSans-Bold"),
    ('ALIGN', (0,0), (0,-1), 'CENTER'),
    ('ALIGN', (-3,0), (-1,-1), 'CENTER'),
    ('RIGHTPADDING', (-3,1), (-1, -1), 2*cm),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ])

  lst.append(Paragraph(u"Zápis výsledků", headingStyle))
  lst.append(Paragraph(run['nice_name'], subHeadingStyle))
  lst.append(Table(entry, style=style, repeatRows=1))

  Print(lst)

def GetStartTable(start, run):
  table = []

  headers = ["Pořadí", "Číslo", "Psovod", "Pes", "Plemeno", "OSA"]
  if run['squads']:
    headers.insert(2, "Družstvo")
  if run['variant'] != 0:
    headers.append("Kategorie")
  table.append(headers)

  for r in start:
    row = []
    row.append(r['order'])
    row.append(r['start_num'])
    if run['squads']:
      row.append(r['squad'])
    row.append(r['handler_name'] + ' ' + r['handler_surname'])
    row.append(r['dog_name'] + ' ' + r['dog_kennel'])
    row.append(r['breed']['name'])
    row.append(r['osa'])
    if run['variant'] != 0:
      row.append(GetFormatter("category").format(r['category']))

    table.append(row)

  return table

def PrintStart(data, run):
  lst = []
  start = GetStartTable(data, run)
  style = TableStyle([
    ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ('FONT', (0,0), (-1,-1), "DejaVuSans"),
    ('FONTSIZE', (0,1), (-1,-1), 8),
    ('FONT', (0,0), (-1, 0), "DejaVuSans-Bold"),
    ('ALIGN', (0,0), (-1,0), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ])

  lst.append(Paragraph(u"Startovní listina", headingStyle))
  lst.append(Paragraph(run['nice_name'], subHeadingStyle))
  lst.append(Table(start, style=style, repeatRows=1))

  Print(lst)

def GetSquadResultsTable(results):
  table = []

  headers = ["#", "Družstvo", "Tr. b.", "Čas", "Číslo", "Psovod", "Pes", "Plemeno", "Chb", "Odm", "Čas", "Tr. b.", "m/s"]
  widths = [1*cm, 3*cm, 1.65*cm, 1.4*cm, 1.4*cm, 5*cm, 4*cm, 4*cm, 1.4*cm, 1.4*cm, 1.4*cm, 1.65*cm, 1.2*cm]
  table.append(headers)

  style = [
    ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ('FONT', (0,0), (-1,-1), "DejaVuSans"),
    ('FONTSIZE', (0,1), (-1,-1), 8),
    ('FONT', (0,0), (-1, 0), "DejaVuSans-Bold"),
    ('ALIGN', (len(headers)-5,1), (len(headers)-1,-1), 'RIGHT'),
    ('ALIGN', (2,1), (4,-1), 'RIGHT'),
    ('ALIGN', (0,0), (-1,0), 'CENTER'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]

  lines = 1
  for r in results:
    first_line = True
    for m in r['members']:
      row = []

      if first_line:
        if r['disq']:
          rank = 'DIS'
        else:
          rank = r['rank']
        row.append(rank)
        row.append(r['name'])
        if r['disq']:
          for i in range(2):
            row.append("DIS")
        else:
          row.append(FloatFormatter().format(r['total_penalty']))
          row.append(FloatFormatter().format(r['result_time']))
        first_line = False
        for i in range(4):
          style.append(("SPAN", (i, lines), (i, lines-1+len(r['members']))))
        style.append(("LINEABOVE", (0, lines), (-1, lines), 1, colors.black))
        lines += len(r['members'])
      else:
        for i in range(4):
          row.append("")

      row.append(m['team_start_num'])
      row.append(Paragraph(m['team_handler'], normalStyle))
      row.append(Paragraph(m['team_dog'], normalStyle))
      row.append(Paragraph(m['breed_name'], normalStyle))
      if m['disq']:
        for i in range(5):
          row.append("DIS")
      else:
        row.append(m['result_mistakes'])
        row.append(m['result_refusals'])
        row.append(FloatFormatter().format(m['result_time']))
        row.append(FloatFormatter().format(m['total_penalty']))
        row.append(FloatFormatter().format(m['speed']))

      table.append(row)

  return Table(table, style=TableStyle(style), colWidths=widths, repeatRows=1)

def GetResultsTable(results, run):
  table = []

  headers = ["#", "Číslo", "Psovod", "Pes", "Plemeno", "OSA", "Chb", "Odm", "Čas", "Tr. b.", "m/s"]
  if run['variant'] == 0:
    headers.insert(5, "Kat")
    headers.insert(1, "Hod")
  table.append(headers)

  style = [
    ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ('FONT', (0,0), (-1,-1), "DejaVuSans"),
    ('FONTSIZE', (0,1), (-1,-1), 8),
    ('FONT', (0,0), (-1, 0), "DejaVuSans-Bold"),
    ('ALIGN', (0,0), (-1,0), 'CENTER'),
    ('ALIGN', (len(headers)-5,1), (len(headers)-1,-1), 'RIGHT'),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]


  for r in results:
    row = []
    if r['disq']:
      rank = 'DIS'
    else:
      rank = r['rank']
    row.append(rank)
    if run['variant'] == 0:
      row.append(r['rating'])
    row.append(r['team_start_num'])
    row.append(r['team_handler'])
    row.append(r['team_dog'])
    row.append(r['breed_name'])
    if run['variant'] == 0:
      row.append(GetFormatter("category").format(r['team_category']))
    row.append(r['team_osa'])
    if r['disq'] == 1:
      for i in range(5):
        row.append("DIS")
    else:
      row.append(r['result_mistakes'])
      row.append(r['result_refusals'])
      row.append(FloatFormatter().format(r['result_time']))
      row.append(FloatFormatter().format(r['total_penalty']))
      row.append(FloatFormatter().format(r['speed']))

    table.append(row)

  return Table(table, style=TableStyle(style), repeatRows=1)

def PrintResults(data, run):
  lst = []
  if run['squads']:
    results = GetSquadResultsTable(data)
  else:
    results = GetResultsTable(data, run)

  if run['time']:
    speed = run['length']/run['time']
  else:
    speed = 0
  runData = u"Rozhodčí: %s --- Počet překážek: %d --- Standardní čas: %.2f s --- Maximální čas: %.2f s --- Délka: %.2f m --- Rychlost: %.2f m/s" % (run['judge'], run['hurdles'], run['time'], run['max_time'], run['length'], speed)
  lst.append(Spacer(1, 0.5*cm))
  lst.append(Paragraph(u"Výsledky", headingStyle))
  lst.append(Paragraph(run['nice_name'], subHeadingStyle))
  lst.append(Spacer(1, 0.2*cm))
  lst.append(Paragraph(runData, normalCenterStyle))
  lst.append(Spacer(1, 0.2*cm))
  lst.append(results)

  Print(lst)

def PrintCerts(data, run_name, count):
  lst = []

  for i in range(0, min(count, len(data))):
    c = data[i]
    if c['disq']:
      break
    lst.append(Spacer(1, 17*cm))
    lst.append(Paragraph(c["team_handler"], certNormalStyle))
    lst.append(Spacer(1, 0.95*cm))
    lst.append(Paragraph(u"a", certSmallStyle))
    lst.append(Spacer(1, 0.55*cm))
    lst.append(Paragraph(c["team_dog"], certNormalStyle))
    lst.append(Spacer(1, 1.5*cm))
    lst.append(Paragraph(str(i+1) + u". místo", certLargeStyle))
    lst.append(Spacer(1, 2.5*cm))
    lst.append(Paragraph(run_name, certNormalStyle))
    lst.append(PageBreak())

  PrintPlain(lst)

def PrintSumsCerts(data, runs, count):
  run_name = ' + '.join([x['nice_name'] for x in runs])
  PrintCerts(data, run_name, count)

def GetSquadSumsTable(sums):
  style = [
    ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ('FONT', (0,0), (-1,-1), "DejaVuSans"),
    ('FONTSIZE', (0,1), (-1,-1), 8),
    ('FONT', (0,0), (-1, 0), "DejaVuSans-Bold"),
    ('ALIGN', (0,0), (-1,0), 'CENTER'),
    ('ALIGN', (2,1), (4,-1), 'RIGHT'),
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]

  table = []

  table.append(["#", "Družstvo", "Tr. b.", "Čas", "Číslo", "Psovod", "Pes", "Plemeno", "Kat"])
  widths = [1*cm, 3*cm, 1.65*cm, 1.4*cm, 1.4*cm, 5*cm, 4*cm, 4*cm, 1.4*cm]

  lines = 1
  for s in sums:
    first_line = True
    for m in s['members']:
      row = []

      if first_line:
        if s['disq']:
          rank = 'DIS'
        else:
          rank = s['rank']
        row.append(rank)
        row.append(s['name'])
        if s['disq']:
          for i in range(2):
            row.append("DIS")
        else:
          row.append(FloatFormatter().format(s['total_penalty']))
          row.append(FloatFormatter().format(s['result_time']))
        first_line = False
        for i in range(4):
          style.append(("SPAN", (i, lines), (i, lines-1+len(s['members']))))
        style.append(("LINEABOVE", (0, lines), (-1, lines), 1, colors.black))
        lines += len(s['members'])
      else:
        for i in range(4):
          row.append("")
      row.append(m['team_start_num'])
      row.append(Paragraph(m['team_handler'], normalStyle))
      row.append(Paragraph(m['team_dog'], normalStyle))
      row.append(Paragraph(m['breed_name'], normalStyle))
      row.append(GetFormatter("category").format(m['team_category']))

      table.append(row)

  return Table(table, style=TableStyle(style), colWidths=widths, repeatRows=1)

def GetSumsTable(sums):
  style = TableStyle([
    ('GRID', (0,0), (-1,-1), 0.25, colors.black),
    ('FONT', (0,0), (-1,-1), "DejaVuSans"),
    ('FONTSIZE', (0,1), (-1,-1), 8),
    ('FONT', (0,0), (-1, 0), "DejaVuSans-Bold"),
    ('ALIGN', (0,0), (-1,0), 'CENTER'),
    ('ALIGN', (6,0), (8,-1), 'RIGHT'),
    ])

  table = []

  table.append(["#", "Číslo", "Psovod", "Pes", "Plemeno", "OSA", "Kat", "Čas", "Tr. b.", "m/s"])

  for s in sums:
    row = []
    if s['disq']:
      rank = 'DIS'
    else:
      rank = s['rank']
    row.append(rank)
    row.append(s['team_id'])
    row.append(s['team_handler'])
    row.append(s['team_dog'])
    row.append(s['breed_name'])
    row.append(s['team_osa'])
    row.append(GetFormatter("category").format(s['team_category']))
    if s['disq']:
      for i in range(3):
        row.append("DIS")
    else:
      row.append(FloatFormatter().format(s['result_time']))
      row.append(FloatFormatter().format(s['total_penalty']))
      row.append(FloatFormatter().format(s['speed']))

    table.append(row)

  return Table(table, style=style, repeatRows=1)

def PrintSums(data, runs):
  lst = []
  if runs[0]['squads']:
    table = GetSquadSumsTable(data)
  else:
    table = GetSumsTable(data)

  lst.append(Paragraph(u"Součty", headingStyle))
  lst.append(Paragraph(' + '.join([x['nice_name'] for x in runs]), subHeadingStyle))
  lst.append(table)

  Print(lst)

class MyTemplate(PageTemplate):
  def __init__(self, params, pageSize=pagesizes.landscape(pagesizes.A4)):
      self.params = params
      self.pageWidth = pageSize[0]
      self.pageHeight = pageSize[1]
      frame1 = Frame(cm,
                     cm,
                     self.pageWidth - 2*cm,
                     self.pageHeight - 2.5*cm,
                     id='normal')
      PageTemplate.__init__(self, frames=[frame1])


  def afterDrawPage(self, canvas, doc):
    canvas.saveState()
    canvas.setFont("DejaVuSans", 8)
    canvas.drawString(cm, self.pageHeight - 1*cm, self.params['comp_name'])
    canvas.drawRightString(self.pageWidth - 1*cm, self.pageHeight - 1*cm, self.params['date'])
    canvas.restoreState()

class PlainTemplate(PageTemplate):
  def __init__(self, pageSize=pagesizes.A4):
      self.pageWidth = pageSize[0]
      self.pageHeight = pageSize[1]
      frame1 = Frame(0,
                     0,
                     self.pageWidth,
                     self.pageHeight,
                     id='normal')
      PageTemplate.__init__(self, frames=[frame1])


def PrintPlain(doc):
  c = BaseDocTemplate("output.pdf", pageTemplates=[PlainTemplate()], pagesize=pagesizes.A4)
  c.build(doc)
  p = subprocess.Popen(['lpr', '-o landscape', 'output.pdf'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  res = p.communicate()
  if p.poll() != 0:
    wx.MessageBox('\n'.join(list(res)), "Tisk")

def Print(doc):
  Client().Get(("param", "competition_name"), lambda r: _gotCompName(doc, r))

def _gotCompName(doc, comp_name):
  params = {'comp_name': comp_name['value'], 'date': strftime(locale.nl_langinfo(locale.D_FMT))}
  c = BaseDocTemplate("output.pdf", pageTemplates=[MyTemplate(params)], pagesize=pagesizes.landscape(pagesizes.A4), rightMargin=1*cm,leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)
  c.build(doc)
  p = subprocess.Popen(['lpr', '-o landscape', 'output.pdf'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  res = p.communicate()
  if p.poll() != 0:
    wx.MessageBox('\n'.join(list(res)), "Tisk")
