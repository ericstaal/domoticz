# LG
#
# Author: elgringo
# Tested only on raspberry PI
# 
#

"""
<plugin key="LGtv" name="LG TV" author="elgringo" version="1.0.1" externallink="https://github.com/ericstaal/domoticz">
    <description>
LG TV<br/><br/>
Periodic check if TV is online via PING or ARPING. When enabled send a WOL packet (if defined).<br/>
    </description>
    <params>
      <param field="Address" label="IP address" width="200px" required="true" default="192.168.13.15"/>
        <param field="Mode1" label="MAC adress" width="200px" required="false"/>
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
        <param field="Mode6" label="Debug" width="75px">
        <options>
          <option label="True" value="Debug"/>
          <option label="False" value="Normal" default="true" />
        </options>
      </param>
    </params>
</plugin>
"""
import Domoticz
import re
import os
import socket
import struct
import subprocess
import xml.etree.ElementTree as etree

class BasePlugin:
    
    regexMac = re.compile('^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    regexOnline = re.compile('1 packets transmitted, 1 (packets |)received')
    regexIp = re.compile('^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
    ip = None
    mac = None
    tempFile = None
    port = 8080
    lastState = False
    key = "" 
    
    queuedCommands = []
    connectionState = 0 # 0= niet, 1 bezig, 2 = wel
    connection = None
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
    
    def __init__(self):
      pass    
   
    def getHeaders(self, msg):
      headers = { 'Content-Type': 'application/atom+xml; charset=utf-8', 'Content-Length' : "%d"%(len(msg)) }
      return headers
      
    def onStart(self):
      # set parameters
      if Parameters["Mode6"] == "Debug":
        Domoticz.Debugging(1)
      
      if (self.regexMac.match(Parameters["Mode1"] )):
        self.mac = Parameters["Mode1"]
        # replace separators
        if len(self.mac) == 12 + 5:
          sep = self.mac[2]
          self.mac = self.mac.replace(sep, '')
          
      if (self.regexIp.match(Parameters["Address"] )):
        self.ip = Parameters["Address"]
      else:
        Domoticz.Error("'"+Parameters["Address"]+"' is not a valid IP address." )
      
      self.tempFile = Parameters["Mode5"] + "ping_"+Parameters["Address"]
      Domoticz.Log ( "Temp file: " + self.tempFile)
      try:
        self.port = int(Parameters["Port"])
      except Exception as e:
        Domoticz.Log("Port is not a number: "+ Parameters["Port"])
      
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

    def onCommand(self, Unit, Command, Level, Hue):
      CommandStr = str(Command);
      
      # Calculate color and send update to devices
      if (Unit == 1):
        if ( CommandStr == "On"):
          self.sendWOL()
        else: # OFF
          self.queuedCommands.append("power_off")
          self.initializeConnection()
          Devices[1].Update( 0, "Off")
          self.lastState = False
      if (Unit == 2):
        self.queuedCommands.append("volume_up")
        self.initializeConnection()
      if (Unit == 3):
        self.queuedCommands.append("volume_down")
        self.initializeConnection()
      if (Unit == 4):
        self.queuedCommands.append("channel_up")
        self.initializeConnection()
      if (Unit == 5):
        self.queuedCommands.append("channel_down")
        self.initializeConnection()
      if (Unit == 6):
        #self.queuedCommands.append("input")
        self.queuedCommands.append("hdmi1")
        self.initializeConnection()
      if (Unit == 7):
        self.queuedCommands.append("tv_radio")
        self.initializeConnection()
      if (Unit == 8):
        self.queuedCommands.append("select")
        self.initializeConnection()
      if (Unit == 9):
        self.queuedCommands.append("exit")
        self.initializeConnection()

    def sendWOL(self):
      # only if WOL exists
      if not (self.mac is None):
        Domoticz.Log("Send WOL to MAC: "+ self.mac)
        data = b'FFFFFFFFFFFF' + (self.mac * 20).encode()
        send_data = b'' 

        # Split up the hex values and pack.
        for i in range(0, len(data), 2):
          send_data += struct.pack('B', int(data[i: i + 2], 16))

        # Broadcast it to the LAN.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(send_data, ('255.255.255.255', 7))
    
    def onMessage(self, Connection, Data, Status, Extra):
    
      datastr = (Data.decode("utf-8"))
      Domoticz.Debug("Received: " + datastr)
      
      if self.sessionState == 1:
        try:
          tree = etree.XML(Data)
          self.session = tree.find('session').text
        except:
          pass
      return
      
    def onStop(self):
      self.connection = None
      self.connectionState = 0
    
    def initializeConnection(self):
      # create a connection and send all commands
      if self.connection is None:
        self.connection = Domoticz.Connection(Name="LG_TCP", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])
      
      if self.connectionState == 0:
        self.connectionState = 1
        self.connection.Connect()
      
    def onDisconnect(self, Connection):
      self.connectionState = 0
      self.connection = None # reset connection
      
      # if there are still command continue
      items = len(self.queuedCommands)
      if (items > 0) and (len(self.key) > 2):
        self.initializeConnection()
        
      return
    
    def onConnect(self, Connection, Status, Description):
      if (Status == 0):
        self.connectionState = 2
        Domoticz.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port)
        
        # if connect we must send data
        # depending on if a key/session/command is known
        if (len(self.key) <= 2):
          Domoticz.Log("Pairing key is unknown. Request pairing key (shown on TV)")
          reqKey = "<!--?xml version=\"1.0\" encoding=\"utf-8\"?--><auth><type>AuthKeyReq</type></auth>"
          self.sessionState = 0 
          self.connection.Send(Message=reqKey, URL="/hdcp/api/auth", Verb="POST", Headers=self.getHeaders(reqKey))
          
        else:
          if self.session is None: # or always session id
            pairCmd = '<?xml version="1.0" encoding="utf-8"?><auth><type>AuthReq</type><value>'+ self.key + '</value></auth>'
            self.sessionState = 1
            self.connection.Send(Message=pairCmd, URL="/hdcp/api/auth", Verb="POST", Headers=self.getHeaders(pairCmd))
            
          else: # message
            items = len(self.queuedCommands)
            if items > 0:
              cmd = self.queuedCommands.pop(0)
              Domoticz.Log("Sending command '" + cmd +"', still "+str(items-1)+" command in queue")
              
              cmdText = '<?xml version="1.0" encoding="utf-8"?><command><session>'+self.session+'</session><name>HandleKeyInput</name><value>'+str(self.LGCodes[cmd])+'</value></command>'
              self.sessionState = 2
              self.connection.Send(Message=cmdText, URL="/hdcp/api/dtv_wifirc", Verb="POST", Headers=self.getHeaders(cmdText))
              
        
      else:
        self.connectionState = 0
        Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)
        self.queuedCommands.clear() # clear send commands
        # destroy connection and create a new one
        self.connection = None
      return
    
    def onHeartbeat(self):
      
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
          Domoticz.Debug("Is device online: "+ str(online))
          os.remove(self.tempFile)
        except Exception as e:
          Domoticz.Error("Failed reading '"+self.tempFile+"' : "+ str(e))
          
        if online: # device is online
          if not self.lastState: # last state was offline
            Devices[1].Update( 1, "On") # update
            self.lastState = True 
            #self.checkConnection()
        else:
          if self.lastState:
            Devices[1].Update( 0, "Off")
            self.lastState = False
            self.connectionState = 0
         
      command = 'ping -c 1 -n -s 1 -q '+ self.ip  + ' > '+self.tempFile+' &'
      subprocess.call(command , shell=True)
      Domoticz.Debug(command)
      
      # request pairing key if needed
      if (self.lastState) and (len(self.key) <= 2):
        self.initializeConnection()
         
       

global _plugin
_plugin = BasePlugin()

def onStart():
  global _plugin
  _plugin.onStart()
  
def onStop():
  global _plugin
  _plugin.onStop()  

def onMessage(Connection, Data, Status, Extra):
  global _plugin
  _plugin.onMessage(Connection, Data, Status, Extra)
  
def onHeartbeat():
  global _plugin
  _plugin.onHeartbeat()

def onCommand(Unit, Command, Level, Hue):
  global _plugin
  _plugin.onCommand(Unit, Command, Level, Hue)    
  
def onConnect(Connection, Status, Description):
  global _plugin
  _plugin.onConnect(Connection, Status, Description)

def onDisconnect(Connection):
  global _plugin
  _plugin.onDisconnect(Connection)
  
    
# Generic helper functions
def DumpConfigToLog():
  for x in Parameters:
    if Parameters[x] != "":
      Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
  Domoticz.Debug("Device count: " + str(len(Devices)))
  for x in Devices:
    Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
    Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
    Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
    Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
    Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
    Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
  return