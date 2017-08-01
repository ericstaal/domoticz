# LEDENET
#
# Description: 
# All text / settings are in dutch, If you want it translated, feel free to do so :)
# Plugin connects to Ledenet / UFOlight RGB(W) controller (https://www.amazon.com/LEDENET-Controller-Android-Smartphone-Control/dp/B00MDKOSN0)
# It gives RGBW sliders, on/off switch and an 'autolight' feature.
# autolight will switch the light on around sunset, and switches the color at a min/max time. 
# debug mode enables faster autolight switching, and more logging
#
# Author: elgringo
#
# History:
# 1.0.0   01-07-2017  Initial version
# 1.0.2   31-07-2017  Updated with new API

"""
<plugin key="Ledenet" name="LedeNet" author="elgringo" version="1.0.2" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="192.168.13.80"/>
    <param field="Port" label="Port" width="30px" required="true" default="5577"/>
    <param field="Mode1" label="Autolight light off" width="150px" required="true" default="22:45" />
    <param field="Mode2" label="Autolight minimal time same color (minutes)" width="150px" required="true">
      <options>
        <option label="5" value="5"/>
        <option label="10" value="10"/>
        <option label="20" value="20"/>
        <option label="30" value="30" default="true"/>
        <option label="45" value="45"/>
      </options>
    </param>
    <param field="Mode3" label="Autolight maximal same color (minutes)" width="150px" required="true">
      <options>
        <option label="30" value="30"/>
        <option label="45" value="45"/>
        <option label="60" value="60" default="true"/>
        <option label="75" value="75"/>
        <option label="90" value="90"/>
        <option label="120" value="120"/>
        <option label="240" value="240"/>
        <option label="300" value="300"/>
      </options>
    </param>
    <param field="Mode4" label="Autolight margin (minutes)" width="150px" required="true">
      <options>
        <option label="5" value="5"/>
        <option label="10" value="10"/>
        <option label="15" value="15" default="true" />
        <option label="20" value="20"/>
        <option label="25" value="25"/>
        <option label="30" value="30"/>
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

# additional imports
from datetime import datetime, timedelta
import time
import random
import urllib.request 
import json

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 2  # lose conenction after
  logLevel = 0                # logLevel
  
  commandOn = b'\x71\x23\x0F\xA3'
  commandOff = b'\x71\x24\x0F\xA4'
  commandStatus = b'\x81\x8A\x8B\x96'
  
  currentStatus = [False,0,0,0,0]        # 0 = True/False (on/off), 1=Red, 2=Green, 3=Blue, 4=white, Status from the lightOn
  requestedStatus = [False,0,0,0,0]      # from Domoticz
  dimmerValues = [0,0,0,0,0]             # values of sliders
  readata = bytearray()         # history
  skipStatus = False            # when written skip next status since it can be previous value

  autolight = False         # if the autolight mode is enabled
  autolightDataset = dict() # dictionary with datimetime / functionpointer
  mustSendUpdate = False    # if the domotica values has been changed but not yet updated to the ledenet (connection problems)
  mustForceOff = False      # If autolight is enabled, light is on an no sunset on startup
  
  domoticzusername = "user"   # needed to get sunset times
  domoticzpassword = "pwd"
  
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
    
    
    self.connection = Domoticz.Connection(Name="LedenetBinair", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
      
    if (len(Devices) == 0):
      # 241 = limitless, subtype 2= RGB/ 1= RGBW, switchtype 7 = philip
      Domoticz.Device(Name="Red",       Unit=1, Type=244, Subtype=73, Switchtype=7).Create()
      Domoticz.Device(Name="Green",     Unit=2, Type=244, Subtype=73, Switchtype=7).Create()
      Domoticz.Device(Name="Blue",      Unit=3, Type=244, Subtype=73, Switchtype=7).Create()
      Domoticz.Device(Name="White",     Unit=4, Type=244, Subtype=73, Switchtype=7).Create()
      Domoticz.Device(Name="Autolight", Unit=5, TypeName="Switch").Create()
      Domoticz.Device(Name="Power",     Unit=6, TypeName="Switch").Create()
      
      # Devices for color picking do no work since it will not return RGB / HSV values.... 
      #Domoticz.Device(Name="RGB Light", Unit=7, Type=241, Subtype=2, Switchtype=7).Create() 
      #Domoticz.Device(Name="Saturatie", Unit=8, Type=244, Subtype=73, Switchtype=7).Create() 
    
    # ICONS
    if ("LedenetAutoLight" not in Images): Domoticz.Image('LedenetAutoLight.zip').Create()
    if ("LedenetLedRed" not in Images): Domoticz.Image('LedenetLedRed.zip').Create()
    if ("LedenetedBlue" not in Images): Domoticz.Image('LedenetLedBlue.zip').Create()
    if ("LedenetLedGreen" not in Images): Domoticz.Image('LedenetLedGreen.zip').Create()
    if ("LedenetLedYellow" not in Images): Domoticz.Image('LedenetLedYellow.zip').Create()
    
    if (1 in Devices):
      Devices[1].Update(nValue=Devices[1].nValue, sValue=str(Devices[1].sValue), Image=Images["LedenetLedRed"].ID)
    if (2 in Devices):
      Devices[2].Update(nValue=Devices[2].nValue, sValue=str(Devices[2].sValue), Image=Images["LedenetLedGreen"].ID)
    if (3 in Devices):
      Devices[3].Update(nValue=Devices[3].nValue, sValue=str(Devices[3].sValue), Image=Images["LedenetLedBlue"].ID)
    if (4 in Devices):
      Devices[4].Update(nValue=Devices[4].nValue, sValue=str(Devices[4].sValue), Image=Images["LedenetLedYellow"].ID)
    if (5 in Devices):
      Devices[5].Update(nValue=Devices[5].nValue, sValue=str(Devices[5].sValue), Image=Images["LedenetAutoLight"].ID)
 
    # autolight is not saves in the devices itself
    self.autolight = Devices[5].nValue != 0
    if self.autolight:
      now = datetime.now()
      sunset = self.volgendeZonondergang()
      if sunset > now:
        self.LogMessage("Autolight enabled, while no sunset yet ("+str(sunset)+"). Disable LED after connected", 1 )
        self.mustForceOff = True
            
    # set default values:
    self.currentStatus[0] = False
    for i in range(1,5):
      try:
        self.dimmerValues[i] = int(Devices[i].sValue.strip('\''))
      except:
        pass
      self.currentStatus[i] = self.uiToRGB(self.dimmerValues[i])
      
      
    self.LogMessage("Started current status: " + str(self.currentStatus) + " dimmer values: " + str(self.dimmerValues), 2 )
    
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.LogMessage("onStop called", 9)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.LogMessage("Connected successfully to: "+Connection.Address+":"+Connection.Port, 3)
      if self.mustForceOff:
        self.connection.Send(self.commandOff)
        self.mustForceOff = False
    else:
      self.LogMessage("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 3)
      self.updateDevices()

    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage Data")

    # only listen to the status, all other are not needed
    if (Data[0]==0x81 and len(self.readata) == 0):
      self.readata.extend(Data)
      self.outstandingMessages = self.outstandingMessages - 1
    elif (len(self.readata) < 14):
      self.readata.extend(Data)
      
    if (len(self.readata) >= 14):
      if not self.skipStatus:
        tempstatus = [0,0,0,0,0]
        tempstatus[0] = (self.readata[2] == 0x23) # 0x23 is ON, 0x24 is OFF
        tempstatus[1] = self.readata[6] # Red
        tempstatus[2] = self.readata[7] # Green
        tempstatus[3] = self.readata[8] # Blue
        tempstatus[4] = self.readata[9] # White
        if (tempstatus != self.currentStatus):
          # values are different than know, update the UI
          self.currentStatus = tempstatus
          self.updateDevices()
          
          status =  "ON" if self.currentStatus[0] else "OFF"
          self.LogMessage("LedeNet changed to (R,G,B,W):(%d,%d,%d,%d) => %s" %(self.currentStatus[1],self.currentStatus[2],self.currentStatus[3], self.currentStatus[4], status), 6)
      else:
        self.skipStatus = False      
        
      self.readata.clear()
    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.LogMessage("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 8)
    
    CommandStr = str(Command)
    self.requestedStatus = self.currentStatus[:]
    # Calculate color and send update to devices
    if ( CommandStr == "Off"):
      if (Unit < 5 ):
        self.requestedStatus[Unit] = self.uiToRGB(0)
      elif (Unit == 6):
        self.requestedStatus[0] = False
      elif (Unit ==5): # autolight
        self.autolightDataset.clear() # Clear also dictionary with toggle values
        self.autolight = False
    elif ( CommandStr == "On"):
      if (Unit < 5):
        self.requestedStatus[Unit] = self.uiToRGB(self.dimmerValues[Unit])
      elif (Unit == 6):
        self.requestedStatus[0] = True
      elif (Unit ==5): # autolight
        self.autolight = True
    elif ( CommandStr == "Set Level" ):
      if (Unit < 5):
        self.dimmerValues[Unit] = Level
        self.requestedStatus[Unit] = self.uiToRGB(Level)
    
    # update controler
    self.updateController()
    # update UI
    self.updateDevices()
    
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.LogMessage("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8)
    
    return

  def onDisconnect(self, Connection):
    self.LogMessage("onDisconnect "+Connection.Address+":"+Connection.Port, 7)

    return

  def onHeartbeat(self):
    self.LogMessage("onHeartbeat called, open messages: " + str(self.outstandingMessages), 9)
    
    if self.checkConnection():
      uiUpdated = False
      if self.autolight:
        if (len(self.autolightDataset) == 0): 
          self.generateAutolightData() # when empty create new dataset
      
        now = datetime.now()
        sortedkeys = sorted(self.autolightDataset.keys())
        key = sortedkeys[0]
    
        now = datetime.now()
        if key <= now:
          self.autolightDataset[key]()
          del self.autolightDataset[key] 
          uiUpdated = True
      
      if (not uiUpdated):
        if (self.outstandingMessages > self.maxOutstandingMessages):
          self.connection.Disconnect()
        else:
          if self.mustSendUpdate:
            self.updateController()
          else:
            self.readata.clear()
            self.connection.Send(self.commandStatus)
            self.outstandingMessages = self.outstandingMessages + 1
           
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
  
  def updateController(self): # send update from domtoicz to ledenet
    if self.checkConnection(True):
      updateColor = False
      self.LogMessage("Current: " + str(self.currentStatus) + " requested: " + str(self.requestedStatus), 5)
  
      for i in range(1,5):
        if self.currentStatus[i] != self.requestedStatus[i]:
          updateColor = True
          break
      
      # update color
      if updateColor:
        checksum = (self.requestedStatus[1] + self.requestedStatus[2] + self.requestedStatus[3] + 0x3F +(self.requestedStatus[4] - 0xFF)) % 0x100
        msg = bytes([0x31, self.requestedStatus[1], self.requestedStatus[2], self.requestedStatus[3], self.requestedStatus[4], 0x00, 0x0F, checksum])
        self.connection.Send(msg)
        self.DumpVariable(msg, "Send message")
        self.skipStatus = True
      
      # update power
      if (self.currentStatus[0] != self.requestedStatus[0]):
        if self.requestedStatus[0]:
          self.connection.Send(self.commandOn)
          self.skipStatus = True
        else:
          self.connection.Send(self.commandOff)
          self.skipStatus = True
        
      # reset status
      self.currentStatus = self.requestedStatus[:]
      self.mustSendUpdate = False
    else:
      self.mustSendUpdate = True
    
  def updateDevices(self): # updates devices based on the curent values
    if ((Devices[6].nValue != 0) != self.currentStatus[0]):
      if (self.currentStatus[0]):
        self.UpdateDevice(6,1,"On")
      else:
        self.UpdateDevice(6,0,"Off")
        
    if ((Devices[5].nValue != 0) != self.autolight):
      if (self.autolight):
        self.UpdateDevice(5,1,"On")
      else:
        self.UpdateDevice(5,0,"Off")        
    
    for i in range(1,5):
      val = self.rgbToUI(self.currentStatus[i]) 
      if (self.currentStatus[i] == 0):
        self.UpdateDevice(i,0,str(self.dimmerValues[i]))
      elif (val == 100):
        self.UpdateDevice(i,1,str(val))
      else:
        self.UpdateDevice(i,2,str(val))
 
  def volgendeZonondergang(self):
    # sunrise from domoticz... But I don't know how to retrieve it....
    
    try:
      domoticzurl = 'http://127.0.0.1:8080/json.htm?type=command&param=getSunRiseSet'
      encoding = 'utf-8'
      
      inlog = '%s:%s' % (self.domoticzusername, self.domoticzpassword) 
      base64string = b64encode(inlog.encode(encoding)).decode(encoding)
      request = urllib.request.Request(domoticzurl)
      request.add_header("Authorization", "Basic %s" % base64string)
      response = urllib.request.urlopen(request)
      data = response.read()
      
      JSON_object = json.loads(data.decode(encoding))
      time = JSON_object['Sunset'].split(':')
      now = datetime.now()
      ret = datetime(now.year, now.month, now.day, int(time[0]), int(time[1]), 0)
      # when started after sunset use 'now'
      now = now + timedelta(minutes = int(Parameters["Mode4"])) 
      if (now > ret):
        ret = ret + timedelta(days = 1) 
      return ret
    except Exception as e:
      self.LogError("Error retrieving Sunset: "+ str(e))
      now = datetime.now()
      return datetime(now.year, now.month, now.day, 22, 0, 0)

  def generateAutolightData(self):
    # Fills dataset based on parameters. It will be stored in a dictionary (key is datetime, value is function pointer). 
    # When time is passed the function is executed (heartbeat) and removed from dictionary. 
    # When empty it will be refilled for the next day
    
    # Fill datatset
    marginLight = int(Parameters["Mode4"])
    endtimeLight = StringToMinutes(Parameters["Mode1"])
    minTimeColor = int(Parameters["Mode2"])
    maxTimeColor = int(Parameters["Mode3"])
    
    random.seed()
    
    lightOn = self.volgendeZonondergang()
    # config loggen 
    self.LogMessage("Autolight data: margin(min) " + str(marginLight) + ", Endtime(min):" + str(endtimeLight) +" ("+str(timedelta(minutes = endtimeLight))+"), switchtime ["+str(minTimeColor)+","+str(maxTimeColor)+"], Suset:"+str(lightOn), 2)
    margin = random.randint(0, marginLight) - (marginLight*3) / 4 # 1/4 after sunset 3/4 before sunset
    lightOn = lightOn + timedelta(minutes = margin)
    
    # create record
    if Parameters["Mode6"] == "10":
      lightOn = datetime.now()+ timedelta(seconds=10) # prevent waiting :)
      minTimeColor = 1 
      maxTimeColor = 3
      
    margin = random.randint(0, marginLight) - marginLight / 2 + endtimeLight
    lightOff = datetime(lightOn.year, lightOn.month, lightOn.day) + timedelta(minutes = margin)
    if ((Parameters["Mode6"] == "10") or (lightOn > lightOff)):
      lightOff = lightOn+timedelta(minutes=10)
      
    self.addRecord(lightOn, self.lightOn)
    switchTime = lightOn
    
    # Add color changes
    while switchTime < lightOff:
      margin = random.randint(minTimeColor, maxTimeColor)
      switchTime = switchTime + timedelta(minutes = margin)
      if (switchTime < lightOff):
        self.addRecord(switchTime, self.lightRandomColor)
        
    self.addRecord(lightOff, self.lightOff)
          
  def addRecord(self, date, func):
    delta = timedelta(milliseconds = 1)
    while date in self.autolightDataset.keys():
      date = date + delta
      break
    self.autolightDataset[date] = func
    self.LogMessage("Autolight: " + str(date) + ", " + func.__name__, 3)
  
  def lightOn(self):
    self.lightRandomColor(False) 
    self.requestedStatus[0] = True
    self.updateController()
    self.updateDevices()
    
  def lightOff(self):
    self.requestedStatus[0] = False
    self.updateController()
    self.updateDevices()
    self.generateAutolightData() # Finished generate new data

  def lightRandomColor(self, selfUpdate = True):
    red = random.randint(0, 255)
    green = random.randint(0, 255)
    blue = random.randint(0, 255)
    white = random.randint(0, 40) # little less white to aad more color cahanges
    
    minBrightness = 100
    maxBrightness = 600
    
    som = red + green + blue + white
    factor = 1
    if som < minBrightness:
      factor = float(minBrightness) / float(som)
    elif som > maxBrightness:
      factor = float(maxBrightness) / float(som)
      
    red = int(red * factor)
    green = int(green * factor)
    blue = int(blue * factor)
    white = int(white * factor)
    
    if red > 255:
      red = 255
    if green > 255:
      green = 255
    if blue > 255:
      blue = 255
    if white > 255:
      white = 255
      
    self.requestedStatus[1] = red;
    self.requestedStatus[2] = green;
    self.requestedStatus[3] = blue;
    self.requestedStatus[4] = white;
    
    if selfUpdate:
      self.updateController()
      self.updateDevices()

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
        self.LogMessage("Update ["+Devices[Unit].Name+"] from: ('"+str(Devices[Unit].nValue)+",'"+str(Devices[Unit].sValue )+"') to: ("+str(nValue)+":'"+str(sValue)+"')", 5)
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
          txt = Item.decode("utf-8")
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

