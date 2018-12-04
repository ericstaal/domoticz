# Marantz pluging
#
# Description: 
#   Mode3 ("Sources") needs to have '|' delimited names of sources that the Denon knows about.  
#   The Selector can be changed afterwards to any text and the plugin will still map to the actual Denon name.
#
#   Adjust for marantz sr5009: removed power (controlled via zone), added tuner preset +/- buttons with stationname
#
# Author: Dnpwwo, 2016 - 2017, Artemgy 2017, elgringo 2017
#
# History:
# 1.0.0   01-07-2017  Initial version
# 2.6.0   31-07-2017  Updated with new API
# 2.6.1   06-08-2017  Added own surce names
# 2.6.2   07-08-2017  Selector switch to buttons
# 2.6.3   07-04-2018  Report connect error only once
# 2.6.4   22-05-2018  Onheartbeat debug level to 8
# 2.6.5   20-06-2018  Solved issue with max open messages
# 2.6.6   26-06-2018  Added logging checkconnection, destroy connection when was connected
# 2.6.7   16-07-2018  Heartbeat configurable
# 2.6.8   06-08-2018  Update logging

"""
<plugin key="DenonMarantz" name="Denon / Marantz AVR Amplifier" author="dnpwwo/artemgy/elgringo" version="2.6.8" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
    <param field="Port" label="Port" width="30px" required="true" default="23"/>
      <param field="Mode1" label="Heartbeat interval" width="50px" required="true">
      <options>
        <option label="1" value="1"/>
        <option label="2" value="2"/>
        <option label="5" value="5"/>
        <option label="8" value="8"/>
        <option label="10" value="10" default="true"/>
        <option label="15" value="15" />
        <option label="20" value="20"/>
        <option label="30" value="30"/>
      </options>
    </param>
    <param field="Mode2" label="Startup Delay" width="50px" required="true">
      <options>
        <option label="2" value="2"/>
        <option label="3" value="3"/>
        <option label="4" value="4" default="true" />
        <option label="5" value="5"/>
        <option label="6" value="6"/>
        <option label="7" value="7"/>
        <option label="10" value="10"/>
      </options>
    </param>
    <param field="Mode3" label="Sources" width="550px" required="true" default="Off|DVD|VDP|TV|CD|DBS|Tuner|Phono|VCR-1|VCR-2|V.Aux|CDR/Tape|AuxNet|AuxIPod"/>
    <param field="Mode4" label="Sources name" width="550px" required="true" default="Off|DVD|VDP|TV|CD|DBS|Tuner|Phono|VCR-1|VCR-2|V.Aux|CDR/Tape|AuxNet|AuxIPod"/>
    <param field="Mode5" label="Disconnect after (tries)"width="50px"  required="true">
      <options>
        <option label="0" value="0" default="true"/>
        <option label="1" value="1"/>
        <option label="2" value="2"/>
        <option label="3" value="3"/>
      </options>
    </param>
    <param field="Mode6" label="Debug level" width="150px">
      <options>
        <option label="0 (No logging)" value="0" default="true"/>
        <option label="1" value="1"/> 
        <option label="2" value="2"/>
        <option label="3" value="3"/>
        <option label="4" value="4"/>
        <option label="5" value="5"/>
        <option label="6" value="6"/>
        <option label="7" value="7"/>
        <option label="8" value="8"/>
        <option label="9 (all)" value="9"/>
        <option label="10 (all with debug)" value="10"/>
      </options>
    </param>
  </params>
</plugin>
"""

import Domoticz
import collections 
import base64
import binascii
from html import escape

