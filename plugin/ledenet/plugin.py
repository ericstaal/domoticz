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
# 1.0.3   22-05-2018  Onheartbeat debug level to 8, remove urllib for python 3.5
# 1.0.4   20-06-2018  Solved issue with max open messages
# 1.0.5   06-08-2018  Update logging
# 2.0.0   13-11-2018  Changed to RGBW colorpicker, added modes, updated icons

"""
<plugin key="Ledenet" name="LedeNet" author="elgringo" version="2.0.0" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="192.168.13.80"/>
    <param field="Port" label="Port" width="30px" required="true" default="5577"/>
    <param field="Mode1" label="Custom mode 1 [R,G,B,(W)|...]" width="700px" required="true" default="200,0,0,0|200,200,0,0" />
    <param field="Mode2" label="Custom mode 2 [R,G,B,(W)|...]" width="700px" required="true" default="50,50,50,50|60,50,40,30|10,20,30,40" />
    <param field="Mode3" label="Custom mode 3 [R,G,B,(W)|...]" width="700px" required="true" default="100,0,0|0,100,0|0,0,100|0,0,0,100" />
    <param field="Mode4" label="Custom mode 4 [R,G,B,(W)|...]" width="700px" required="true" default="255,255,255|0,0,0,255|0,0,0" />
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
from datetime import datetime, timedelta
import time
import subprocess
import json
import re

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 0  # lose connection after
  logLevel = 0                # logLevel
  
  commandOn = b'\x71\x23\x0F\xA3'
  commandOff = b'\x71\x24\x0F\xA4'
  commandStatus = b'\x81\x8A\x8B\x96'
  
  currentStatus = [False,0,0,0,0]        # 0 = True/False (on/off), 1=Red, 2=Green, 3=Blue, 4=white, Status from the lightOn
  currentmode = 0x61                     # current mode static|or...
  currentspeed = 0                       # 0x1-0x1f
  
  mode = 0                               # from rgb picker
  masterLevel = 0                        # from rgb picker, master brightness (svalue)
  dimmerValues = [0,0,0,0]               # RGBW values from control, used to determine requestedstatus
  power = False                          # from rgb picker,
  autospeed = 1                          # auto mode speed [1-100%] 
  automode = 0                           # auto mode
  custommodechanged = False
  selectorMap = {}
  
  mustSendUpdate = False    # if the domotica values has been changed but not yet updated to the ledenet (connection problems)
    
  readata = bytearray()         # history
  skipStatus = False            # when written skip next status since it can be previous value

  def checkConnection(self, checkonly = False):
    # Check connection and connect none
    isConnected = False
    
    try:
      if not self.connection is None:
        if self.connection.Connected():
          isConnected = True
        else:
          if (not self.connection.Connecting()) and (not checkonly):
            self.outstandingMessages = 0
            self.connection.Connect()
          
    except:
      self.connection = None
      self.Log("CheckConnection error, try to reset", 1, 3)

    
    return isConnected
    
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.Log("Debuglevel '"+Parameters["Mode6"]+"' is not an integer", 1, 3)
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    else:
      Domoticz.Heartbeat(20)
      
    self.Log("onStart called", 9, 1)
    self.connection = Domoticz.Connection(Name="LedenetBinair", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
      
    try:
      self.maxOutstandingMessages = int(Parameters["Mode5"])
    except:
      self.Log("max open messages '"+Parameters["Mode5"]+"' is not an integer", 1, 3)
      
    # ICONS
    if ("LedenetRGBspeed" not in Images): Domoticz.Image('LedenetRGBspeed.zip').Create()
    if ("LedenetRGBmode" not in Images): Domoticz.Image('LedenetRGBmode.zip').Create()
    
    if (1 not in Devices):
      Domoticz.Device(Name="RGB Light", Unit=1, Type=241, Subtype=6,  Switchtype=7).Create()
    else:
      try:
        jsoncolor = json.loads(Devices[1].Color)
        self.mode = int(jsoncolor['m'])
        self.power = Devices[1].nValue > 0
        self.dimmerValues[0] = jsoncolor['r']
        self.dimmerValues[1] = jsoncolor['g']
        self.dimmerValues[2] = jsoncolor['b']
        self.dimmerValues[3] = jsoncolor['ww']
        self.masterLevel = int(Devices[1].sValue)
      except:
        self.Log("failed to parse color:'"+Devices[1].Color+"' or sValue:'"+Devices[1].sValue+"' for level", 1, 3)
    if (2 not in Devices):
      Domoticz.Device(Name="Speed",Unit=2, Type=244, Subtype=73, Switchtype=7, Image=Images["LedenetRGBspeed"].ID).Create()
    else:
      try:
        self.autospeed = int(Devices[2].sValue)
      except:
        self.Log("Failed to parse sValue:'"+Devices[1].sValue+"' for speed", 1, 3)
    
    self.selectorMap[0] = 0x61       
    self.selectorMap[10] = 1 
    self.selectorMap[20] = 2
    self.selectorMap[30] = 3
    self.selectorMap[40] = 4
    self.selectorMap[50] = 0x25
    self.selectorMap[60] = 0x26
    self.selectorMap[70] = 0x27
    self.selectorMap[80] = 0x28
    self.selectorMap[90] = 0x29
    self.selectorMap[100] = 0x2A
    self.selectorMap[110] = 0x2B
    self.selectorMap[120] = 0x2C
    self.selectorMap[130] = 0x2D
    self.selectorMap[140] = 0x2E
    self.selectorMap[150] = 0x2F
      
    SourceOptions = {'LevelActions': "|||||||||||||||",
                     'LevelNames': "Static|Custom 1|Custom 2|Custom 3|Custom 4|Multi color|Red|Green|Glue|Yellow|Cyan|Purple|White|Red Green|Red Blue|Green Blue",
                     'LevelOffHidden': 'false',
                     'SelectorStyle': '1'}
    
    if (3 not in Devices):
      Domoticz.Device(Name="Mode", Unit=3, TypeName="Selector Switch", Switchtype=18, Options=SourceOptions, Image=Images["LedenetRGBmode"].ID).Create()
    else:
      try:
        self.automode = int(Devices[3].sValue)
      except:
        self.Log("Failed to parse sValue:'"+Devices[3].sValue+"' for automode", 1, 3)
   
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.Log("onStop called", 9, 1)
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port, 3, 2)
    else:
      self.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 3, 2)
      self.updateDevices()

    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage Data", Level=8)

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
        tempmode = self.readata[3]
        tempspeed = self.readata[5]
        tempstatus[1] = self.readata[6] # Red
        tempstatus[2] = self.readata[7] # Green
        tempstatus[3] = self.readata[8] # Blue
        tempstatus[4] = self.readata[9] # White

        adjcurrentmode = self.currentmode
        if adjcurrentmode < 10:
          adjcurrentmode = 0x60
          
        if (tempmode == 0x61):
          if (tempstatus != self.currentStatus or tempmode != self.currentmode or tempspeed != self.currentspeed):
            self.Log("LedeNet changed R:%d, G:%d, B:%d, W:%d, Speed:0x%X, Mode:0x%X, pwr:%d => R:%d, G:%d, B:%d, W:%d, Speed:0x%X, Mode:0x%X, pwr:%d" %
            (self.currentStatus[1],self.currentStatus[2],self.currentStatus[3], self.currentStatus[4], self.currentspeed, self.currentmode, self.currentStatus[0], tempstatus[1], tempstatus[2], tempstatus[3], tempstatus[4],tempspeed, tempmode,tempstatus[0]), 6, 2)
                    
            self.currentStatus = tempstatus
            self.currentmode = tempmode
            self.currentspeed = tempspeed
            
            self.updateFromDeviceStatus()

            
        elif (tempstatus[0] != self.currentStatus[0] or tempmode != adjcurrentmode or tempspeed != self.currentspeed):
          self.Log("LedeNet changed Speed:0x%X, Mode:0x%X, pwr:%d => Speed:0x%X, Mode:0x%X, pwr:%d" %
          (self.currentspeed, self.currentmode, self.currentStatus[0], tempspeed, tempmode, tempstatus[0]), 6, 2)
          
          self.currentStatus[0] = tempstatus[0]
          self.currentmode = tempmode
          self.currentspeed = tempspeed
          
          self.updateFromDeviceStatus()
      
      else:
        self.skipStatus = False      
        
      self.readata.clear()
    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 7, 1)
    
    CommandStr = str(Command)
    self.requestedStatus = self.currentStatus[:]
    
    # Calculate color and send update to devices
    if ( CommandStr == "Off"):
      if (Unit == 1):
        self.power = False
      elif (Unit == 2):
        self.autospeed = 1
      elif (Unit == 3):
        self.automode = 0x61
    elif ( CommandStr == "On"):
      if (Unit == 1):
        self.power = True
    elif ( CommandStr == "Set Level" ):
      if (Unit == 1):
        self.masterLevel = Level
        self.power = Level > 0
        if (self.power):
          self.automode = 0x61
      elif (Unit == 2):
        if Level <= 0:
          self.autospeed = 1
        else:
          self.autospeed = Level 
      elif (Unit == 3):
        self.automode = self.selectorMap[Level]
        if (self.automode <= 10):
          self.custommodechanged = True
    elif (CommandStr == "Set Color" ):
      if (Unit == 1):
        jsoncolor = json.loads(Hue)
        self.masterLevel = Level    
        self.dimmerValues[0] = jsoncolor['r']
        self.dimmerValues[1] = jsoncolor['g']
        self.dimmerValues[2] = jsoncolor['b']
        self.dimmerValues[3] = jsoncolor['ww']
        self.mode = int( jsoncolor['m'] )
        self.automode = 0x61

    # update controler
    self.updateController()
    
    # update UI
    self.updateDevices()
    
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.Log("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8, 1)
    
    return

  def onDisconnect(self, Connection):
    self.Log("onDisconnect "+Connection.Address+":"+Connection.Port, 7, 1)
    return

  def onHeartbeat(self):
    self.Log("onHeartbeat called, open messages: " + str(self.outstandingMessages), 8, 1)
    
    if self.checkConnection():
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
  def updateFromDeviceStatus(self):
    # convert function
    self.dimmerValues[0] = self.currentStatus[1]
    self.dimmerValues[1] = self.currentStatus[2]
    self.dimmerValues[2] = self.currentStatus[3]
    self.dimmerValues[3] = self.currentStatus[4]
    self.power = self.currentStatus[0]
    self.autospeed = int(round((30 - (self.currentspeed - 1))*3.3))+1 
    
    if not self.power:
      self.automode = 0x61
    elif self.currentmode < 10:
      self.automode = 1 # custom mode, use the first one
    else:
      self.automode = self.currentmode

    if self.automode == 0x61:
      if (self.dimmerValues[0] > 0 or self.dimmerValues[1] > 0 or self.dimmerValues[2] > 0):
        if (self.dimmerValues[3] > 0):
          self.mode = 4
        else:
          self.mode = 3
      else:
        self.mode = 1
    
    if (self.mode == 1):
      self.masterLevel = int(round((self.dimmerValues[3]*100.0) / 255.0)) 
      self.dimmerValues[3] = 255
    else:
      max = 0
      for i in range(4):
        if (max < self.dimmerValues[i]):
          max = self.dimmerValues[i]
          
      if (max >= 255):
        self.masterLevel = 100 
      else:
        for i in range(4):
          if (max > 0):
            self.dimmerValues[i] = int(round(float(self.dimmerValues[i])*255.0/float(max)))
        self.masterLevel = int(round((max*100.0)/255.0))
      
    self.updateDevices()
    return
  
  def convertMasterLevel(self, val):
    # Converts [0-255] => [0-255] time master level
    val = val * self.masterLevel; 
    if (val >= 25500):
      return 255;
    elif (val <= 0):
      return 0;
    else:
      return int(round(val/100))
  
  def programCustom(self, custommode):
    if self.custommodechanged:
      customdata = ""
      msg = [0x51]
      if custommode == 4:
        customdata = Parameters["Mode4"]
      elif  custommode == 3:
        customdata = Parameters["Mode3"]
      elif  custommode == 2:
        customdata = Parameters["Mode2"]
      else:
        customdata = Parameters["Mode1"]
       
      customsplitdata = customdata.split("|")
      error = False
      for i in range(0,16):
        if (i < len(customsplitdata)):
          colorsplit = customsplitdata[i].split(",")
          for j in range(0,4):
            val = j +1
            if (val == 4):
              val = 0
            
            if j < len(colorsplit):
              try:
                val = int(colorsplit[j])
              except:
                error = True
            msg.append(val)
        else:
          msg.extend([1,2,3,0])
      
      msg.extend([self.currentspeed, 0x3A, 0xFF, 0x0F])
      
      if error:
        self.Log("Failed to parse custom mode "+str(custommode)+", '"+customdata+"'", 1, 3)
      else:
        self.Log("Set custom mode "+str(custommode)+", '"+customdata+"'", 4, 1)
      checksum = 0
      for itm in msg:
        checksum = checksum + itm
      checksum = checksum % 0x100
      msg.append(checksum)
      
    
      msgbytes = bytes(msg)
      self.connection.Send(msgbytes)
      self.DumpVariable(msgbytes, "Send custom mode message", Level=8)
      self.custommodechanged = False
      return True
    return False
    
  def updateController(self): # send update from domtoicz to ledenet
    if self.checkConnection(True):
      updateColor = False
      requestedStatus = self.currentStatus[:]
      requestedStatus[0] = self.power
      
      if (self.mode == 3 or self.mode == 4):
        requestedStatus[1] = self.convertMasterLevel( self.dimmerValues[0] )
        requestedStatus[2] = self.convertMasterLevel( self.dimmerValues[1] )
        requestedStatus[3] = self.convertMasterLevel( self.dimmerValues[2] )
      else:
        requestedStatus[1] = 0
        requestedStatus[2] = 0
        requestedStatus[3] = 0
      if (self.mode == 1 or self.mode == 4):
        requestedStatus[4] = self.convertMasterLevel( self.dimmerValues[3] )
      else:
        requestedStatus[4] = 0
      self.Log("Current: " + str(self.currentStatus) + " requested: " + str(requestedStatus), 7, 1)
  
      for i in range(1,5):
        if self.currentStatus[i] != requestedStatus[i]:
          updateColor = True
          break
      
      # update color
      if updateColor:
        checksum = (requestedStatus[1] + requestedStatus[2] + requestedStatus[3] + 0x3F +(requestedStatus[4] - 0xFF)) % 0x100
        msg = bytes([0x31, requestedStatus[1], requestedStatus[2], requestedStatus[3], requestedStatus[4], 0x00, 0x0F, checksum])
        self.connection.Send(msg)
        self.DumpVariable(msg, "Send color message", Level=8)
        self.skipStatus = True
      
      # update power
      if (self.currentStatus[0] != requestedStatus[0]):
        if requestedStatus[0]:
          self.connection.Send(self.commandOn)
          self.skipStatus = True
        else:
          self.connection.Send(self.commandOff)
          self.skipStatus = True
        
      #mode & speed
      newspeed = int(round((100.0 - self.autospeed)/3.3))+1
      if newspeed > 0x1F:
        newspeed = 0x1F
      elif newspeed < 0x01:
        newspeed = 0x01
       
      if (self.currentmode != self.automode or self.currentspeed != newspeed):
        self.Log("Speed level:%d speed changed from:0x%X to 0x%X Mode changed from:0x%X to 0x%X"% (self.autospeed, self.currentspeed, newspeed, self.currentmode, self.automode ), 6, 1)
        self.currentmode = self.automode
        if self.currentmode < 10:
          self.currentmode = 0x60
        self.currentspeed = newspeed
        
        if (self.automode <= 10):
          self.programCustom(self.automode)
        else:
          # predefined
          checksum = (0x61 + self.currentmode + self.currentspeed + 0x0F ) % 0x100
        
          msg = bytes([0x61, self.currentmode, self.currentspeed, 0x0F, checksum])
          self.connection.Send(msg)
          self.DumpVariable(msg, "Send mode message", Level=8)
          self.skipStatus = True
                
      # reset status
      self.currentStatus = requestedStatus[:]
      self.mustSendUpdate = False
    else:
      self.mustSendUpdate = True
    
  def updateDevices(self): # updates devices based on the curent values
    color = json.dumps({
      'm':self.mode, 
      'r':self.dimmerValues[0],
      'g':self.dimmerValues[1],
      'b':self.dimmerValues[2],
      'ww':self.dimmerValues[3],
      'cw':0,
      't':0,
    })
    
    # 0 = off, 1 = on, 15=%
    for key, value in self.selectorMap.items():
      if (value == self.automode):
        self.UpdateDevice(3,key,key)
        break
    
    if self.power:
      if self.automode == 0x61:
        self.UpdateRGBDevice(1,15,self.masterLevel, color)
      else:
        self.UpdateRGBDevice(1,1,self.masterLevel, color)
    else:
      self.UpdateRGBDevice(1,0,self.masterLevel, color)
    
    self.UpdateDevice(2,2,self.autospeed)
    return
   
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

