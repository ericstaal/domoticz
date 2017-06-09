#
#     Denon & Marantz AVR plugin
#
#     Author:   Dnpwwo, 2016 - 2017, Artemgy 2017, elgringo 2017
#
#   Mode3 ("Sources") needs to have '|' delimited names of sources that the Denon knows about.  
#   The Selector can be changed afterwards to any text and the plugin will still map to the actual Denon name.
#   
#   Adjust for marantz sr5009: removed pwer (controlled via zone), added tuner preset +/- buttons with stationname
#
"""
<plugin key="DenonMarantz" version="2.5.6" name="Denon / Marantz AVR Amplifier" author="dnpwwo/artemgy/elgringo" externallink="https://github.com/ericstaal/domoticz/blob/master/plugin/marantz">
  <description>
Denon & Marantz AVR plugin.<br/><br/>
&quot;Sources&quot; need to have '|' delimited names of sources that the Denon knows about from the technical manual.<br/>
The Sources Selector(s) can be changed after initial creation to any text and the plugin will still map to the actual Denon name.<br/><br/>
Devices will be created in the Devices Tab only and will need to be manually made active.
  </description>
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
    <param field="Mode6" label="Debug" width="75px">
      <options>
        <option label="True" value="Debug"/>
        <option label="False" value="Normal"  default="true" />
      </options>
    </param>
  </params>
</plugin>
"""
import Domoticz
import base64
import datetime

