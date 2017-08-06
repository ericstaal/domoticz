# WOL ping plugin. 
#
# Description: Pings host and activates it via WOL
#
# Author: elgringo
#
# History:
# 1.0.0   01-07-2017  Initial version
# 1.0.1   31-07-2017  Updated with new API

"""
<plugin key="WOLping" name="WOL/Pinger" author="elgringo" version="1.0.1" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP address" width="200px" required="true" default="127.0.0.1"/>
    <param field="Mode1" label="MAC adress" width="200px" required="false"/>
    <param field="Port" label="Port" width="30px" required="false" default="7"/>
    <param field="Mode2" label="Interval" width="50px" required="true" default="10" /> 
    <param field="Mode3" label="Max missed" width="50px" required="true" default="1" /> 
    <param field="Mode4" label="File location" width="200px" required="true" default="/tmp/" /> 
    <param field="Mode5" label="Mode" width="75px">
      <options>
        <option label="ping" value="ping" default="true"/>
        <option label="arping" value="arping" />
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
import binascii
import base64
import html

# additional imports
import re
import os
import socket
import struct
import subprocess
import xml.etree.ElementTree as etree

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 1  # lose conenction after
  logLevel = 0                # logLevel
  
  regexMac = re.compile('^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
  regexOnline = re.compile('1 packets transmitted, 1 (packets |)received')
  regexIp = re.compile('^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
  ip = None
  mac = None
  tempFile = None
  wolport = 7
  arping = True
  lastState = False
  
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
    
    # self.connection = ...
    if (self.regexMac.match(Parameters["Mode1"] )):
      self.mac = Parameters["Mode1"]
      # replace separators
      if len(self.mac) == 12 + 5:
        sep = self.mac[2]
        self.mac = self.mac.replace(sep, '')
        
    if (self.regexIp.match(Parameters["Address"] )):
      self.ip = Parameters["Address"]
    else:
      self.LogError("'"+Parameters["Address"]+"' is not a valid IP adress." )
    
    self.arping = (Parameters["Mode5"] == "arping")
    self.tempFile = Parameters["Mode4"] + "ping_"+Parameters["Address"]
    self.LogMessage( "Temp file: " + self.tempFile, 1)
    try:
      self.wolport = int(Parameters["Port"])
    except Exception as e:
      self.LogError("Port is not a number: "+ Parameters["Port"])
    try:
      self.maxOutstandingMessages = int(Parameters["Mode3"])
    except Exception as e:
      self.LogError("Max missed is not a number: "+ Parameters["Mode3"])
    try: 
      Domoticz.Heartbeat(int(Parameters["Mode2"]))
    except:
      pass
      
    # initial cleanup
    if (os.path.isfile(self.tempFile)):
      subprocess.call('sudo chmod +wr '+ self.tempFile , shell=True)
      os.remove(self.tempFile)
         
    # create a switch
    if (len(Devices) == 0):
      Domoticz.Device(Name="Device", Unit=1, TypeName="Switch").Create()
    
    self.lastState = Devices[1].nValue != 0
      
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.LogMessage("onStop called", 9)
    
    return

  def onConnect(self, Connection, Status, Description):
    self.LogMessage("onConnect "+Connection.Address+":"+Connection.Port+" Status: "+ str(Status)+", Description:"+str(Description), 7)

    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage Data")

    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.LogMessage("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 8)
    
    if ( str(Command) == "On"):
      # send WOL
      self.sendWOL()
        
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.LogMessage("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8)
    
    return

  def onDisconnect(self, Connection):
    self.LogMessage("onDisconnect "+Connection.Address+":"+Connection.Port, 7)

    return

  def onHeartbeat(self):
    self.LogMessage("onHeartbeat called, open messages: " + str(self.outstandingMessages), 9)
    
    if (os.path.isfile(self.tempFile)):
      online = False
      try:
      
        # check current status
        subprocess.call('sudo chmod +wr '+ self.tempFile , shell=True)
          
        file = open(self.tempFile)
        text = file.read()
        file.close()
        
        online = len(self.regexOnline.findall(text)) > 0
        self.LogMessage("Is device online: "+ str(online), 6)
        os.remove(self.tempFile)
      except Exception as e:
        self.LogError("Failed reading '"+self.tempFile+"' : "+ str(e))
        
      if online: # device is online
        if not self.lastState: # last state was offline
          self.outstandingMessages = 0 # reset miss counter
          Devices[1].Update( 1, "On") # update
          self.lastState = True 
      else:
        if self.lastState:
          self.outstandingMessages = self.outstandingMessages + 1
          if self.outstandingMessages > self.maxOutstandingMessages:
            Devices[1].Update( 0, "Off")
            self.lastState = False
          
    if self.arping:
      #ARPING
      command = 'sudo arping -c1 -W 1 '+ self.ip  + ' > '+self.tempFile+' &'
    else:
      #PING
      command = 'ping -c 1 -n -s 1 -q '+ self.ip  + ' > '+self.tempFile+' &'
    subprocess.call(command , shell=True)
    self.LogMessage(command, 9)
      
    return

####################### Specific helper functions for plugin #######################    
  def sendWOL(self):
    # only if WOL exists
    if not (self.mac is None):
      self.LogMessage("Send WOL to MAC: "+ self.mac, 3)
      data = b'FFFFFFFFFFFF' + (self.mac * 20).encode()
      send_data = b'' 

      # Split up the hex values and pack.
      for i in range(0, len(data), 2):
        send_data += struct.pack('B', int(data[i: i + 2], 16))

      # Broadcast it to the LAN.
      sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
      sock.sendto(send_data, ('255.255.255.255', self.wolport))
    
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

