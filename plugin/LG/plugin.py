# LG 2011 TV
#
# Description: Connect to LG tv. Only after TV has been switched on
#
# Author: elgringo
#
# History:
# 1.0.0   01-07-2017  Initial version
# 1.0.2   31-07-2017  Updated with new API
# 1.0.3   06-08-2017  Added mute button
# 1.0.4   25-05-2018  Removed bash ping used internal ICMP
# 1.0.5   06-08-2018  Update logging
# 1.0.6   10-08-2018  Fix connection issues
# 1.0.7   20-11-2018  Let mute give a status
# 1.0.8   02-12-2018  Added source / channel name
# 1.1.0   04-12-2018  Input as selector, removed ping
# 1.1.1   05-12-2018  Cleanup some code
# 1.1.2   14-02-2019  Connection fix
# 1.1.3   16-03-2019  Clear dropped comands on start
# 1.1.4   06-04-2019  Destroy connection when it took more than 60 seconds
# 1.1.5   12-05-2019  Insert exit command when last send command was a while ago (to wake up TV)
# 1.1.6   02-01-2020  Auto drop commands after 5 minutes no activity
# 1.1.7   26-04-2020 drop command wehn not send for 30 in heartbeart

"""
<plugin key="LGtv" name="LG TV" author="elgringo" version="1.1.7" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP address" width="200px" required="true" default="192.168.13.15"/>
    <param field="Port" label="Port" width="30px" required="false" default="8080"/>
    <param field="Mode2" label="Heartbeat interval" width="50px" required="true">
      <options>
        <option label="5" value="5"/>
        <option label="8" value="8"/>
        <option label="10" value="10"/>
        <option label="15" value="15"/>
        <option label="20" value="20" default="true"/>
        <option label="25" value="25"/>
        <option label="30" value="30"/>
      </options>
    </param>
    <param field="Mode3" label="max queued commands" width="50px" required="true">
      <options>
        <option label="1" value="1" default="true"/>
        <option label="2" value="2"/>
        <option label="3" value="3" />
        <option label="4" value="4"/>
        <option label="5" value="5"/>
        <option label="10" value="10"/>
        <option label="20" value="20"/>
        <option label="50" value="50"/>
      </options>
    </param>
    <param field="Mode4" label="Pairing key" width="200px" default="" /> 
    <param field="Mode1" label="Sources (eg: off|tv|hdmi1|hdmi4|radio|av1|av3|usb)" width="550px" required="true" default="off|tv|hdmi1|radio"/>
    <param field="Mode5" label="Sources name" width="550px" required="true" default="Off|TV|Receiver|Radio"/>
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
import re
import time

class BasePlugin:
  
  connection = None           # Network connection
  logLevel = 0                # logLevel
 
  ip = None
  port = 8080
  
  tvmuted = False
  lastConnected = False
  key = ""  # pairing key
  
  regexIp = re.compile('^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
  
  source = 0 # based on mode1 and mode5 (1 is actual, 5 is name)
  
  queuedCommands = []
  sessionState = 0 # 0 = pairing, 1 = session, 2 = command/poll
  session = None # session ID
  maxQueued = 1
  selectorMap = {}
  
  srcLastLive = 0
  srcRadio = 0
  srcTv = 0
  srcOff = 0
  srcHdmi = []
  srcAv = []
  
  lastStartConnectTime = 0
  lastCommandTime = 0
  
  # dictionary with all codes
  LGCodes = { "status_bar": 35, "quick_menu": 69, "home_menu": 67, "premium_menu": 89, "installation_menu": 207, "factory_advanced_menu1": 251, "factory_advanced_menu2": 255,
              "power_off": 8, "sleep_timer": 14, "left": 7, "right": 6, "up": 64, "down": 65, "select": 68, "back": 40, "exit": 91, "red": 114, "green": 113, "yellow": 99,
              "blue": 97, "0": 16, "1": 17, "2": 18, "3": 19, "4": 20, "5": 21, "6": 22, "7": 23, "8": 24, "9": 25, "underscore": 76, "play": 176, "pause": 186, "fast_forward": 142,
              "rewind": 143, "stop": 177, "record": 189, "tv_radio": 15, "simplink": 126, "input": 11, "component_rgb_hdmi": 152, "component": 191, "rgb": 213, "hdmi": 198,
              "hdmi1": 206, "hdmi2": 204, "hdmi3": 233, "hdmi4": 218, "av1": 90, "av2": 208, "av3": 209, "usb": 124, "slideshow_usb1": 238, "slideshow_usb2": 168, "channel_up": 0,
              "channel_down": 1, "channel_back": 26, "favorites": 30, "teletext": 32, "t_opt": 33, "channel_list": 83, "greyed_out_add_button?": 85, "guide": 169, "info": 170,
              "live_tv": 158, "av_mode": 48, "picture_mode": 77, "ratio": 121, "ratio_4_3": 118, "ratio_16_9": 119, "energy_saving": 149, "cinema_zoom": 175, "3d": 220,
              "factory_picture_check": 252, "volume_up": 2, "volume_down": 3, "mute": 9, "audio_language": 10, "sound_mode": 82, "factory_sound_check": 253, "subtitle_language": 57,
              "audio_description": 145
  }
  
  def checkConnection(self, checkonly = False):
    # Check connection and connect none
    isConnected = False
    
    if self.connection is None:
      self.connection = Domoticz.Connection(Name="LG_TCP", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])
      self.Log("checkConnection: Connection created", 9, 1)
    else:
      if self.connection.Connected():
        isConnected = True
      else:
        if (not self.connection.Connecting()) and (not checkonly):
          self.connection.Connect()
          self.lastStartConnectTime = time.time()
          self.Log("checkConnection: Trying to connect", 9, 1)
        else:
          nu = time.time()
          if (nu - self.lastStartConnectTime) > 60:
            self.connection = None
            self.Log("checkConnection: last connection attempt took more than "+str(nu -self.lastStartConnectTime)+" seconds. Destroy connection", 5, 3)
    
    return isConnected
    
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.Log("Debuglevel '"+Parameters["Mode6"]+"' is not an integer", 1, 3)
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    self.Log("onStart called", 9, 1)
                
    if (self.regexIp.match(Parameters["Address"] )):
      self.ip = Parameters["Address"]
    else:
      self.Log("'"+Parameters["Address"]+"' is not a valid IP address.", 1, 3 )
    
    try:
      self.port = int(Parameters["Port"])
    except Exception as e:
      self.Log("Port is not a number: "+ Parameters["Port"], 1, 3)
        
    try:
      self.maxQueued = int(Parameters["Mode3"])
    except Exception as e:
      self.Log("'"+Parameters["Mode3"]+"' is not a number.", 1, 3 )
      
    try: 
      Domoticz.Heartbeat(int(Parameters["Mode2"]))
    except:
      pass
      
    self.key = Parameters["Mode4"] 
    
    dictValue = 0
    sourceOptions = {}
    for item in Parameters["Mode1"].split('|'):
      # parse into type, since we cannot read all specific types...
      if item == "off":
        self.srcOff = dictValue
        self.selectorMap[dictValue] = "power_off"
      elif item == "tv":
        self.srcTv = dictValue
        self.selectorMap[dictValue] = "tv_radio"
      elif item == "radio":
        self.srcRadio = dictValue
        self.selectorMap[dictValue] = "tv_radio"
      elif item == "hdmi1" or item == "hdmi2" or item == "hdmi3" or item == "hdmi4":
        self.srcHdmi.append(dictValue)
        self.selectorMap[dictValue] = item
      elif item == "av1" or item == "av2" or item == "av3" or item == "usb" or item == "usb":
        self.srcAv.append(dictValue)
        self.selectorMap[dictValue] = item
      else:
        self.Log("Unknown source type '"+str(item)+"' with value "+str(dictValue), Level = 2, Type = 3)
        self.selectorMap[dictValue] = item
      dictValue = dictValue + 10
        
    srcLastLive = self.srcTv
    if (Parameters["Mode1"].count('|') != Parameters["Mode5"].count('|')):
      self.Log("Sources ("+Parameters["Mode1"]+") and names ("+Parameters["Mode5"]+") do not match! Using only sources", 1, 3)
      
      sourceOptions = {'LevelActions': '|'*Parameters["Mode1"].count('|'),
               'LevelNames': Parameters["Mode1"],
               'LevelOffHidden': 'false',
               'SelectorStyle': '0'} # 1 = combobox, 0 = buttons
    else:
      sourceOptions = {'LevelActions': '|'*Parameters["Mode5"].count('|'),
               'LevelNames': Parameters["Mode5"],
               'LevelOffHidden': 'false',
               'SelectorStyle': '0'}
        
    #ICONS
    if ("LGtvchanneldown" not in Images): Domoticz.Image('LGtvchanneldown.zip').Create()
    if ("LGtvchannelup" not in Images): Domoticz.Image('LGtvchannelup.zip').Create()
    if ("LGtvexit" not in Images): Domoticz.Image('LGtvexit.zip').Create()
    if ("LGtvvolmin" not in Images): Domoticz.Image('LGtvvolmin.zip').Create()
    if ("LGtvvolplus" not in Images): Domoticz.Image('LGtvvolplus.zip').Create()
    if ("LGtvok" not in Images): Domoticz.Image('LGtvok.zip').Create()
    if ("LGtvmute" not in Images): Domoticz.Image('LGtvmute.zip').Create()
    
    # create buttons
    if (1 not in Devices): 
      Domoticz.Device(Name="Source", Unit=1, TypeName="Selector Switch", Switchtype=18, Image=2, Options=sourceOptions).Create()
    elif (Devices[1].Options != sourceOptions):
      self.Log("Sources or names have changed.", Level = 2, Type = 1)
      
      # update does not work, so delte it and readd it.
      Devices[1].Delete()
      Domoticz.Device(Name="Source",     Unit=1, TypeName="Selector Switch", Switchtype=18, Image=2, Used=1, Options=sourceOptions).Create()
    
    if (2 not in Devices):
      Domoticz.Device(Name="Volume up",     Unit=2, TypeName="Switch", Image=Images["LGtvvolplus"].ID).Create()
    if (3 not in Devices):
      Domoticz.Device(Name="Volume down",   Unit=3, TypeName="Switch", Image=Images["LGtvvolmin"].ID).Create()
    if (4 not in Devices):
      Domoticz.Device(Name="Channel up",    Unit=4, TypeName="Switch", Image=Images["LGtvchannelup"].ID).Create()
    if (5 not in Devices):
      Domoticz.Device(Name="Channel down",  Unit=5, TypeName="Switch", Image=Images["LGtvchanneldown"].ID).Create()
    if (8 not in Devices):
      Domoticz.Device(Name="Mute",          Unit=8, TypeName="Switch", Image=Images["LGtvmute"].ID).Create()
    else:
      self.UpdateDevice(8,0,"Off")
      
    if (9 not in Devices):
      Domoticz.Device(Name="Exit",          Unit=9, TypeName="Switch", Image=Images["LGtvexit"].ID).Create()
    if (11 not in Devices): 
      Domoticz.Device(Name="Channel",       Unit=11, Type=243, Subtype=19, Switchtype=0).Create()
    else:
      self.UpdateDevice(11,0,"Off")
    self.lastConnected = False
    
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.Log("onStop called", 9,1)
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port, 5, 2)
      
      # device connected
      if not self.lastConnected: # last state was offline
        # source is updated of first status message
        self.setSourceDevice(10) # 10 is probably the first valid input
        self.lastCommandTime = 0
        
        if len(self.queuedCommands) > 0:
          self.Log("New connection made dropped "+str(len(self.queuedCommands))+" commands", 4, 2)
          self.queuedCommands.clear()
          
        self.UpdateDevice(8,0,"Off")
        self.tvmuted = False
        self.lastConnected = True 
      
      # if connect we must send data depending on if a key/session/command is known
      if (len(self.key) <= 2):
        self.Log("Pairing key is unknown. Request pairing key (shown on TV)", 1, 2)
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
          self.sessionState = 2
          if items > 0:
            cmd = self.queuedCommands.pop(0)
            self.Log("Sending command '" + cmd +"', still "+str(items-1)+" command in queue", 5, 1)
            if cmd in self.LGCodes:
              cmdText = '<?xml version="1.0" encoding="utf-8"?><command><session>'+self.session+'</session><name>HandleKeyInput</name><value>'+str(self.LGCodes[cmd])+'</value></command>'
            else:
              self.Log("Command '"+str(cmd)+" is not known in dictionay, send as actual value", 5, 1)
              cmdText = '<?xml version="1.0" encoding="utf-8"?><command><session>'+self.session+'</session><name>HandleKeyInput</name><value>'+str(cmd)+'</value></command>'
            self.sendMessage(Message=cmdText, URL="/hdcp/api/dtv_wifirc") 
          else: # just request the status
            self.sendMessage(Message="", URL="/hdcp/api/data?target=cur_channel&session="+self.session, Verb="GET")
    else: # status != 0
      self.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description+" dropped "+str(len(self.queuedCommands))+" commands", 5, 2)
        
      self.setSourceDevice(self.srcOff)
      self.lastConnected = False
      self.tvmuted = False
      self.queuedCommands.clear()
      self.session = None
      self.sessionState = 0
      self.UpdateDevice(8,0,"Off") 
      
    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage SessionState: "+ str(self.sessionState) + ", Data", Level=7, BytesAsStr = True)
    
    if ('Status' in Data) and ('Data' in Data):
      datastr = (Data['Data'].decode("utf-8"))
      self.DumpVariable(datastr, "data string", Level=7, BytesAsStr = True)
      
      if Data['Status'] == '200':
        if self.sessionState == 1:
          self.session = self.getTag(datastr, 'session')
          self.Log("Session ID: "+self.session , 7, 1)
        else:
          self.determineSource(datastr)
      if Data['Status'] == '401':
        self.Log("Received error while sending data; retry connection" , 4, 1)
        self.session = None
        self.sessionState = 0

    return

  def onCommand(self, Unit, Command, Level, Hue):
    CommandStr = str(Command)
    self.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + CommandStr + "', Level: " + str(Level)+", Hue: " + str(Hue), 8, 1)

    #self.DumpVariable(self.selectorMap, "selectormap: ", Level=7, BytesAsStr = True)
    currentlen = len(self.queuedCommands)
    nu = time.time()
        
    if self.maxQueued > currentlen:
      # send command to wake up TV
      
      if (nu - self.lastCommandTime) > 250:
        if self.lastCommandTime == 0:
          self.Log("onCommand: no command send yet. Insert additional exit to wake TV", 4, 2)
        else:
          self.Log("onCommand: last command send "+str(nu - self.lastCommandTime)+" seconds ago. Insert additional exit to wake TV", 4, 2)
        self.queuedCommands.append("exit") 
        
      self.lastCommandTime = time.time()
        
      if (Unit == 1):
        newsrc = self.source
        if (CommandStr == "Set Level"):
          if Level != self.source:
            newsrc = Level
            if (Level == self.srcRadio or Level == self.srcTv): # check what last live source was
              if self.srcLastLive != Level and self.source != self.srcTv and self.source != self.srcRadio:
                self.queuedCommands.append(self.selectorMap[Level]) 
                self.queuedCommands.append("stopSending") 
              self.queuedCommands.append(self.selectorMap[Level])
              self.srcLastLive = Level
            else:
              self.queuedCommands.append(self.selectorMap[Level]) 
       
        elif (CommandStr == "Off"):
          newsrc = self.srcOff
          self.queuedCommands.append(self.selectorMap[self.srcOff]) 
        elif (CommandStr == "On"):
          if self.source != self.srcTv: 
            newsrc = self.srcTv 
            self.queuedCommands.append(self.selectorMap[self.srcTv])
                       
        self.setSourceDevice(newsrc)
       
      elif (Unit == 2):
        self.queuedCommands.append("volume_up") 
      elif (Unit == 3):
        self.queuedCommands.append("volume_down")
      elif (Unit == 4):
        self.queuedCommands.append("channel_up")
      elif (Unit == 5):
        self.queuedCommands.append("channel_down")
      elif (Unit == 8):
        if (CommandStr == "On" and not self.tvmuted):
          self.queuedCommands.append("mute")
          self.tvmuted = True
        elif (CommandStr == "Off" and self.tvmuted):
          self.queuedCommands.append("mute")
          self.tvmuted = False
        
        if self.tvmuted:
          Devices[8].Update( 1, "On")
        else:
          Devices[8].Update( 0, "Off")
      elif (Unit == 9):
        self.queuedCommands.append("exit")
      
      self.DumpVariable(self.queuedCommands, "queuedCommands")
      if len(self.queuedCommands) > 0 and currentlen == 0:
        self.checkConnection()
    else:
      self.Log("Still "+ str(len(self.queuedCommands))+ " commands queued, drop this command" , 4, 1)
      
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.Log("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8, 1)
    return

  def onDisconnect(self, Connection):
    items = len(self.queuedCommands)
    if items > 0:
      self.Log("onDisconnect "+Connection.Address+":"+Connection.Port+", still "+ str(items)+" in the queue", 4, 2)
      if (len(self.key) > 2): # if there are still command continue (and key must be present of course)
        self.DumpVariable(self.queuedCommands, "queuedCommands", Level=6)
        if (self.queuedCommands[0] == "stopSending"):
          self.Log("stopSending command found, wait until next connection to continue", 4, 2)
        else:
          self.checkConnection()
    else:
      self.Log("onDisconnect "+Connection.Address+":"+Connection.Port+", no more commands in the queue", 6, 2)
        
    return

  def onHeartbeat(self):
    #clean up old not executed command (older than 30 seconds)
    currentlen = len(self.queuedCommands)
    nu = time.time()
    if ((nu - self.lastCommandTime) > 30) and (currentlen > 0) :
      self.Log("onHeartbeat: last command send "+str(nu - self.lastCommandTime)+" seconds ago, still "+str(currentlen)+" commands waiting, all dropped", 4, 3)
      self.queuedCommands.clear()
      currentlen = 0
    
    if (currentlen == 0 ): 
      self.Log("onHeartbeat called, check connection", 9,1)
      self.checkConnection()
    elif ((currentlen > 0) and self.queuedCommands[0] == "stopSending"):
      self.Log("onHeartbeat called, stopSending command dropped, check connection", 4,1)
      self.queuedCommands.pop(0)
      self.checkConnection()

    return

####################### Specific helper functions for plugin #######################   
  def setSourceDevice(self, src, txt = None):
    if (txt is None):
      if (src == self.srcOff):
        txt = "Off"
      elif (src == self.srcRadio):
        txt = "Radio"
      elif (src == self.srcTv):
        txt = "TV" 
      elif (src in self.srcHdmi):
        txt = "HDMI"
      elif (src in self.srcAv):
        txt = "AV"
      else:
        txt = "?"
    
    if (src != self.source):
      self.source = src
      self.UpdateDevice(1, self.source, self.source)
      self.UpdateDevice(11,0,txt)
      self.Log("Set source from "+str(self.source)+" to "+str(src)+" and text to '"+txt+"'", 5, 1)
    elif (src == self.srcTv or src == self.srcRadio):
      self.UpdateDevice(11,0,txt)
      self.Log("Set text to '"+txt+"'", 5, 1)
      
      
  def determineSource(self, xmldata):
    #try:
    
    txt = None
    src = self.source
    error = False
    name = None
    
    type = self.getTag(xmldata, 'type')
    
    if (len(type) > 0):
      major = int(self.getTag(xmldata, 'major')) # channel number
      if not self.lastConnected:
        src = self.srcOff
      else:
        if type == "cable":
          name = self.getTag(xmldata, 'name')
          txt = "["+str(major)+"] "+name
          
          if major >= 100:
            src = self.srcRadio
          else:
            src = self.srcTv
          self.srcLastLive = src
        elif type == "terrestrial" and major == 0: # av 
          txt = "AV"
          if len(self.srcAv) > 0:
            if src not in self.srcAv:
              src = self.srcAv[0]
        elif type == "satellite" and major == 16368: # hdmi
          txt = "HDMI" 
          if len(self.srcHdmi) > 0:
            if src not in self.srcHdmi:
              src = self.srcHdmi[0]
        else:
          txt = "?" 
          error = True
          
      if error or self.logLevel >= 5:
        if (name is None):
          name = self.getTag(xmldata, 'name')
        physicalNum = self.getTag(xmldata, 'physicalNum')
        sourceIndex = self.getTag(xmldata, 'sourceIndex')
        minor = self.getTag(xmldata, 'minor')
        
        if (error):
          self.Log("Could not determine source type:'"+type+", major:"+str(major)+", minor:"+minor+", physicalNum:"+physicalNum+", sourceIndex:"+sourceIndex+", name:"+name, 2, 3)
        else:
          if src in self.selectorMap:
            self.Log("Source determined as "+str(src)+"("+self.selectorMap[src] +"), '"+txt+"' (type:'"+type+", major:"+str(major)+", minor:"+minor+", physicalNum:"+physicalNum+", sourceIndex:"+sourceIndex+", name:"+name+")", 5, 1)
          else:
            self.Log("Source determined as "+str(src)+", '"+txt+"' (type:'"+type+", major:"+str(major)+", minor:"+minor+", physicalNum:"+physicalNum+", sourceIndex:"+sourceIndex+", name:"+name+")", 5, 1)
        
    self.setSourceDevice(src, txt)
    
    #except:
    #  pass
      
    return
    
  def getTag(self, data, tag):
    begintag = "<"+str(tag)+">"
    begin = data.find(begintag)
    begin = begin + len(begintag)
    
    end = data.find("</"+str(tag)+">")
    returnvalue = ""
    if (end > begin and begin >= 0):
      returnvalue = data[begin:end]
      
    return returnvalue
    
  def sendMessage(self, Message, URL, Verb="POST", Headers={ 'Content-Type': 'application/atom+xml; charset=utf-8', 'Connection': 'Keep-Alive'}):
    Headers['Host']=self.connection.Address+":"+self.connection.Port
    data = {"Verb":Verb, "URL":URL, "Headers": Headers, 'Data': Message}
    self.DumpVariable(data, "Data to send", Level=8, BytesAsStr = True)
    if self.connection.Connected:
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

