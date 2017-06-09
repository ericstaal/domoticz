# HOSOLA
#
# Author: elgringo

"""
<plugin key="Hosola_Omnik" name="Hosola / Omnik solar inverter" author="elgringo" version="1.0.1" externallink="https://github.com/ericstaal/domoticz/tree/master/plugin/hosola/">
  <description>
Connects to Hosola or Omnik solar inverter, auto detect 1,2 or 3 phases used. 
  </description>
  <params>
    <param field="Address" label="IP Address"                    width="200px" required="true" default="127.0.0.1"/>
    <param field="Port"    label="Port"                          width="30px"  required="true" default="8899"/>
    <param field="Mode1"   label="Serial number (intefers only)" width="150px" required="true" />
    <param field="Mode2"   label="Disconnect after (tries)"      width="50px"  required="true">
      <options>
        <option label="0" value="0"/>
        <option label="1" value="1"/>
        <option label="2" value="2"/>
        <option label="3" value="3" default="true" />
        <option label="4" value="4"/>
        <option label="5" value="5"/>
        <option label="6" value="6"/>
      </options>
    </param>
    <param field="Mode3"   label="Heartbeat interval"            width="50px"  required="true">
      <options>
        <option label="5" value="5"/>
        <option label="10" value="10"/>
        <option label="15" value="15" default="true"/>
        <option label="20" value="20" />
        <option label="25" value="25"/>
        <option label="30" value="30"/>
      </options>
    </param>
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

class BasePlugin:
    
  connection = None
  totalEnergy = 0.0             # inital values
  inverterId = None
  readBytes = bytearray()
  
  busyConnecting = False
  
  oustandingMessages = 0
  
  def __init__(self):
    return

  def createInverterId(self):
    self.inverterId = None
    try:
      intserial = int(Parameters["Mode1"])
      cs = 115;  # offset, not found any explanation sofar for this offset

      # convert to byte array,
      bytesserial = intserial.to_bytes(((intserial.bit_length() + 7) // 8), byteorder='little')

      # create checksum
      for idx in range(0,len(bytesserial), 1):
        cs = cs + 2 * bytesserial[idx]

      # build indentifier
      self.inverterId = bytearray()
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

      Domoticz.Debug("Created indentifier: "+ createByteString(self.inverterId))
      
    except:
      Domoticz.Error (Parameters["Mode1"]+" is not a valid serial number!")
  
  def onStart(self):
    if Parameters["Mode6"] == "Debug":
      Domoticz.Debugging(1)
    
    Domoticz.Heartbeat(int(Parameters["Mode3"])) 
    self.createInverterId()
    
    # add temperature if not exists
    if (1 not in Devices):
      Domoticz.Device(Name="Temperature", Unit=1, Type=80, Subtype=5, Switchtype=0, Image=0).Create()
      
    # get total energy
    if (4 in Devices):
      self.totalEnergy = GetTotalEnergy(Devices[4].sValue)
    elif (7 in Devices):
      self.totalEnergy = GetTotalEnergy(Devices[7].sValue)
    elif  (10 in Devices):
      self.totalEnergy = GetTotalEnergy(Devices[10].sValue)
    Domoticz.Log("Current total energy: "+str(self.totalEnergy))
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

  def onStop(self):
    Domoticz.Log("onStop called")
    return

  def checkConnection(self, checkonly = False):
    # Check connection and connect none
    isConnected = False
    if self.connection is None:
      self.connection = Domoticz.Connection(Name="Hosola_OmnikBinair", Transport="TCP/IP", Protocol="None", Address=Parameters["Address"], Port=Parameters["Port"])
    
    if self.connection.Connected() == True:
      isConnected = True
    else:
      if self.busyConnecting:
        isConnected = False
      else:
        if not checkonly:
          self.oustandingMessages = 0
          self.busyConnecting = True
          self.connection.Connect() # if failed (??) set self.busyConnecting back to false, create new conenction (??)
        isConnected = False
    return isConnected
      
  def onConnect(self, Connection, Status, Description):
    self.busyConnecting = False
    if (Status == 0):
      Domoticz.Log("Connected successfully to: "+Connection.Address+":"+Connection.Port)
      self.sendNullValues()
    else:
      Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Connection.Address+":"+Connection.Port+" with error: "+Description)
      # destroy connection and create a new one
      self.connection = None
    return

  def onMessage(self, Connection, Data, Status, Extra):
    self.readBytes.extend(Data) 
    
    if len(self.readBytes) > 155:
      if (self.readBytes[0] == 0x68 and self.readBytes[2] == 0x41): # what is the inital series?
        self.oustandingMessages = self.oustandingMessages - 1
    
      if (self.readBytes[154]==0x4F and self.readBytes[155] == 0x4B): 
        vac = []
        vdc = []
        pac = []
        vac.append(GetValue(self.readBytes,51,2,10)) # volt
        vac.append(GetValue(self.readBytes,53,2,10))
        vac.append(GetValue(self.readBytes,55,2,10))
        vdc.append(GetValue(self.readBytes,33,2,10)) # Volt
        vdc.append(GetValue(self.readBytes,35,2,10))
        vdc.append(GetValue(self.readBytes,37,2,10))
        pac.append(GetValue(self.readBytes,59,2,1)) # watt
        pac.append(GetValue(self.readBytes,63,2,1))
        pac.append(GetValue(self.readBytes,67,2,1))
        
        temperature = GetValue(self.readBytes,31,2,10) #Celcius
        self.totalEnergy = GetValue(self.readBytes,71,4,0.01) # wh 0.01
        
        self.ustandingMessages = self.oustandingMessages - 1
        
        Domoticz.Debug("VAC: "+str(vac)+" VDC: "+str(vdc)+" PAC: "+str(pac)+" Total: "+str(self.totalEnergy)+ " Temperature: "+str(temperature))
        
        # add / update devices if needed
        for i in range(3):
          if (vac[i] > 0 or vdc[i] > 0 or pac[i] > 0):
            unt = 2+i*3
            if (unt not in Devices):
              Domoticz.Device(Name=("VAC "+str(i+1)), Unit=unt, Type=243, Subtype=8, Switchtype=0, Image=0).Create()
            UpdateDevice(unt, vac[i])
            
            unt = unt + 1
            if (unt not in Devices):
              Domoticz.Device(Name=("VDC "+str(i+1)), Unit=unt, Type=243, Subtype=8, Switchtype=0, Image=0).Create()
            UpdateDevice(unt, vdc[i])
              
            unt = unt + 1
            if (unt not in Devices):
              Domoticz.Device(Name=("Power "+str(i+1)), Unit=unt, Type=243, Subtype=29, Switchtype=4, Image=0).Create()
            UpdateDevice(unt, pac[i], self.totalEnergy)
        
        UpdateDevice(1, temperature)
        self.readBytes = bytearray()
        
      else:
        Domoticz.Error("Incorrect messsage: "+createByteString(self.readBytes))
        self.readBytes = bytearray()
      

  def onCommand(self, Unit, Command, Level, Hue):
    Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))
    return

  def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
    Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)
    return

  def onDisconnect(self, Connection):
    # self.busyConnecting = False Should not be needed
    Domoticz.Log("Disconnected from: "+Connection.Address+":"+Connection.Port)
    self.connection = None # reset connection
    return
    
  def sendNullValues(self):
    UpdateDevice(1, 0)
    UpdateDevice(2, 0)
    UpdateDevice(3, 0)
    UpdateDevice(4, 0, self.totalEnergy)
    UpdateDevice(5, 0)
    UpdateDevice(6, 0)
    UpdateDevice(7, 0, self.totalEnergy)
    UpdateDevice(8, 0)
    UpdateDevice(9, 0)
    UpdateDevice(10, 0, self.totalEnergy)
    
  def onHeartbeat(self):
    # send identifier
    if self.checkConnection(): # checks if connect if not retry
      if self.oustandingMessages > int(Parameters["Mode2"]):
        self.sendNullValues()
        self.connection.Disconnect()
      else:
        if self.inverterId is not None: # Only send message if inverter id is known
          self.oustandingMessages = self.oustandingMessages + 1
          if (len(self.readBytes) > 0):
            Domoticz.Error("Erased (send new request): "+createByteString(self.readBytes))
            self.readBytes = bytearray()  # clear all bytes read
          self.connection.Send(self.inverterId)


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

def onMessage(Connection, Data, Status, Extra):
  global _plugin
  _plugin.onMessage(Connection, Data, Status, Extra)

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
  
def UpdateDevice(Unit, sValue1, sValue2 = None):
  if (Unit in Devices):
    if sValue2 is None:
      sValue = str(sValue1)
    else:
      sValue = str(sValue1)+";"+str(sValue2)
    if (Devices[Unit].sValue != sValue):
      Devices[Unit].Update(0, sValue)
      Domoticz.Debug("Update "+Devices[Unit].Name + " from: "+ Devices[Unit].sValue+" to: "+sValue)
  return  
  
def GetTotalEnergy(sValue):
  returnValue = 0.0
  try:
    returnValue = float(str(sValue).split(';')[1])
  except:
    Domoticz.Debug("could not convert "+str(sValue))
    pass
  return returnValue
  
  
def createByteString(bytes):
  # create string from bytes
  returnvalue = "[ " 
  for b in bytes:
    returnvalue += str(hex(b))+" "
  
  returnvalue+= "]("+str(len(bytes))+")"
  return returnvalue
     
def GetValue(bytes, start, length, divider):
  returnValue = 0.0
  try:
    value = int.from_bytes(bytes[start:(start+length)], byteorder='big')
    if value == 0:
      returnValue = 0
    elif divider != 1:
      returnValue = value / divider
    else:
      returnValue = value
    #Domoticz.Debug("Start: "+str(start)+" length: "+str(length)+" bytes: "+ createByteString(bytes[start:(start+length)]) +" val: "+str(returnValue)+"("+str(value)+")")
  except Exception as e:
    Domoticz.Error("Could get value at idx: "+str(start)+" length: "+str(length)+" Error: "+ str(e)+" from: "+createByteString(bytes) )
  return returnValue