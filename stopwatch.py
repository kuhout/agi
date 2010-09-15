import serial
import threading

class StopwatchThread(threading.Thread):
  def Test(self):
    ser = serial.Serial('/dev/ttyUSB0');
    ser.read(1)

  def GetTime(self):
    return self.time

  def GetText(self):
    return self.text

  def Get(self, what):
    return getattr(self, what)

class SimpleStopwatchThread(StopwatchThread):
  def run(self):
    self.time = 0
    self.text = "0:00:00"
    ser = serial.Serial('/dev/ttyUSB0');
    num = ""
    while True:
      x = ser.read()
      o = ord(x)
      if o == 255:
        if len(num) == 5:
          self.time = int(num[0])*60 + int(num[1:3]) + float(num[3:5])/100
          self.text = "%s:%s:%s" % (num[0], num[1:3], num[3:5])
        num = ""
      elif o >= 48 and o <=57:
        num = x + num

  def GetCapabilities(self):
    return ['time']

class AdvancedStopwatchThread(StopwatchThread):
  def run(self):
    ser = serial.Serial('/dev/ttyUSB0');
    self.text = num = "0:00:00"
    self.time = self.mistakes = self.refusals = 0
    temp = ""
    while True:
      while temp[-3:] != "RW:":
        temp += ser.read(1)
      temp = ""
      while len(temp) <= 37:
        temp += ser.read(1)
      h = reduce(lambda a,d: 256*a+d, map(ord, reversed(temp[4:7])), 0)
      m = h / 60000
      s = (h % 60000) / 1000
      ms = (h % 60000 % 1000) / 10
      mis = ord(temp[8])
      ref = ord(temp[12])
      self.time = float(m*60 + s % 60) + float(ms) / 100
      self.mistakes = mis
      self.refusals = ref
      self.text = "ch:%d o:%d %02d:%02d:%02d" % (mis, ref, m, s % 60, ms)

  def GetCapabilities(self):
    return ['time', 'mistakes', 'refusals']