class BasePlugin:
  connection = None
  busyConnecting = False
  
  oustandingPings = 0
  #powerOn = False

  mainOn = False
  mainSource = 0
  mainVolume1 = 0
  stationName = ""
  
  ignoreMessages = "|SS|SV|SD|MS|PS|CV|SY|TP|"
  selectorMap = {}
  #pollingDict =  {"PW":"ZM?\r", "ZM":"SI?\r", "SI":"MV?\r", "MV":"MU?\r", "MU":"PW?\r" }
  #pollingDict =  {"ZM":"SI?\r", "SI":"MV?\r", "MV":"MU?\r", "MU":"ANNAME?\r", "TF":"ZM?\r"  }
  pollingDict =  {"ZM":"SI?\r", "SI":"MV?\r", "MV":"MU?\r", "MU":"ZM?\r" }
  lastMessage = "ZM"
  lastHeartbeat = datetime.datetime.now()

  SourceOptions = {}
  
  def checkConnection(self, checkonly = False):
    # Check connection and connect none
    isConnected = False
    
    if self.connection is None:
      self.connection = Domoticz.Connection(Name="Telnet", Transport="TCP/IP", Protocol="Line", Address=Parameters["Address"], Port=Parameters["Port"])
      
    if self.connection.Connected() == True:
      isConnected = True
    else:
      if self.busyConnecting:
        isConnected = False
      else:
        if not checkonly:
          self.oustandingPings = 0
          self.busyConnecting = True
          self.connection.Connect() # if failed (??) set self.busyConnecting back to false, create new conenction (??)
        isConnected = False

    return isConnected
  
  def onStart(self):
    if Parameters["Mode6"] == "Debug":
      Domoticz.Debugging(1)

    self.SourceOptions = {'LevelActions': '|'*Parameters["Mode3"].count('|'),
               'LevelNames': Parameters["Mode3"],
               'LevelOffHidden': 'false',
               'SelectorStyle': '1'}
      
    if (len(Devices) == 0):
      Domoticz.Device(Name="Source",     Unit=2, TypeName="Selector Switch", Switchtype=18, Image=5, Options=self.SourceOptions).Create()
      Domoticz.Device(Name="Volume",     Unit=3, Type=244, Subtype=73, Switchtype=7, Image=8).Create()
      Domoticz.Device(Name="Tuner up",   Unit=4, TypeName="Switch").Create()
      Domoticz.Device(Name="Tuner down", Unit=5, TypeName="Switch").Create()
      Domoticz.Device(Name="Station",    Unit=6, Type=243, Subtype=19, Switchtype=0).Create()
    else:
      if (2 in Devices and (len(Devices[2].sValue) > 0)):
        self.mainSource = int(Devices[2].sValue)
        self.mainOn = (Devices[2].nValue != 0)
      if (3 in Devices and (len(Devices[3].sValue) > 0)):
        self.mainVolume1 = int(Devices[3].sValue) if (Devices[3].nValue != 0) else int(Devices[3].sValue)*-1
    
    #ICONS
    if ("DenonMarantzIncrease" not in Images): Domoticz.Image('DenonMarantzIncrease.zip').Create()
    if ("DenonMarantzDecrease" not in Images): Domoticz.Image('DenonMarantzDecrease.zip').Create()
    if ("DenonMarantzboombox" not in Images): Domoticz.Image('DenonMarantzboombox.zip').Create()
    
    
    if (4 in Devices):
      Devices[4].Update(nValue=Devices[4].nValue, sValue=str(Devices[4].sValue), Image=Images["DenonMarantzIncrease"].ID)
    if (5 in Devices):
      Devices[5].Update(nValue=Devices[5].nValue, sValue=str(Devices[5].sValue), Image=Images["DenonMarantzDecrease"].ID)
    if (6 in Devices):
      Devices[6].Update(nValue=Devices[5].nValue, sValue=str(Devices[6].sValue), Image=Images["DenonMarantzboombox"].ID)      
 
    
    DumpConfigToLog()
    dictValue=0
    for item in Parameters["Mode3"].split('|'):
      self.selectorMap[dictValue] = item
      dictValue = dictValue + 10
    
    #self.checkConnection()
    return

  def onConnect(self, Connection, Status, Description):
    self.busyConnecting = False
    if (Status == 0):
      Domoticz.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port)
      #self.connection.Send('PW?\r')
      #self.connection.Send('ZM?\r', Delay=1)
      self.connection.Send('ZM?\r')
    else:
      #self.powerOn = False
      Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)
      # destroy connection and create a new one
      self.connection = None
      self.SyncDevices()
    return

  def onMessage(self, Connection, Data, Status, Extra):
    self.oustandingPings = self.oustandingPings - 1
    strData = Data.decode("utf-8", "ignore")
    Domoticz.Debug("onMessage called with Data: '"+str(strData)+"'")
    
    strData = strData.strip()
    action = strData[0:2]
    detail = strData[2:]
    if (action in self.pollingDict): self.lastMessage = action

    
    #if (action == "PW"):    # Power Status
    #  if (detail == "STANDBY"):
    #    self.powerOn = False
    #  elif (detail == "ON"):
    #    self.powerOn = True
    #  else: Domoticz.Debug("Unknown: Action "+action+", Detail '"+detail+"' ignored.")
    #elif (action == "ZM"):    # Main Zone on/off
    if (action == "ZM"):    # Main Zone on/off
      if (detail == "ON"):
        self.mainOn = True
      elif (detail == "OFF"):
        self.mainOn = False
      else: Domoticz.Debug("Unknown: Action "+action+", Detail '"+detail+"' ignored.")
    elif (action == "SI"):    # Main Zone Source Input
      for key, value in self.selectorMap.items():
        if (detail == value):    
          self.mainSource = key
          #self.lastMessage = "MU" # force reloading channel name
    elif (action == "MV"):    # Master Volume
      if (detail.isdigit()):
        if (abs(self.mainVolume1) != int(detail[0:2])): self.mainVolume1 = int(detail[0:2])
      elif (detail[0:3] == "MAX"): Domoticz.Debug("Unknown: Action "+action+", Detail '"+detail+"' ignored.")
      else: Domoticz.Log("Unknown: Action "+action+", Detail '"+detail+"' ignored.")
    elif (action == "MU"):    # Overall Mute
      if (detail == "ON"):     self.mainVolume1 = abs(self.mainVolume1)*-1
      elif (detail == "OFF"):    self.mainVolume1 = abs(self.mainVolume1)
      else: Domoticz.Debug("Unknown: Action "+action+", Detail '"+detail+"' ignored.")
    elif (action == "TF"):
      self.stationName = detail[6:].strip()
      
    else:
      if (self.ignoreMessages.find(action) < 0):
        Domoticz.Debug("Unknown message '"+action+"' ignored.")
    self.SyncDevices()
    
    return

  def onCommand(self, Unit, Command, Level, Hue):
    Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    Command = Command.strip()
    action, sep, params = Command.partition(' ')
    action = action.capitalize()
    params = params.capitalize()
    delay = 0
    
    #if (self.powerOn == False):
    #  delay = int(Parameters["Mode2"])
    #else:
    #  # Amp will ignore commands if it is responding to a heartbeat so delay send
    lastHeartbeatDelta = (datetime.datetime.now()-self.lastHeartbeat).total_seconds()
    if (lastHeartbeatDelta < 0.5):
      delay = 1
      Domoticz.Log("Last heartbeat was "+str(lastHeartbeatDelta)+" seconds ago, delaying command send.")

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
        #self.lastMessage = "MU" # force reloading channel name
      elif (Unit == 5):   # Down
        self.connection.Send(Message='TPANDOWN\r', Delay=delay)
        #self.lastMessage = "MU" # force reloading channel name
    return

  def onDisconnect(self, Connection):
    Domoticz.Log("Denon device has disconnected.")
    # self.busyConnecting = False Should not be needed
    self.connection = None # reset connection
    return

  def onHeartbeat(self):
    if self.checkConnection(): # if false will initialize a new connection
      if (self.oustandingPings > 5):
        self.connection.Disconnect()
      else:
        self.lastHeartbeat = datetime.datetime.now()
        self.connection.Send(self.pollingDict[self.lastMessage])
        Domoticz.Debug("onHeartbeat: self.lastMessage "+self.lastMessage+", Sending '"+self.pollingDict[self.lastMessage][0:2]+"'.")
        self.oustandingPings = self.oustandingPings + 1
    return

  def SyncDevices(self):
    #if (self.powerOn == False):
    #  UpdateDevice(2, 0, "0")
    #  UpdateDevice(3, 0, str(abs(self.mainVolume1)))
    #else:
    UpdateDevice(2, self.mainSource if self.mainOn else 0, str(self.mainSource if self.mainOn else 0))
    if (self.mainVolume1 <= 0 or self.mainOn == False): UpdateDevice(3, 0, str(abs(self.mainVolume1)))
    else: UpdateDevice(3, 2, str(self.mainVolume1))
    
    UpdateDevice(6,0,self.stationName)

    return
    