# additional imports
import datetime

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 0  # lose connection after
  logLevel = 0                # logLevel
  
  mainOn = False
  mainSource = 0
  mainVolume1 = 0
  stationName = ""
  
  ignoreMessages = "|SS|SV|SD|MS|PS|CV|SY|TP|"
  selectorMap = {}
  pollingDict =  {"ZM":"SI?\r", "SI":"MV?\r", "MV":"MU?\r", "MU":"ZM?\r" }
  lastMessage = "ZM"
  lastHeartbeat = datetime.datetime.now()
  
  errorReported = False
  wasConnected = False # check if was connected if so cdestroy the connection
  
  def checkConnection(self, checkonly = False):
    # Check connection and connect none
    isConnected = False
    
    try:
      if self.connection is None:
        self.connection = Domoticz.Connection(Name="Telnet", Transport="TCP/IP", Protocol="Line", Address=Parameters["Address"], Port=Parameters["Port"])
        self.connection.Connect()
        self.Log("checkConnection: Connection created, trying to connect", 6, 2)
      else:
        if self.connection.Connected():
          isConnected = True
        else:
          if self.wasConnected:
            self.wasConnected = False
            self.connection = None
            self.Log("checkConnection: Connection destroyed", 6, 2)
          else:
            if (not self.connection.Connecting()) and (not checkonly):
              self.outstandingMessages = 0
              self.connection.Connect()
              self.Log("checkConnection: Trying to connect", 6, 2)
      
    except:
      isConnected = False
      self.connection = None
      self.wasConnected = False
      self.Log("checkConnection: Error, try to reset",1,3)

    return isConnected
    
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.Log("Debuglevel '"+Parameters["Mode6"]+"' is not an integer", 1, 3)
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    self.Log("onStart called, heartbeat interval " +str(Parameters["Mode1"])+" seconds", 4, 1)
    
    Domoticz.Heartbeat(int(Parameters["Mode1"])) 
    
    try:
      self.maxOutstandingMessages = int(Parameters["Mode5"])
    except:
      self.Log("max open messages '"+Parameters["Mode5"]+"' is not an integer", 1, 3)
      
    dictValue=0
    for item in Parameters["Mode3"].split('|'):
      self.selectorMap[dictValue] = item
      dictValue = dictValue + 10
        
    if (Parameters["Mode3"].count('|') != Parameters["Mode4"].count('|')):
      self.Log("Sources ("+Parameters["Mode3"]+") and names ("+Parameters["Mode4"]+") do not match! Using only sources", 1, 3)
      
      sourceOptions = {'LevelActions': '|'*Parameters["Mode3"].count('|'),
               'LevelNames': Parameters["Mode3"],
               'LevelOffHidden': 'false',
               'SelectorStyle': '0'} # 1 = combobox, 0 = buttons
    else:
      sourceOptions = {'LevelActions': '|'*Parameters["Mode4"].count('|'),
               'LevelNames': Parameters["Mode4"],
               'LevelOffHidden': 'false',
               'SelectorStyle': '0'}
      
    #ICONS
    if ("DenonMarantzIncrease" not in Images): Domoticz.Image('DenonMarantzIncrease.zip').Create()
    if ("DenonMarantzDecrease" not in Images): Domoticz.Image('DenonMarantzDecrease.zip').Create()
    if ("DenonMarantzboombox" not in Images): Domoticz.Image('DenonMarantzboombox.zip').Create()
    
    if (2 not in Devices): 
      Domoticz.Device(Name="Source", Unit=2, TypeName="Selector Switch", Switchtype=18, Image=5, Options=sourceOptions).Create()
      if (len(Devices[2].sValue) > 0):
        self.mainSource = int(Devices[2].sValue)
        self.mainOn = (Devices[2].nValue != 0)
    elif (Devices[2].Options != sourceOptions):
      self.Log("Sources or names have changed.", Level = 2, Type = 1)
      
      # update does not work, so delte it and readd it.
      Devices[2].Delete()
      Domoticz.Device(Name="Source",     Unit=2, TypeName="Selector Switch", Switchtype=18, Image=5, Used=1, Options=sourceOptions).Create()
      
    if (3 not in Devices): 
      Domoticz.Device(Name="Volume",     Unit=3, Type=244, Subtype=73, Switchtype=7, Image=8).Create()
      if (len(Devices[3].sValue) > 0):
        self.mainVolume1 = int(Devices[3].sValue) if (Devices[3].nValue != 0) else int(Devices[3].sValue)*-1
        
    if (4 not in Devices): 
      Domoticz.Device(Name="Tuner up",   Unit=4, TypeName="Switch", Image=Images["DenonMarantzIncrease"].ID).Create()
    
    if (5 not in Devices): 
      Domoticz.Device(Name="Tuner down", Unit=5, TypeName="Switch", Image=Images["DenonMarantzDecrease"].ID).Create()
    
    if (6 not in Devices): 
      Domoticz.Device(Name="Station",    Unit=6, Type=243, Subtype=19, Switchtype=0, Image=Images["DenonMarantzboombox"].ID).Create()
    
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.Log("onStop called", 9, 1)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port, 2, 2)
      if not self.wasConnected:
        self.wasConnected = True
      self.connection.Send('ZM?\r')
      if self.errorReported:
        self.errorReported = False
      
    else:
      if not self.errorReported:
        self.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 2, 2)
        self.SyncDevices()
        self.errorReported = True
	  
    return

  def onMessage(self, Connection, Data):
    
    if (self.outstandingMessages >= 1):
      self.outstandingMessages = self.outstandingMessages - 1
      
    strData = Data.decode("utf-8", "ignore")
        
    strData = strData.strip()
    self.Log("onMessage received: "+strData , 9, 1)
    action = strData[0:2]
    detail = strData[2:]
    if (action in self.pollingDict): self.lastMessage = action

    if (action == "ZM"):    # Main Zone on/off
      if (detail == "ON"):
        self.mainOn = True
      elif (detail == "OFF"):
        self.mainOn = False
      else: LogMessage("Unknown: Action "+action+", Detail '"+detail+"' ignored.", 7)
    elif (action == "SI"):    # Main Zone Source Input
      for key, value in self.selectorMap.items():
        if (detail == value):    
          self.mainSource = key
          #self.lastMessage = "MU" # force reloading channel name
    elif (action == "MV"):    # Master Volume
      if (detail.isdigit()):
        if (abs(self.mainVolume1) != int(detail[0:2])): self.mainVolume1 = int(detail[0:2])
      elif (detail[0:3] == "MAX"): Domoticz.Debug("Unknown: Action "+action+", Detail '"+detail+"' ignored.")
      else: LogMessage("Unknown: Action "+action+", Detail '"+detail+"' ignored.", 7)
    elif (action == "MU"):    # Overall Mute
      if (detail == "ON"):     self.mainVolume1 = abs(self.mainVolume1)*-1
      elif (detail == "OFF"):    self.mainVolume1 = abs(self.mainVolume1)
      else: LogMessage("Unknown: Action "+action+", Detail '"+detail+"' ignored.", 7)
    elif (action == "TF"):
      self.stationName = detail[6:].strip()
      
    else:
      if (self.ignoreMessages.find(action) < 0):
        self.Log("Unknown message '"+action+"' ignored.", 8, 1)
    self.SyncDevices()

    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 8, 1)
    
    Command = Command.strip()
    action, sep, params = Command.partition(' ')
    action = action.capitalize()
    params = params.capitalize()
    delay = 0
    
    lastHeartbeatDelta = (datetime.datetime.now()-self.lastHeartbeat).total_seconds()
    if (lastHeartbeatDelta < 0.5):
      delay = 1
      self.Log("Last heartbeat was "+str(lastHeartbeatDelta)+" seconds ago, delaying command send.", 4, 1)

    # Main Zone devices
    if self.checkConnection(True):
      if (Unit == 2):   # Main selector
        if (action == "On"):
          self.connection.Send(Message='ZMON\r', Delay=delay)
        elif (action == "Set"):
          self.connection.Send(Message='SI'+self.selectorMap[Level]+'\r', Delay=delay)
        elif (action == "Off"):
          self.connection.Send(Message='ZMOFF\r', Delay=delay)
      elif (Unit == 3):   # Main Volume control
        if (action == "On"):
          self.connection.Send(Message='MUOFF\r', Delay=delay)
        elif (action == "Set"):
          self.connection.Send(Message='MV'+str(Level)+'\r', Delay=delay)
        elif (action == "Off"):
          self.connection.Send(Message='MUON\r', Delay=delay)
      elif (Unit == 4):   # Up
        self.connection.Send(Message='TPANUP\r', Delay=delay)
      elif (Unit == 5):   # Down
        self.connection.Send(Message='TPANDOWN\r', Delay=delay)
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.Log("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8, 1)
    
    return

  def onDisconnect(self, Connection):
    self.Log("onDisconnect "+Connection.Address+":"+Connection.Port, 7, 2)

    return

  def onHeartbeat(self):
    self.Log("onHeartbeat called, open messages: " + str(self.outstandingMessages), 8, 1)
    if self.checkConnection(): # if false will initialize a new connection
      if (self.outstandingMessages > self.maxOutstandingMessages):
        self.connection.Disconnect()
      else:
        # send message
        self.lastHeartbeat = datetime.datetime.now()
        self.outstandingMessages = self.outstandingMessages + 1
        self.Log("onHeartbeat: lastMessage "+self.lastMessage+", Sending '"+self.pollingDict[self.lastMessage][0:2]+"'. ", 8, 1)
        self.connection.Send(self.pollingDict[self.lastMessage])   
        
      
    return

####################### Specific helper functions for plugin #######################    
  def SyncDevices(self):
    self.UpdateDevice(2, self.mainSource if self.mainOn else 0, str(self.mainSource if self.mainOn else 0))
    if (self.mainVolume1 <= 0 or self.mainOn == False): self.UpdateDevice(3, 0, str(abs(self.mainVolume1)))
    else: self.UpdateDevice(3, 2, str(self.mainVolume1))
    
    if (len(self.stationName) == 0):
      self.UpdateDevice(6,0,"?")
    elif (not self.stationName.isdigit()):
      self.UpdateDevice(6,0,self.stationName)

    return  
    
####################### Generic helper member functions for plugin ####################### 
  def StringToMinutes(self, value):
    # hh:mm
    splitted = value.split(":")
    if len(splitted) >= 2:
      minutes = int(splitted[len(splitted)-1]) + int(splitted[len(splitted)-2])*60
    else:
      minutes = int(splitted[0])
    return minutes  
   
  def UpdateDevice(self, Unit, nValue, sValue1, sValue2 = None):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
      if sValue2 is None:
        sValue = str(sValue1)
      else:
        sValue = str(sValue1)+";"+str(sValue2)
        
      if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
        self.Log("Update ["+Devices[Unit].Name+"] from: ('"+str(Devices[Unit].nValue)+":'"+str(Devices[Unit].sValue )+"') to: ("+str(nValue)+":'"+str(sValue)+"')", 5, 1)
        Devices[Unit].Update(nValue, sValue)
    return
   
  def DumpDeviceToLog(self,Unit):
    self.Log(str(Devices[Unit].ID)+":"+Devices[Unit].Name+", (n:"+str(Devices[Unit].nValue)+", s:"+Devices[Unit].sValue+", Sgl:"+str(Devices[Unit].SignalLevel)+", bl:"+str(Devices[Unit].BatteryLevel)+", img:"+ str(Devices[Unit].Image)+", typ:"+ str(Devices[Unit].Type)+", styp:"+ str(Devices[Unit].SubType)+")", 6, 1)
    return   
    
  def DumpConfigToLog(self):
    for x in Parameters:
      if Parameters[x] != "":
        self.Log( "'" + x + "':'" + str(Parameters[x]) + "'", 7, 1)
    self.Log("Device count: " + str(len(Devices)), 6, 1)
    for x in Devices:
      self.DumpDeviceToLog(x)
    return
    
  def DumpVariable(self, Item, Varname, Level = 5, BytesAsStr = False, Prefix=""):
    if self.logLevel >= Level:
      Prefix = str(Prefix)
      if isinstance(Item, dict):
        self.Log(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): ", Level, 1)
        
        if len(Prefix) < 3:
          Prefix = "--> "
        else:
          Prefix = "--" + Prefix
          
        for b in Item:
          if isinstance(b, str):
            self.DumpVariable( Item[b], "'"+str(b) + "'", Level, BytesAsStr, Prefix)
          else:
            self.DumpVariable( Item[b], str(b), Level, BytesAsStr, Prefix)
         
      elif isinstance(Item, (bytes, bytearray)):
        if BytesAsStr:
          txt = escape(Item.decode("utf-8", "ignore"))
        else:
          txt = "[ " 
          for b in Item:
            txt += '0x{:02X} '.format(b)
          txt +=  "]"
        
        self.Log(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): " + txt, Level, 1)
      elif isinstance(Item, (tuple, list)):
        self.Log(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): ", Level, 1)
        
        if len(Prefix) < 3:
          Prefix = "--> "
        else:
          Prefix = "--" + Prefix
          
        idx = 0
        for b in Item:
          self.DumpVariable( b, "["+str(idx) + "]", Level, BytesAsStr, Prefix)
          idx=idx+1

      elif isinstance(Item, str):
        self.Log(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): '"+Item+"'", Level, 1)
      else:
        self.Log(Prefix + str(Varname) + " ("+type(Item).__name__+"): "+str(Item), Level, 1)
           
    return

  def Log(self, Message, Level, Type):
    # Message = string, Level [0-10], Type [1=Normal, 2=Status, 3=Error]
    if self.logLevel >= Level:
      if Type == 2:
        Domoticz.Status(Message)
      elif Type == 3:
        Domoticz.Error(Message)
      else:
        Domoticz.Log(Message)
    
    return
    
  def stringToBase64(self, s):
    return base64.b64encode(s.encode('utf-8')).decode("utf-8")

  def base64ToString(self, b):
    return base64.b64decode(b).decode('utf-8')  
    
####################### Global functions for plugin #######################
global _plugin
_plugin = BasePlugin()

def onStart():
  global _plugin
  _plugin.onStart()

def onStop():
  global _plugin
  _plugin.onStop()

def onConnect(Connection, Status, Description):
  global _plugin
  _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
  global _plugin
  _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
  global _plugin
  _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
  global _plugin
  _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
  global _plugin
  _plugin.onDisconnect(Connection)

def onHeartbeat():
  global _plugin
  _plugin.onHeartbeat()

