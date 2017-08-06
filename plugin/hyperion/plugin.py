# HYPERION
#
# Description: To control a Hyperion (ambilight for raspberry) via the JSON server
# Author: elgringo
#
# History:
# 1.0.0   05-08-2017  Initial version

"""
<plugin key="Hyperion" name="Hyperion" author="elgringo" version="1.0.2" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="192.168.13.9"/>
    <param field="Port" label="Port" width="40px" required="true" default="19444"/>
    
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
import json


from datetime import datetime, timedelta
import time
import random
import urllib.request 
import json

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 2  # lose connection after
  logLevel = 0                # logLevel
  
  readata = bytearray()       # history
  SourceOptions = {}
  selectorMap = {}
  effectFileMap = {}
  
  priority = 1                # priority channel
  currentColor = [0,0,0]      # RGB
  
  dimmerValues = [0,0,0]      # values of sliders
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
      self.LogError("Debuglevel '"+Parameters["Mode6"]+"' is not an integer")
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    else:
      Domoticz.Heartbeat(20)
      
    self.LogMessage("onStart called", 9)
    self.connection = Domoticz.Connection(Name="Hyperion", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
      
    # ICONS
    if ("HyperionLedRed" not in Images): Domoticz.Image('HyperionLedRed.zip').Create()
    if ("HyperionLedBlue" not in Images): Domoticz.Image('HyperionLedBlue.zip').Create()
    if ("HyperionLedGreen" not in Images): Domoticz.Image('HyperionLedGreen.zip').Create()

    if (1 not in Devices):
      Domoticz.Device(Name="Red",       Unit=1, Type=244, Subtype=73, Switchtype=7, Image=Images["HyperionLedRed"].ID).Create()
    if (2 not in Devices):
      Domoticz.Device(Name="Green",     Unit=2, Type=244, Subtype=73, Switchtype=7, Image=Images["HyperionLedGreen"].ID).Create()
    if (3 not in Devices):
      Domoticz.Device(Name="Blue",      Unit=3, Type=244, Subtype=73, Switchtype=7, Image=Images["HyperionLedBlue"].ID).Create()
     
    # Devices for color picking do no work since it will not return RGB / HSV values.... 
    #Domoticz.Device(Name="RGB Light", Unit=7, Type=241, Subtype=2, Switchtype=7).Create() 
    #Domoticz.Device(Name="Saturatie", Unit=8, Type=244, Subtype=73, Switchtype=7).Create() 
    
    # set default values:
    for i in range(1,4):
      try:
        self.dimmerValues[i-1] = int(Devices[i].sValue.strip('\''))
      except:
        pass
      self.currentColor[i-1] = self.uiToRGB(self.dimmerValues[i-1])
      
    self.LogMessage("Started current status: " + str(self.currentColor) + " dimmer values: " + str(self.dimmerValues), 2 )
    
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.LogMessage("onStop called", 9)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.LogMessage("Connected successfully to: "+Connection.Address+":"+Connection.Port, 3)
      self.sendMessage({'command' : 'serverinfo'})
      self.errorReported = False
    else:
      if not self.errorReported:
        self.errorReported = True
        self.LogMessage("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 3)

    return

  def UpdateDevices(self, Value = 10):
    red = self.rgbToUI(self.currentColor[0])
    if (red <= 0):
      self.UpdateDevice(1, 0, str(red))
    elif (red >= 100):
      self.UpdateDevice(1, 1, str(red))
    else:
      self.UpdateDevice(1, 2, str(red))
      
    green = self.rgbToUI(self.currentColor[1])
    if (green <= 0):
      self.UpdateDevice(2, 0, str(green))
    elif (green >= 100):
      self.UpdateDevice(2, 1, str(green))
    else:
      self.UpdateDevice(2, 2, str(green))
      
    blue = self.rgbToUI(self.currentColor[2])
    if (blue <= 0):
      self.UpdateDevice(3, 0, str(blue))
    elif (blue >= 100):
      self.UpdateDevice(3, 1, str(blue))
    else:
      self.UpdateDevice(3, 2, str(blue))
      
    #self.selectorMap[Value]
    self.UpdateDevice(6, Value, Value)
          
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
               
        if (6 in Devices):
          if Devices[6].Options != self.SourceOptions:
            self.LogMessage("Effects have changed. Updating switch.", Level = 2)
            Devices[6].Delete()
            Domoticz.Device(Name="Mode", Unit=6, TypeName="Selector Switch", Switchtype=18, Used=1, Options=self.SourceOptions).Create()
        else:
          self.LogMessage("Effects device not present add it.", Level = 2)
          Domoticz.Device(Name="Mode", Unit=6, TypeName="Selector Switch", Switchtype=18, Options=self.SourceOptions).Create()
      
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
            self.LogMessage(str(key)+": "+str(val)+" => looking for "+ str(effectactive), 8)
            if (val == effectactive):
              Value = Key
              update = True
              break
          
      if (update):
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
    self.LogMessage("onCommand called for Unit " + str(Unit) + ": Parameter '" + CommandStr + "', Level: " + str(Level)+", Hue: " + str(Hue), 6)
    
    if Unit == 6: # mode
      if ( CommandStr == "Off") or (Level == 0):
        self.sendMessage({"command" : "clearall"})
        Level = 0
      elif (Level == 10):
        self.sendMessage({"command" : "color", "color": self.currentColor, "priority": self.priority})
      else:
        self.sendMessage({"command" : "effect", "effect" : {"name":self.selectorMap[Level]},"priority":self.priority})
        
      self.UpdateDevices(Level)
    else:
      if ( CommandStr == "Off"):
        self.currentColor[Unit-1] = self.uiToRGB(0)
      elif ( CommandStr == "On"):
        self.currentColor[Unit-1] = self.uiToRGB(self.dimmerValues[Unit-1])
      elif ( CommandStr == "Set Level" ):
        self.dimmerValues[Unit-1] = Level
        self.currentColor[Unit-1] = self.uiToRGB(Level)
      self.sendMessage({"command" : "color", "color": self.currentColor, "priority": self.priority})
      self.UpdateDevices(10)
   
    return
  
  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.LogMessage("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8)
    
    return

  def onDisconnect(self, Connection):
    self.LogMessage("onDisconnect "+Connection.Address+":"+Connection.Port, 7)

    return

  def onHeartbeat(self):
    self.LogMessage("onHeartbeat called, open messages: " + str(self.outstandingMessages), 9)
    
    self.checkConnection()

    return

####################### Specific helper functions for plugin #######################    
  def uiToRGB(self, val):
    # Converts [0-100] => [0-255]
    if (val >= 100):
      return 255;
    elif (val <= 0):
      return 0;
    else:
      return int(round(2.55*val))
  
  def rgbToUI(self, val):
    # Converts [0-255] => [0-100]
    if (val >= 255):
      return 100;
    elif (val <= 0):
      return 0;
    else:
      return int(round(val/2.55))
  
    
 
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

