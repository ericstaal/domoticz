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

"""
<plugin key="DenonMarantz" name="Denon / Marantz AVR Amplifier" author="dnpwwo/artemgy/elgringo" version="2.6.2" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
    <param field="Port" label="Port" width="30px" required="true" default="23"/>
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
import html

# additional imports
import datetime

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 5  # lose conenction after
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

  SourceOptions = {}
  
  def checkConnection(self, checkonly = False):
    # Check connection and connect none
    isConnected = False
    
    if not self.connection is None:
      if self.connection.Connected():
        isConnected = True
      else:
        if (not self.connection.Connecting()) and (not checkonly):
          self.outstandingMessages = 0
          self.connection.Connect()
    
    return isConnected
    
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.LogError("Debuglevel '"+Parameters["Mode6"]+"' is not an integer")
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    self.LogMessage("onStart called", 9)
    
    self.connection = Domoticz.Connection(Name="Telnet", Transport="TCP/IP", Protocol="Line", Address=Parameters["Address"], Port=Parameters["Port"])
    
    dictValue=0
    for item in Parameters["Mode3"].split('|'):
      self.selectorMap[dictValue] = item
      dictValue = dictValue + 10
        
    if (Parameters["Mode3"].count('|') != Parameters["Mode4"].count('|')):
      self.LogError("Sources ("+Parameters["Mode3"]+") and names ("+Parameters["Mode4"]+") do not match! Using only sources")
      
      self.SourceOptions = {'LevelActions': '|'*Parameters["Mode3"].count('|'),
               'LevelNames': Parameters["Mode3"],
               'LevelOffHidden': 'false',
               'SelectorStyle': '0'} # 1 = combobox, 0 = buttons
    else:
      self.SourceOptions = {'LevelActions': '|'*Parameters["Mode4"].count('|'),
               'LevelNames': Parameters["Mode4"],
               'LevelOffHidden': 'false',
               'SelectorStyle': '0'}
      
    #ICONS
    if ("DenonMarantzIncrease" not in Images): Domoticz.Image('DenonMarantzIncrease.zip').Create()
    if ("DenonMarantzDecrease" not in Images): Domoticz.Image('DenonMarantzDecrease.zip').Create()
    if ("DenonMarantzboombox" not in Images): Domoticz.Image('DenonMarantzboombox.zip').Create()
    
    if (2 not in Devices): 
      Domoticz.Device(Name="Source",     Unit=2, TypeName="Selector Switch", Switchtype=18, Image=5, Options=self.SourceOptions).Create()
      if (len(Devices[2].sValue) > 0):
        self.mainSource = int(Devices[2].sValue)
        self.mainOn = (Devices[2].nValue != 0)
    elif (Devices[2].Options != self.SourceOptions):
      self.LogMessage("Sources or names have changed.", Level = 2)
      
      # update does not work, so delte it and readd it.
      Devices[2].Delete()
      Domoticz.Device(Name="Source",     Unit=2, TypeName="Selector Switch", Switchtype=18, Image=5, Used=1, Options=self.SourceOptions).Create()
      
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
    self.LogMessage("onStop called", 9)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.LogMessage("Connected successfully to: "+Connection.Address+":"+Connection.Port, 2)
      self.connection.Send('ZM?\r')
      
    else:
      self.LogMessage("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 2)
      self.SyncDevices()

    return

  def onMessage(self, Connection, Data):
    
    if (self.outstandingMessages >= 1):
      self.outstandingMessages = self.outstandingMessages - 1
      
    strData = Data.decode("utf-8", "ignore")
        
    strData = strData.strip()
    self.LogMessage("onMessage called: "+strData , 9)
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
        self.LogMessage("Unknown message '"+action+"' ignored.", 8)
    self.SyncDevices()

    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.LogMessage("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 8)
    
    Command = Command.strip()
    action, sep, params = Command.partition(' ')
    action = action.capitalize()
    params = params.capitalize()
    delay = 0
    
    lastHeartbeatDelta = (datetime.datetime.now()-self.lastHeartbeat).total_seconds()
    if (lastHeartbeatDelta < 0.5):
      delay = 1
      self.LogMessage("Last heartbeat was "+str(lastHeartbeatDelta)+" seconds ago, delaying command send.", 4)

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
    self.LogMessage("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8)
    
    return

  def onDisconnect(self, Connection):
    self.LogMessage("onDisconnect "+Connection.Address+":"+Connection.Port, 7)

    return

  def onHeartbeat(self):
    self.LogMessage("onHeartbeat called, open messages: " + str(self.outstandingMessages), 9)
    if self.checkConnection(): # if false will initialize a new connection
      if (self.outstandingMessages > self.maxOutstandingMessages):
        self.connection.Disconnect()
      else:
        # send message
        self.lastHeartbeat = datetime.datetime.now()
        self.connection.Send(self.pollingDict[self.lastMessage])
        self.LogMessage("onHeartbeat: lastMessage "+self.lastMessage+", Sending '"+self.pollingDict[self.lastMessage][0:2]+"' Open messages: "+str(self.maxOutstandingMessages)+". ", 8)
        
        self.outstandingMessages = self.outstandingMessages + 1
      
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
        self.LogMessage("Update ["+Devices[Unit].Name+"] from: ('"+str(Devices[Unit].nValue)+":'"+str(Devices[Unit].sValue )+"') to: ("+str(nValue)+":'"+str(sValue)+"')", 5)
        Devices[Unit].Update(nValue, sValue)
    return
   
  def DumpDeviceToLog(self,Unit):
    self.LogMessage(str(Devices[Unit].ID)+":"+Devices[Unit].Name+", (n:"+str(Devices[Unit].nValue)+", s:"+Devices[Unit].sValue+", Sgl:"+str(Devices[Unit].SignalLevel)+", bl:"+str(Devices[Unit].BatteryLevel)+", img:"+ str(Devices[Unit].Image)+", typ:"+ str(Devices[Unit].Type)+", styp:"+ str(Devices[Unit].SubType)+")", 6)
    return   
    
  def DumpConfigToLog(self):
    for x in Parameters:
      if Parameters[x] != "":
        self.LogMessage( "'" + x + "':'" + str(Parameters[x]) + "'", 7)
    self.LogMessage("Device count: " + str(len(Devices)), 6)
    for x in Devices:
      self.DumpDeviceToLog(x)
    return
    
  def DumpVariable(self, Item, Varname, Level = 5, BytesAsStr = False, Prefix=""):
    if self.logLevel >= Level:
      Prefix = str(Prefix)
      if isinstance(Item, dict):
        self.LogMessage(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): ", Level)
        
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
          txt = html.escape(Item.decode("utf-8", "ignore"))
        else:
          txt = "[ " 
          for b in Item:
            txt += str(hex(b))+" "
          txt +=  "]"
        
        self.LogMessage(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): " + txt, Level)
      elif isinstance(Item, (tuple, list)):
        self.LogMessage(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): ", Level)
        
        if len(Prefix) < 3:
          Prefix = "--> "
        else:
          Prefix = "--" + Prefix
          
        idx = 0
        for b in Item:
          self.DumpVariable( b, "["+str(idx) + "]", Level, BytesAsStr, Prefix)
          idx=idx+1

      elif isinstance(Item, str):
        self.LogMessage(Prefix + str(Varname) + " ("+type(Item).__name__+"["+str(len(Item))+"]): '"+Item+"'", Level)
      else:
        self.LogMessage(Prefix + str(Varname) + " ("+type(Item).__name__+"): "+str(Item), Level)
           
    return

  def LogMessage(self, Message, Level):
    if Level > 0:
      if self.logLevel >= Level:
        if self.logLevel >= 10:
          Domoticz.Debug(Message)
        else:
          Domoticz.Log(Message)
    elif (Level < 0) or (Level > 10):
      Domoticz.Error(Message)
      
    return
    
  def LogError(self, Message):
    self.LogMessage(Message, -1)
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

