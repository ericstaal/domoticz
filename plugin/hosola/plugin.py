# HOSOLA
#
# Description: HOSOLA / OMNIK solar inverter
#
# Author: elgringo
#
# History:
# 1.0.0   01-07-2017  Initial version
# 1.0.1   31-07-2017  Updated with new API
# 1.0.2   22-05-2018  Onheartbeat debug level to 8
# 1.0.3   12-06-2018  Connection bugfix when set to nonen, outstanding messages cleared
# 1.0.4   13-06-2018  Clean up code
# 1.0.5   20-06-2018  Solved issue with max open messages
# 1.0.6   03-07-2018  Fixed logging, robust for invalid messages
# 1.0.7   08-07-2018  Report start and end of incorrect message
# 1.0.8   06-08-2018  Update logging

"""
<plugin key="Hosola_Omnik" name="Hosola / Omnik solar inverter" author="elgringo" version="1.0.8" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
    <param field="Port" label="Port" width="30px"  required="true" default="8899"/>
    <param field="Mode1" label="Serial number (integers only)" width="150px" required="true" />
    <param field="Mode2" label="Disconnect after (tries)"width="50px"  required="true">
      <options>
        <option label="0" value="0" default="true"/>
        <option label="1" value="1"/>
        <option label="2" value="2"/>
        <option label="3" value="3"/>
        <option label="4" value="4"/>
        <option label="5" value="5"/>
        <option label="6" value="6"/>
      </options>
    </param>
    <param field="Mode3" label="Heartbeat interval" width="50px" required="true">
      <options>
        <option label="5" value="5"/>
        <option label="10" value="10"/>
        <option label="15" value="15" default="true"/>
        <option label="20" value="20" />
        <option label="25" value="25"/>
        <option label="30" value="30"/>
        <option label="40" value="40"/>
        <option label="50" value="50"/>
        <option label="60" value="60"/>
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
import datetime
import collections 
import base64
from html import escape

# additional imports

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 0  # lose connection after
  logLevel = 0                # logLevel
  
  totalEnergy = 0.0           # inital values
  inverterId = bytearray()
  readBytes = bytearray()
  
  errorReported = False
  errorIncorrectStartReported = False
  nofIncorrectMessages = 0
  lastIncorrectStart = datetime.datetime.now()
  
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
      else:
        self.outstandingMessages = 0
        self.connection = Domoticz.Connection(Name="Hosola_OmnikBinair", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
        self.connection.Connect()
    except:
      self.connection = None
      self.Log("CheckConnection error, try to reset",1,3)
    
    return isConnected
    
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.Log("Debuglevel '"+Parameters["Mode6"]+"' is not an integer",1,3)
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    self.Log("onStart called, heartbeat interval " +str(Parameters["Mode3"])+" seconds", 4, 1)  
    
    self.maxOutstandingMessages = int(Parameters["Mode2"])
    Domoticz.Heartbeat(int(Parameters["Mode3"])) 
    self.createInverterId()
    
    # add temperature if not exists
    if (1 not in Devices):
      Domoticz.Device(Name="Temperature", Unit=1, Type=80, Subtype=5, Switchtype=0, Image=0).Create()
      
    # get total energy
    if (4 in Devices):
      self.totalEnergy = self.GetTotalEnergy(Devices[4].sValue)
    elif (7 in Devices):
      self.totalEnergy = self.GetTotalEnergy(Devices[7].sValue)
    elif  (10 in Devices):
      self.totalEnergy = self.GetTotalEnergy(Devices[10].sValue)
    self.Log("Current total energy: "+str(self.totalEnergy), 1, 2)
    # id 1= temp
    # id 2= VAC phase 1
    # id 3= VDC phase 1
    # id 4= Power phase 1
    # id 5= VAC phase 2
    # id 6= VDC phase 2
    # id 7= Power phase 2
    # id 8= VAC phase 3
    # id 9= VDC phase 3
    # id 10= Power phase 3
    
    #self.checkConnection()    
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    self.Log("onStop called", 9, 1)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port, 2, 2)
      self.sendNullValues()
      if self.errorReported:
        self.errorReported = False
    else:
      if not self.errorReported:
        self.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 2, 2)
        self.errorReported = True
    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage Data")
    
    self.readBytes.extend(Data) 
    if len(self.readBytes) > 3:
      if (self.readBytes[0] != 0x68 or self.readBytes[1] != 0x73 or self.readBytes[2] != 0x41):
        # incorrect message, purge it
        self.outstandingMessages = self.outstandingMessages - 1
        if not self.errorIncorrectStartReported:
          self.DumpVariable(self.readBytes, "Incorrect start message purge it", Level = 4)
          
          self.nofIncorrectMessages = self.nofIncorrectMessages +1
          self.lastIncorrectStart = datetime.datetime.now()
          
          self.Log("Incorrect message received. Occurrences: "+ str(self.nofIncorrectMessages), 3, 3)
          self.errorIncorrectStartReported = True
        self.readBytes.clear()
    
    if len(self.readBytes) > 155:
      self.outstandingMessages = self.outstandingMessages - 1
      if (self.readBytes[154 ]== 0x4F and self.readBytes[155] == 0x4B): 
        if self.errorIncorrectStartReported:
          self.errorIncorrectStartReported = False
          endtime = datetime.datetime.now()
          self.Log("First correct message received, duration: "+ str(endtime-self.lastIncorrectStart), 3, 2)
          
        vac = []
        vdc = []
        pac = []
        vac.append(self.GetValue(self.readBytes,51,2,10)) # volt
        vac.append(self.GetValue(self.readBytes,53,2,10))
        vac.append(self.GetValue(self.readBytes,55,2,10))
        vdc.append(self.GetValue(self.readBytes,33,2,10)) # Volt
        vdc.append(self.GetValue(self.readBytes,35,2,10))
        vdc.append(self.GetValue(self.readBytes,37,2,10))
        pac.append(self.GetValue(self.readBytes,59,2,1)) # watt
        pac.append(self.GetValue(self.readBytes,63,2,1))
        pac.append(self.GetValue(self.readBytes,67,2,1))
        
        temperature = self.GetValue(self.readBytes,31,2,10) #Celcius
        self.totalEnergy = self.GetValue(self.readBytes,71,4,0.01) # wh 0.01
        
        #self.outstandingMessages = self.outstandingMessages - 1
        
        self.Log("VAC: "+str(vac)+" VDC: "+str(vdc)+" PAC: "+str(pac)+" Total: "+str(self.totalEnergy)+ " Temperature: "+str(temperature), 5, 2)
        
        # add / update devices if needed
        for i in range(3):
          if (vac[i] > 0 or vdc[i] > 0 or pac[i] > 0):
            unt = 2+i*3
            if (unt not in Devices):
              Domoticz.Device(Name=("VAC "+str(i+1)), Unit=unt, Type=243, Subtype=8, Switchtype=0, Image=0).Create()
            self.UpdateDevice(unt, 0, vac[i])
            
            unt = unt + 1
            if (unt not in Devices):
              Domoticz.Device(Name=("VDC "+str(i+1)), Unit=unt, Type=243, Subtype=8, Switchtype=0, Image=0).Create()
            self.UpdateDevice(unt, 0, vdc[i])
              
            unt = unt + 1
            if (unt not in Devices):
              Domoticz.Device(Name=("Power "+str(i+1)), Unit=unt, Type=243, Subtype=29, Switchtype=4, Image=0).Create()
            self.UpdateDevice(unt, 0, pac[i], self.totalEnergy)
        
        self.UpdateDevice(1, 0, temperature)
        self.DumpVariable(self.readBytes, "Correct messsage", Level = 8)
        self.readBytes.clear()        
        
      else:
        self.DumpVariable(self.readBytes, "Incorrect messsage", Level = 4)
        self.readBytes.clear()
    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 8, 1)
    
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.Log("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8, 1)
    
    return

  def onDisconnect(self, Connection):
    self.Log("onDisconnect "+Connection.Address+":"+Connection.Port, 7, 1)

    return

  def onHeartbeat(self):
    self.Log("onHeartbeat called, open messages: " + str(self.outstandingMessages), 7, 1)
    
    try:
      if self.checkConnection(): # checks if connect if not retry
        if self.outstandingMessages > self.maxOutstandingMessages:
          self.sendNullValues()
          self.connection.Disconnect()
        else:
          if len(self.inverterId) > 4: # Only send message if inverter id is known
            self.outstandingMessages = self.outstandingMessages + 1
            if self.outstandingMessages == 1:
              self.connection.Send(self.inverterId)
    except Exception as e:
      self.Log("OnHeartbeat Error: "+ str(e), 1, 3 )
    
    return

####################### Specific helper functions for plugin #######################    
  def createInverterId(self):
    self.inverterId.clear()
    try:
      intserial = int(Parameters["Mode1"])
      cs = 115;  # offset, not found any explanation sofar for this offset

      # convert to byte array,
      bytesserial = intserial.to_bytes(((intserial.bit_length() + 7) // 8), byteorder='little')

      # create checksum
      for idx in range(0,len(bytesserial), 1):
        cs = cs + 2 * bytesserial[idx]

      # build indentifier
      self.inverterId.append(0x68)
      self.inverterId.append(0x02)
      self.inverterId.append(0x40)
      self.inverterId.append(0x30)
      self.inverterId.extend(bytesserial)
      self.inverterId.extend(bytesserial)
      self.inverterId.append(0x01)
      self.inverterId.append(0x00)
      self.inverterId.append(cs & 0xFF)
      self.inverterId.append(0x16)  

      self.DumpVariable(self.inverterId, "Inverter ID")
      
    except:
      self.Log(Parameters["Mode1"]+" is not a valid serial number!", 1,3)
  
  def sendNullValues(self):
    # id 1= temp
    # id 2= VAC phase 1
    # id 3= VDC phase 1
    # id 4= Power phase 1
    # id 5= VAC phase 2
    # id 6= VDC phase 2
    # id 7= Power phase 2
    # id 8= VAC phase 3
    # id 9= VDC phase 3
    # id 10= Power phase 3
    #self.UpdateDevice(1, 0, 0)
    #self.UpdateDevice(2, 0, 0)
    self.UpdateDevice(3, 0, 0)
    self.UpdateDevice(4, 0, 0, self.totalEnergy)
    #self.UpdateDevice(5, 0, 0)
    self.UpdateDevice(6, 0, 0)
    self.UpdateDevice(7, 0, 0, self.totalEnergy)
    #self.UpdateDevice(8, 0, 0)
    self.UpdateDevice(9, 0, 0)
    self.UpdateDevice(10, 0, 0, self.totalEnergy)
    
    
  def GetTotalEnergy(self, sValue):
    returnValue = 0.0
    try:
      returnValue = float(str(sValue).split(';')[1])
    except:
      self.Log("could not convert "+str(sValue), 1,3)
      pass
    return returnValue
  
  def GetValue(self, bytes, start, length, divider):
    returnValue = 0.0
    try:
      value = int.from_bytes(bytes[start:(start+length)], byteorder='big')
      if value == 0:
        returnValue = 0
      elif divider != 1:
        returnValue = value / divider
      else:
        returnValue = value
        
      self.DumpVariable(bytes[start:(start+length)], "Start: "+str(start)+" length: "+str(length)+" val: "+str(returnValue)+"("+str(value)+") bytes", Level = 9)
    except Exception as e:
      self.DumpVariable(bytes, "Could get value at idx: "+str(start)+" length: "+str(length)+" Error: "+ str(e)+" from", Level = -1)
    
    return returnValue
  
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