global _plugin
_plugin = BasePlugin()

def onStart():
  global _plugin
  _plugin.onStart()

def onConnect(Connection, Status, Description):
  global _plugin
  _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data, Status, Extra):
  global _plugin
  _plugin.onMessage(Connection, Data, Status, Extra)

def onCommand(Unit, Command, Level, Hue):
  global _plugin
  _plugin.onCommand(Unit, Command, Level, Hue)

def onDisconnect(Connection):
  global _plugin
  _plugin.onDisconnect(Connection)

def onHeartbeat():
  global _plugin
  _plugin.onHeartbeat()

def UpdateDevice(Unit, nValue, sValue):
  # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
  if (Unit in Devices):
    if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
      Devices[Unit].Update(nValue, str(sValue))
      Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
  return

def DumpConfigToLog():
  for x in Parameters:
    if Parameters[x] != "":
      Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
  Domoticz.Debug("Device count: " + str(len(Devices)))
  for x in Devices:
    Domoticz.Debug("Device:       " + str(x) + " - " + str(Devices[x]))
    Domoticz.Debug("Internal ID:   '" + str(Devices[x].ID) + "'")
    Domoticz.Debug("External ID:   '" + str(Devices[x].DeviceID) + "'")
    Domoticz.Debug("Device Name:   '" + Devices[x].Name + "'")
    Domoticz.Debug("Device nValue:  " + str(Devices[x].nValue))
    Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
    Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
  return

def stringToBase64(s):
  return base64.b64encode(s.encode('utf-8')).decode("utf-8")

def base64ToString(b):
  return base64.b64decode(b).decode('utf-8')