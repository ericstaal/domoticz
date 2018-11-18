# HYPERION
#
# Description: To control a Hyperion (ambilight for raspberry) via the JSON server
# Author: elgringo
#
# History:
# 1.0.0   05-08-2017  Initial version
# 1.0.1   06-08-2017  Make priority channel configurable
# 1.0.2   22-05-2018  Remove urllib dependancies
# 1.0.3   20-06-2018  Solved issue with max open messages
# 1.0.4   06-08-2018  Update logging
# 1.1.0   18-11-2018  Changed to RGB colorpicker, updated icon

"""
<plugin key="Hyperion" name="Hyperion" author="elgringo" version="1.0.4" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="192.168.13.9"/>
    <param field="Port" label="Port" width="40px" required="true" default="19444"/>
    <param field="Mode1" label="Priority channel" width="200px" default="1" />
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
import json

from datetime import datetime, timedelta
import time


class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 0  # lose connection after
  logLevel = 0                # logLevel
  
  readata = bytearray()       # history
  SourceOptions = {}
  selectorMap = {}
  effectFileMap = {}
  
  priority = 1                # priority channel
  currentColor = [0,0,0]      # RGB
  
  dimmerValues = [0,0,0]      # values of sliders
  masterLevel = 0 
  errorReported = False

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
      self.Log("Debuglevel '"+Parameters["Mode6"]+"' is not an integer",1,3)
      
    try:
      self.maxOutstandingMessages = int(Parameters["Mode5"])
    except:
      self.Log("max open messages '"+Parameters["Mode5"]+"' is not an integer",1,3)
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    else:
      Domoticz.Heartbeat(20)
     
    try:
      self.priority = int(Parameters["Mode1"])
      if self.priority<0:
        self.Log("Priority is smaller than 0 ("+Parameters["Mode1"]+") this is not allowed, using 1 as priority",1,3)
        self.priority = 1
    except:
      self.Log("Priority '"+Parameters["Mode1"]+"' is not an integer, using 1 as priority",1,3)
      
    self.Log("onStart called", 9, 1)
    self.connection = Domoticz.Connection(Name="Hyperion", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
      
    # ICONS
    if ("HyperionMode" not in Images): Domoticz.Image('HyperionMode.zip').Create()

    if (1 not in Devices):
      Domoticz.Device(Name="RGB Light", Unit=1, Type=241, Subtype=2,  Switchtype=7).Create()
    else:
      try:
        jsoncolor = json.loads(Devices[1].Color)
        self.dimmerValues[0] = jsoncolor['r']
        self.dimmerValues[1] = jsoncolor['g']
        self.dimmerValues[2] = jsoncolor['b']
        self.masterLevel = int(Devices[1].sValue)
      except:
        self.Log("failed to parse color:'"+Devices[1].Color+"' or sValue:'"+Devices[1].sValue+"' for level", 1, 3)
    
    self.Log("Started current status: " + str(self.currentColor) + " dimmer values: " + str(self.dimmerValues), 2, 2)
    
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.Log("onStop called", 9, 1)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port, 3, 2)
      self.sendMessage({'command' : 'serverinfo'})
      self.errorReported = False
    else:
      if not self.errorReported:
        self.errorReported = True
        self.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 3,2)

    return

  def UpdateDevices(self, Value = 10):
  
    color = json.dumps({
      'm':3, 
      'r':self.dimmerValues[0],
      'g':self.dimmerValues[1],
      'b':self.dimmerValues[2],
      'ww':0,
      'cw':0,
      't':0,
    })
    
    # Value 0=off, 10=rg, other is mode
    if (Value == 0):
      self.UpdateRGBDevice(1,0,self.masterLevel, color)
    elif (Value == 10):
      self.UpdateRGBDevice(1,15,self.masterLevel, color)
    else:
      self.UpdateRGBDevice(1,1,self.masterLevel, color)
   
    #self.selectorMap[Value]
    self.UpdateDevice(2, Value, Value)
          
    return
  
  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage Data", Level = 9, BytesAsStr = True)

    self.readata.extend(Data)
    dataparsed = None
    try:
      decoded_response = self.readata.decode("utf-8")
      dataparsed = json.loads(decoded_response)
      self.readata.clear()
    except:
      pass # happens when json message is incomplete
   
    update = False
    if (dataparsed is not None):
      # Check effects have changed
      if ("info" in dataparsed) and ("effects" in dataparsed["info"]):
        effects = []
        self.effectFileMap = {}
        sourcestring = "Auto|Fixed|"
        for itm in dataparsed["info"]["effects"]:
          tmp = itm["name"].upper()
          if "UDP" not in tmp and "SHUTDOWN" not in tmp:
            effects.append(itm["name"])
            sourcestring += itm["name"] + "|"
            self.effectFileMap[itm["script"] ] = itm["name"]
      
        amount = len(effects)+2
        sourcestring = sourcestring[:-1]
      
        self.DumpVariable(effects, "Effects", Level = 4, BytesAsStr = True)
        self.DumpVariable(self.effectFileMap, "EffectFileMap", Level = 5, BytesAsStr = True)
        self.SourceOptions = {'LevelActions': '|'*amount,
               'LevelNames': sourcestring,
               'LevelOffHidden': 'false',
               'SelectorStyle': '1'}
        
        dictValue=0
        for item in sourcestring.split('|'):
          self.selectorMap[dictValue] = item
          dictValue = dictValue + 10
        self.DumpVariable(self.selectorMap, "SelectorMap", Level = 7, BytesAsStr = True)
               
        if (2 in Devices):
          if Devices[2].Options != self.SourceOptions:
            self.Log("Effects have changed. Updating switch.", Level = 2, Type = 2)
            Devices[2].Delete()
            Domoticz.Device(Name="Mode", Unit=2, TypeName="Selector Switch", Switchtype=18, Used=1, Options=self.SourceOptions, Image=Images["HyperionMode"].ID).Create()
        else:
          self.Log("Effects device not present add it.", Level = 2, Type = 2)
          Domoticz.Device(Name="Mode", Unit=2, TypeName="Selector Switch", Switchtype=18, Options=self.SourceOptions, Image=Images["HyperionMode"].ID).Create()
      
      # actual color
      
      if ("info" in dataparsed) and ("activeLedColor" in dataparsed["info"]):
        self.DumpVariable(dataparsed["info"]["activeLedColor"], "Active Led", Level = 8, BytesAsStr = True)
        if ("RGB Value" in dataparsed["info"]["activeLedColor"]):
          if (len(dataparsed["info"]["activeLedColor"]["RGB Value"]) >= 3):
            self.currentColor[0] = dataparsed["info"]["activeLedColor"]["RGB Value"][0]
            self.currentColor[1] = dataparsed["info"]["activeLedColor"]["RGB Value"][1]
            self.currentColor[2] = dataparsed["info"]["activeLedColor"]["RGB Value"][2]
            update = True
     
      # actual effect:
      Value = 10
      if ("info" in dataparsed) and ("activeEffects" in dataparsed["info"]):
        self.DumpVariable(dataparsed["info"]["activeEffects"], "Active Effect", Level = 8, BytesAsStr = True)
        if ("script" in dataparsed["info"]["activeEffects"]):
          effectactive = self.effectFileMap[dataparsed["info"]["activeEffects"]["script"]]
          
          for key, val in self.selectorMap.items():
            self.Log(str(key)+": "+str(val)+" => looking for "+ str(effectactive), 8, 1)
            if (val == effectactive):
              Value = Key
              update = True
              break
          
      if (update):
        self.updateFromDeviceStatus()
        self.UpdateDevices(Value)
    return

  def sendMessage(self, jsonData):
    self.DumpVariable(jsonData, "Sending message")

    data = json.dumps(jsonData, sort_keys=True)
    data = data+ '''\n'''
    if self.checkConnection():
      self.connection.Send(data)
    return
  
  def onCommand(self, Unit, Command, Level, Hue):
    CommandStr = str(Command)
    self.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + CommandStr + "', Level: " + str(Level)+", Hue: " + str(Hue), 6, 1)
    
    updateLevel = Level
    
    if Unit == 2: # mode
      if ( CommandStr == "Off") or (Level == 0):
        updateLevel = 0
      elif (Level == 10):
        self.sendMessage({"command" : "color", "color": self.currentColor, "priority": self.priority})
      else:
        self.sendMessage({"command" : "effect", "effect" : {"name":self.selectorMap[Level]},"priority":self.priority})
        
      self.UpdateDevices(updateLevel)
    else:
      updateLevel = 10
      if (CommandStr == "Set Color" ):
        jsoncolor = json.loads(Hue)
        self.masterLevel = Level    
        self.dimmerValues[0] = jsoncolor['r']
        self.dimmerValues[1] = jsoncolor['g']
        self.dimmerValues[2] = jsoncolor['b']
      elif ( CommandStr == "Set Level" ):
        self.masterLevel = Level
      elif ( CommandStr == "Off"):
        updateLevel = 0
        
      self.currentColor[0] = self.convertMasterLevel(self.dimmerValues[0])
      self.currentColor[1] = self.convertMasterLevel(self.dimmerValues[1])
      self.currentColor[2] = self.convertMasterLevel(self.dimmerValues[2])
      if updateLevel > 0:
        self.sendMessage({"command" : "color", "color": self.currentColor, "priority": self.priority})

    self.UpdateDevices(updateLevel)
    if updateLevel <= 0:
      #self.sendMessage({"command" : "clearall"})
      self.sendMessage({"command" : "clear", "priority" : self.priority})
       
    return
  
  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.Log("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8, 1)
    
    return

  def onDisconnect(self, Connection):
    self.Log("onDisconnect "+Connection.Address+":"+Connection.Port, 7, 2)

    return

  def onHeartbeat(self):
    self.Log("onHeartbeat called, open messages: " + str(self.outstandingMessages), 9, 1)
    self.checkConnection()

    return

####################### Specific helper functions for plugin #######################    
  def convertMasterLevel(self, val):
    # Converts [0-255] => [0-255] time master level
    val = val * self.masterLevel; 
    if (val >= 25500):
      return 255;
    elif (val <= 0):
      return 0;
    else:
      return int(round(val/100))
      
  def updateFromDeviceStatus(self):
    self.dimmerValues[0] = self.currentColor[0]
    self.dimmerValues[1] = self.currentColor[1]
    self.dimmerValues[2] = self.currentColor[2]
    
    max = 0
    for i in range(3):
      if (max < self.dimmerValues[i]):
        max = self.dimmerValues[i]
        
    if (max >= 255):
      self.masterLevel = 100 
    else:
      for i in range(3):
        if (max > 0):
          self.dimmerValues[i] = int(round(float(self.dimmerValues[i])*255.0/float(max)))
      self.masterLevel = int(round((max*100.0)/255.0))

####################### Generic helper member functions for plugin #######################  
   
  def UpdateRGBDevice(self, Unit, n_Value, s_Value, color):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
      self.Log("Update ["+Devices[Unit].Name+"] from: ('"+str(Devices[Unit].nValue)+":'"+str(Devices[Unit].sValue )+"':"+str(Devices[Unit].Color )+"') to: ("+str(n_Value)+":'"+str(s_Value)+"':"+str(color )+"') ", 5, 1)
      Devices[Unit].Update(nValue=n_Value, sValue=str(s_Value), Color=color)
    return
    
  def UpdateDevice(self, Unit, n_Value, sValue1, sValue2 = None):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
      if sValue2 is None:
        s_Value = str(sValue1)
      else:
        s_Value = str(sValue1)+";"+str(sValue2)
        
      if (Devices[Unit].nValue != n_Value) or (Devices[Unit].sValue != s_Value):
        self.Log("Update ["+Devices[Unit].Name+"] from: ('"+str(Devices[Unit].nValue)+":'"+str(Devices[Unit].sValue )+"') to: ("+str(n_Value)+":'"+str(s_Value)+"')", 5, 1)
        Devices[Unit].Update(nValue=n_Value, sValue=s_Value)
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

