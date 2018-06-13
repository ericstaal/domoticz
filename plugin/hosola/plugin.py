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
# 1.0.4   13-06-2018  CLean up code

"""
<plugin key="Hosola_Omnik" name="Hosola / Omnik solar inverter" author="elgringo" version="1.0.4" externallink="https://github.com/ericstaal/domoticz/blob/master/">
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
from html import escape

# additional imports

class BasePlugin:
  
  connection = None           # Network connection
  outstandingMessages = 0     # Open messages without reply
  maxOutstandingMessages = 5  # lose conenction after
  logLevel = 0                # logLevel
  
  totalEnergy = 0.0           # inital values
  inverterId = bytearray()
  readBytes = bytearray()
  
  errorReported = False
  
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
      self.LogError("CheckConnection error, try to reset")
    
    return isConnected
    
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.LogError("Debuglevel '"+Parameters["Mode6"]+"' is not an integer")
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    self.LogMessage("onStart called", 9)
    
    #self.connection = Domoticz.Connection(Name="Hosola_OmnikBinair", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
      
    maxOutstandingMessages = int(Parameters["Mode2"])
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
    self.LogMessage("Current total energy: "+str(self.totalEnergy), 1)
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
    self.LogMessage("onStop called", 9)
    
    return

  def onConnect(self, Connection, Status, Description):
    if (Status == 0):
      self.LogMessage("Connected successfully to: "+Connection.Address+":"+Connection.Port, 2)
      self.sendNullValues()
      if self.errorReported:
        self.errorReported = False
    else:
      if not self.errorReported:
        self.LogMessage("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description, 2)
        self.errorReported = True
    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage Data")
    
    self.readBytes.extend(Data) 
    
    if len(self.readBytes) > 155:
      if (self.readBytes[0] == 0x68 and self.readBytes[2] == 0x41 and self.readBytes[154 ]== 0x4F and self.readBytes[155] == 0x4B): 
        self.outstandingMessages = self.outstandingMessages - 1
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
        
        self.LogMessage("VAC: "+str(vac)+" VDC: "+str(vdc)+" PAC: "+str(pac)+" Total: "+str(self.totalEnergy)+ " Temperature: "+str(temperature), 5)
        
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
        self.readBytes.clear()
        
      else:
        self.DumpVariable(self.readBytes, "Incorrect messsage", Level = -1)
        self.readBytes.clear()
    return

  def onCommand(self, Unit, Command, Level, Hue):
    self.LogMessage("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level)+", Hue: " + str(Hue), 8)
    
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    self.LogMessage("onNotification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile, 8)
    
    return

  def onDisconnect(self, Connection):
    self.LogMessage("onDisconnect "+Connection.Address+":"+Connection.Port, 7)

    return

  def onHeartbeat(self):
    self.LogMessage("onHeartbeat called, open messages: " + str(self.outstandingMessages), 8)
    
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
      self.LogError("OnHeartbeat Error: "+ str(e) )
    
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
      self.LogError(Parameters["Mode1"]+" is not a valid serial number!")
  
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
      self.LogError("could not convert "+str(sValue))
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
          txt = escape(Item.decode("utf-8", "ignore"))
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

