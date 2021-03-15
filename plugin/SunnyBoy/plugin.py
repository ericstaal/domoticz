# SunnyBoy
#
# Description: Sunnyboy modbus plugin
#
# Author: elgringod
#
# Prerequisites: sudo pip3 install -U pymodbus pymodbusTCP
# Modbus TCP server activated on Inverter
#
# History:
# 1.0.0   27-06-2020  Initial version

"""
<plugin key="SunnyBoy_Modbus" name="Sunnyboy inverter via Modbus" author="elgringo" version="1.0.0" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Address" label="IP Address" width="200px" required="true" default="127.0.0.1"/>
    <param field="Port" label="Port" width="30px" required="true" default="502"/>
    <param field="Mode1" label="Unit ID" width="30px" required="true" default="3"/>

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
    
    <param field="Mode6" label="Debug level" width="200px">
      <options>
        <option label="0 (No logging)" value="0"/>
        <option label="1" value="1"/> 
        <option label="2" value="2"/>
        <option label="3" value="3"/>
        <option label="4" value="4" default="true"/>
        <option label="5" value="5"/>
        <option label="6" value="6"/>
        <option label="7" value="7"/>
        <option label="8 (with debug registers)" value="8"/>
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
from pymodbus.client.sync import ModbusTcpClient
#from pymodbus.transaction import ModbusRtuFramer  
import struct

class BasePlugin:
  
  connection = None           # ModBusConnection

  logLevel = 0                # logLevel
  totalEnergy = 0.0           # inital values
  
  unitid = 0
    
  def checkConnection(self, checkonly = False):
    # Check connection and connect none
    isConnected = False
    try:
      if (not self.connection is None):
        if (not self.connection.is_socket_open()):
          if (not checkonly):
            self.connection.connect()
      else:
        self.connection = ModbusTcpClient(host=Parameters["Address"], port=int(Parameters["Port"]))
        self.connection.connect()
        
      isConnected = self.connection.is_socket_open()
    except:
      self.connection = None
      self.Log("CheckConnection error, try to reset",1,3)
    
    return isConnected
    
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.Log("Debuglevel '"+Parameters["Mode6"]+"' is not an integer",1,3)
      
    try:
      self.unitid = int(Parameters["Mode1"])
    except:
      self.unitid = 1
      self.Log("Unit ID '"+Parameters["Mode1"]+"' is not an integer, using 1",1,2)
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    self.Log("onStart called, heartbeat interval " +str(Parameters["Mode3"])+" seconds", 4, 1)  
    
    Domoticz.Heartbeat(int(Parameters["Mode3"])) 
    
    # create devices if needed
    if (1 not in Devices):
      Domoticz.Device(Name="Temperature", Unit=1, Type=80, Subtype=5, Switchtype=0, Image=0).Create()
    if (3 in Devices): 
      self.UpdateDevice(3,0,"Off")
    else:
      Domoticz.Device(Name="Status", Unit=3, Type=243, Subtype=19, Switchtype=0).Create()
    if (4 in Devices):
      self.totalEnergy = self.GetTotalEnergy(Devices[4].sValue)
    else:
      Domoticz.Device(Name="Power", Unit=4, Type=243, Subtype=29, Switchtype=4, Image=0).Create()
    
    self.Log("Current total energy: "+str(self.totalEnergy), 1, 2)
    # id 1= temperature
    # id 3= Status (system status) + temp deriation ??
    # id 4= Power
     
    self.DumpConfigToLog()
    return

  def onStop(self):
    if (not self.connection is None):
      self.connection.close()
      self.connection = None
      self.Log("onStop called, closed connection", 3, 1)
    else:
      self.Log("onStop called,", 9, 1)
    
    return

  def onConnect(self, Connection, Status, Description):
    return

  def onMessage(self, Connection, Data):
    self.DumpVariable(Data, "OnMessage Data")
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
    self.Log("onHeartbeat called", 8, 1)
    
    try:
      if self.checkConnection(): # checks if connect if not retry
        # status
        status = "Unknown"
        deriation = ""
        
        # Temp deriation
        result = self.readAddress(30219, "U32")
        if result[0]:
          if result[1] == 557:
            deriation = ", Temperature derating"
          elif result[1] == 1704:
            deriation = ", WMAX derating"
          elif result[1] == 1705:
            deriation = ", Frequency derating"
          elif result[1] == 1706:
            deriation = ", Current limitation"
        else:
          # read of register faield, probably since there is no sun :)
          self.sendNullValues()
          return
        
        # status
        result = self.readAddress(30201, "U32")
        if result[0]:
          if result[1] == 35:
            status = "Error"
          elif result[1] == 303:
            status = "Off"
          elif result[1] == 307:
            status = "OK"
          elif result[1] == 455:
            status = "Warning"
          else:
            status = "Unknown(%d)" % result[1]

        self.UpdateDevice(3, 0, status + deriation)
       

        # current power
        currentpower = 0 
        result = self.readAddress(30775, "U32")
        if result[0]:
          currentpower = result[1]
                  
        #total power
        result = self.readAddress(30529, "U32")
        if result[0]:
          self.totalEnergy = result[1]
        
        self.UpdateDevice(4, 0, currentpower, self.totalEnergy)
        
        # temperature
        result = self.readAddress(30953, "S32")
        if result[0]:
          self.UpdateDevice(1, 0, result[1]/10 )
          
        # debug
        if (self.logLevel >= 8):
          self.readAddress(30211, "U32") # user action
          
      else:
        self.sendNullValues()
        self.connection.close()
        self.connection = None

    except Exception as e:
      self.Log("OnHeartbeat Error: "+ str(e), 1, 3 )
      
    return

####################### Specific helper functions for plugin #######################    
  def readAddress(self, smaadr, datatype):
    res = True
    resvalue = 0

    modbusresult = self.connection.read_holding_registers(address = smaadr, count = 2, unit=self.unitid)
    
    if modbusresult.isError():
      res = False
      self.Log("Failed to read address: "+ str(smaadr), 1, 2 ) #probably connection lost
      
      self.sendNullValues()
      self.connection.close()
      self.connection = None
    else:
      
      w1 = struct.pack('H', modbusresult.registers[0]) # Assuming register values are unsigned short's
      w2 = struct.pack('H', modbusresult.registers[1]) # Assuming register values are unsigned short's
      
      if datatype == 'S32':
        resvalue = struct.unpack('i', w2 + w1)[0]
        if resvalue >= 2147483647 or resvalue <= -2147483647: 
          res = False
      elif datatype== 'U32':
        resvalue = struct.unpack('I', w2 + w1)[0]
        if resvalue == 16777213:
          res = False        
      else:
        self.Log("Unknown datatype: "+ str(datatype), 1, 3 )
        res = False
      
    self.Log("Read address:"+str(smaadr)+", value: "+str(resvalue)+" (hex: "+hex(resvalue)+") result: "+str(res), 6, 2 )
    
    return res, resvalue
    
    
  def sendNullValues(self):
    # id 1= temp
    # id 3= Status (system stauts + temp deriation ??
    # id 4= Power
    
    self.UpdateDevice(3, 0, "Off")
    self.UpdateDevice(4, 0, 0, self.totalEnergy)
    
    
  def GetTotalEnergy(self, sValue):
    returnValue = 0.0
    try:
      returnValue = float(str(sValue).split(';')[1])
    except:
      self.Log("could not convert "+str(sValue), 1,3)
      pass
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

