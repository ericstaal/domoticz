# LG 2011 TV
#
# Description: Connect to LG tv. Only after TV has been switched on
#
# Author: elgringo
#
# History:
# 1.0.0   01-07-2017  Initial version
# 1.0.2   31-07-2017  Updated with new API

"""
<plugin key="LGtv" name="LG TV" author="elgringo" version="1.0.2" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP address" width="200px" required="true" default="192.168.13.15"/>
    <param field="Port" label="Port" width="30px" required="false" default="8080"/>
    <param field="Mode2" label="Heartbeat interval" width="50px" required="true">
      <options>
        <option label="10" value="10"/>
        <option label="15" value="15"/>
        <option label="20" value="20" default="true"/>
        <option label="25" value="25"/>
        <option label="30" value="30"/>
      </options>
    </param>
    <param field="Mode4" label="Pairing key" width="200px" default="" /> 
    <param field="Mode5" label="File location" width="200px" required="true" default="/tmp/" /> 
        
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
import re
import os
import socket
import struct
import subprocess
import xml.etree.ElementTree as etree

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 5  # lose conenction after
  logLevel = 0                # logLevel
  
  regexOnline = re.compile('1 packets transmitted, 1 (packets |)received')
  regexIp = re.compile('^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
  ip = None
  mac = None
  tempFile = None
  port = 8080
  lastState = False
  key = "" 
  
  queuedCommands = []
  sessionState = 0 # 0 = pairing, 1 = session, 2 = command
  session = None # session ID, updated every heartbeat???
  
  # dictionary with all codes
  LGCodes = {
"status_bar": 35,
"quick_menu": 69,
"home_menu": 67,
"premium_menu": 89,
"installation_menu": 207,
"factory_advanced_menu1": 251,
"factory_advanced_menu2": 255,
"power_off": 8,
"sleep_timer": 14,
"left": 7,
"right": 6,
"up": 64,
"down": 65,
"select": 68,
"back": 40,
"exit": 91,
"red": 114,
"green": 113,
"yellow": 99,
"blue": 97,
"0": 16,
"1": 17,
"2": 18,
"3": 19,
"4": 20,
"5": 21,
"6": 22,
"7": 23,
"8": 24,
"9": 25,
"underscore": 76,
"play": 176,
"pause": 186,
"fast_forward": 142,
"rewind": 143,
"stop": 177,
"record": 189,
"tv_radio": 15,
"simplink": 126,
"input": 11,
"component_rgb_hdmi": 152,
"component": 191,
"rgb": 213,
"hdmi": 198,
"hdmi1": 206,
"hdmi2": 204,
"hdmi3": 233,
"hdmi4": 218,
"av1": 90,
"av2": 208,
"av3": 209,
"usb": 124,
"slideshow_usb1": 238,
"slideshow_usb2": 168,
"channel_up": 0,
"channel_down": 1,
"channel_back": 26,
"favorites": 30,
"teletext": 32,
"t_opt": 33,
"channel_list": 83,
"greyed_out_add_button?": 85,
"guide": 169,
"info": 170,
"live_tv": 158,
"av_mode": 48,
"picture_mode": 77,
"ratio": 121,
"ratio_4_3": 118,
"ratio_16_9": 119,
"energy_saving": 149,
"cinema_zoom": 175,
"3d": 220,
"factory_picture_check": 252,
"volume_up": 2,
"volume_down": 3,
"mute": 9,
"audio_language": 10,
"sound_mode": 82,
"factory_sound_check": 253,
"subtitle_language": 57,
"audio_description": 145
}
  
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
    
    self.connection = Domoticz.Connection(Name="LG_TCP", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])
      
    if (self.regexIp.match(Parameters["Address"] )):
      self.ip = Parameters["Address"]
    else:
      self.LogError("'"+Parameters["Address"]+"' is not a valid IP address." )
    
    self.tempFile = Parameters["Mode5"] + "ping_"+Parameters["Address"]
    self.LogMessage ( "Temp file: " + self.tempFile, 3)
    try:
      self.port = int(Parameters["Port"])
    except Exception as e:
      self.LogError("Port is not a number: "+ Parameters["Port"])
    
    try: 
      Domoticz.Heartbeat(int(Parameters["Mode2"]))
    except:
      pass
      
    self.key = Parameters["Mode4"] 
    
    # initial cleanup
    if (os.path.isfile(self.tempFile)):
      subprocess.call('sudo chmod +wr '+ self.tempFile , shell=True)
      os.remove(self.tempFile)
         
    # create buttons
    if (len(Devices) == 0):
      Domoticz.Device(Name="Power",         Unit=1, TypeName="Switch").Create() 
      
      Domoticz.Device(Name="Volume up",     Unit=2, TypeName="Switch").Create()
      Domoticz.Device(Name="Volume down",   Unit=3, TypeName="Switch").Create()
      
      Domoticz.Device(Name="Channel up",    Unit=4, TypeName="Switch").Create()
      Domoticz.Device(Name="Channel down",  Unit=5, TypeName="Switch").Create()
      
      Domoticz.Device(Name="HDMI",          Unit=6, TypeName="Switch").Create() # or TV
      Domoticz.Device(Name="TV/Radio",      Unit=7, TypeName="Switch").Create() 
      #Domoticz.Device(Name="OK",            Unit=8, TypeName="Switch").Create() # or HDMI1
      Domoticz.Device(Name="Exit",          Unit=9, TypeName="Switch").Create()
      
    #ICONS
    if ("LGtvchanneldown" not in Images): Domoticz.Image('LGtvchanneldown.zip').Create()
    if ("LGtvchannelup" not in Images): Domoticz.Image('LGtvchannelup.zip').Create()
    if ("LGtvplasma_tv" not in Images): Domoticz.Image('LGtvplasma_tv.zip').Create()
    if ("LGtvsatellite_dish" not in Images): Domoticz.Image('LGtvsatellite_dish.zip').Create()
    if ("LGtvexit" not in Images): Domoticz.Image('LGtvexit.zip').Create()
    if ("LGtvvolmin" not in Images): Domoticz.Image('LGtvvolmin.zip').Create()
    if ("LGtvvolplus" not in Images): Domoticz.Image('LGtvvolplus.zip').Create()
    if ("LGtvsystem" not in Images): Domoticz.Image('LGtvsystem.zip').Create()
    if ("LGtvok" not in Images): Domoticz.Image('LGtvok.zip').Create()
    
    if (1 in Devices):
      Devices[1].Update(nValue=Devices[1].nValue, sValue=str(Devices[1].sValue), Image=Images["LGtvplasma_tv"].ID)
    if (2 in Devices):
      Devices[2].Update(nValue=Devices[2].nValue, sValue=str(Devices[2].sValue), Image=Images["LGtvvolplus"].ID)
    if (3 in Devices):
      Devices[3].Update(nValue=Devices[3].nValue, sValue=str(Devices[3].sValue), Image=Images["LGtvvolmin"].ID)   
    if (4 in Devices):
      Devices[4].Update(nValue=Devices[4].nValue, sValue=str(Devices[4].sValue), Image=Images["LGtvchannelup"].ID)    
    if (5 in Devices):
      Devices[5].Update(nValue=Devices[5].nValue, sValue=str(Devices[5].sValue), Image=Images["LGtvchanneldown"].ID)  
    if (6 in Devices):
      Devices[6].Update(nValue=Devices[6].nValue, sValue=str(Devices[6].sValue), Image=Images["LGtvsystem"].ID)          
    if (7 in Devices):
      Devices[7].Update(nValue=Devices[7].nValue, sValue=str(Devices[7].sValue), Image=Images["LGtvsatellite_dish"].ID)  
    if (8 in Devices):
      Devices[8].Update(nValue=Devices[8].nValue, sValue=str(Devices[8].sValue), Image=Images["LGtvok"].ID)
    if (9 in Devices):
      Devices[9].Update(nValue=Devices[9].nValue, sValue=str(Devices[9].sValue), Image=Images["LGtvexit"].ID)
      
    self.lastState = Devices[1].nValue != 0 # was on/off
      
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.LogMessage("onStop called", 9)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.LogMessage("Connected successfully to: "+Connection.Address+":"+Connection.Port, 5)
      
      # if connect we must send data
      # depending on if a key/session/command is known
      if (len(self.key) <= 2):
        self.LogMessage("Pairing key is unknown. Request pairing key (shown on TV)", 1)
        reqKey = "<!--?xml version=\"1.0\" encoding=\"utf-8\"?--><auth><type>AuthKeyReq</type></auth>"
        self.sessionState = 0 
        self.sendMessage(Message=reqKey, URL="/hdcp/api/auth")
        
      else:
        if self.session is None: # or always session id
          pairCmd = '<?xml version="1.0" encoding="utf-8"?><auth><type>AuthReq</type><value>'+ self.key + '</value></auth>'
          self.sessionState = 1
          self.sendMessage(Message=pairCmd, URL="/hdcp/api/auth")
          
        else: # message
          items = len(self.queuedCommands)
          if items > 0:
            cmd = self.queuedCommands.pop(0)
            self.LogMessage("Sending command '" + cmd +"', still "+str(items-1)+" command in queue", 5)
            
            cmdText = '<?xml version="1.0" encoding="utf-8"?><command><session>'+self.session+'</session><name>HandleKeyInput</name><value>'+str(self.LGCodes[cmd])+'</value></command>'
            self.sessionState = 2
            self.sendMessage(Message=cmdText, URL="/hdcp/api/dtv_wifirc") 
                  
    else:
      self.LogMessage("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 4)
      self.queuedCommands.clear() # clear send commands
      self.session = None
        
    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage SessionState: "+ str(self.sessionState) + ", Data", Level=8, BytesAsStr = True)
    
    if ('Status' in Data) and ('Data' in Data):
      datastr = (Data['Data'].decode("utf-8"))
      
      if (Data['Status'] == '200') and (self.sessionState == 1):
        try:
          tree = etree.XML(Data['Data'])
          self.session = tree.find('session').text
          self.LogMessage("Session ID: "+self.session , 7)
        except:
          pass
    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.LogMessage("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 8)
    
    CommandStr = str(Command)
      
    if (Unit == 1):
      if ( CommandStr == "Off"):
        self.queuedCommands.append("power_off")
    if (Unit == 2):
      self.queuedCommands.append("volume_up")
    if (Unit == 3):
      self.queuedCommands.append("volume_down")
    if (Unit == 4):
      self.queuedCommands.append("channel_up")
    if (Unit == 5):
      self.queuedCommands.append("channel_down")
    if (Unit == 6):
      self.queuedCommands.append("hdmi1")
    if (Unit == 7):
      self.queuedCommands.append("tv_radio")
    if (Unit == 8):
      self.queuedCommands.append("select")
    if (Unit == 9):
      self.queuedCommands.append("exit")
    
    if len(self.queuedCommands) > 0:
      self.DumpVariable(self.queuedCommands, "queuedCommands")
      self.checkConnection()
      
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.LogMessage("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8)
    
    return

  def onDisconnect(self, Connection):
    items = len(self.queuedCommands)
    self.LogMessage("onDisconnect "+Connection.Address+":"+Connection.Port+", still "+ str(items)+" in the queue", 7)
   
    # if there are still command continue
    if (items > 0) and (len(self.key) > 2):
      self.DumpVariable(self.queuedCommands, "queuedCommands", Level=7)
      self.checkConnection()
        
    return

  def onHeartbeat(self):
    self.LogMessage("onHeartbeat called, open messages: " + str(self.outstandingMessages), 9)
   
    # check if TV is online
    if (os.path.isfile(self.tempFile)):
      online = False
      try:
      
        # check current status
        subprocess.call('sudo chmod +wr '+ self.tempFile , shell=True)
          
        file = open(self.tempFile)
        text = file.read()
        file.close()
        
        online = len(self.regexOnline.findall(text)) > 0
        self.LogMessage("Is device online: "+ str(online), 7)
        os.remove(self.tempFile)
      except Exception as e:
        self.LogError("Failed reading '"+self.tempFile+"' : "+ str(e))
        
      if online: # device is online
        if not self.lastState: # last state was offline
          Devices[1].Update( 1, "On") # update
          self.lastState = True 
      else:
        self.session = None
        if self.lastState:
          Devices[1].Update( 0, "Off")
          self.lastState = False
          
    command = 'ping -c 1 -n -s 1 -q '+ self.ip  + ' > '+self.tempFile+' &'
    subprocess.call(command , shell=True)
    self.LogMessage(command, 9)
      
    return

####################### Specific helper functions for plugin #######################   

  def sendMessage(self, Message, URL, Verb="POST", Headers={ 'Content-Type': 'application/atom+xml', 'Connection': 'Keep-Alive'}):
    #'Content-Type': 'application/atom+xml; charset=utf-8'
    Headers['Host']=Connection.Address+":"+Connection.Port
    data = {"Verb":Verb, "URL":URL, "Headers": Headers, 'Data': Message}
    self.DumpVariable(data, "Data to send")
    self.connection.Send(data)

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
