# Raspberry Pi Disk Usage
#
# Description: Reports temperature and free disk space
#
# Author: elgringo
#
# History:
# 1.0.0   01-07-2017  Initial version
# 1.0.1   31-07-2017  Updated with new API
# 1.0.2   14-04-2018  Only update when size > 0
# 1.0.3   06-08-2018  Update logging
# 1.1.0   27-08-2018  Added PWM fan control
# 1.1.1   02-09-2018  Repaired fan control

"""
<plugin key="RaspberryInfo" name="System Status" author="elgringo" version="1.1.1" externallink="https://github.com/ericstaal/domoticz/blob/master/">
  <params>
    <param field="Mode1" label="Size" width="50px" required="true">
      <options>
        <option label="Kb" value="Kb" />
        <option label="Mb" value="Mb" />
        <option label="Gb" value="Gb" default="true"/>
      </options>
    </param>
    <param field="Mode2" label="Heartbeat interval" width="50px" required="true">
      <options>
        <option label="20" value="10" />
        <option label="20" value="20" />
        <option label="30" value="30" />
        <option label="60" value="60" default="true"/>
      </options>
    </param>
    <param field="Port" label="Fan PWM pin (BCM)" width="150px" required="true">
      <options>
        <option label="Not connected" value="-1" default="true"/>
        <option label="0" value="0"/>
        <option label="1" value="1"/>
        <option label="2" value="2"/>
        <option label="3" value="3"/>
        <option label="4" value="4"/>
        <option label="5" value="5"/>
        <option label="6" value="6"/>
        <option label="7" value="7"/>
        <option label="8" value="8"/>
        <option label="9" value="9"/>
        <option label="10" value="10"/>
        <option label="11" value="11"/>
        <option label="12 (hardware PWM)" value="12"/>
        <option label="13 (hardware PWM)" value="13"/>
        <option label="14" value="14"/>
        <option label="15" value="15"/>
        <option label="16" value="16"/>
        <option label="17" value="17"/>
        <option label="18 (hardware PWM)" value="18"/>
        <option label="19 (hardware PWM)" value="19"/>
        <option label="20" value="20"/>
        <option label="21" value="21"/>
        <option label="22" value="22"/>
        <option label="23" value="23"/>
        <option label="24" value="24"/>
        <option label="25" value="25"/>
        <option label="26" value="26"/>
        <option label="27" value="27"/>
      </options>
    </param>
    <param field="Address" label="Temperature fan maximal speed" width="50px" required="true" default="45"/>
    <param field="Mode4" label="Temperature fan minimal speed" width="50px" required="true" default="30"/>
    <param field="Mode5" label="Minimal PWM step" width="50px" required="true">
      <options>
        <option label="1" value="1" default="true"/>
        <option label="2" value="2"/>
        <option label="5" value="5"/>
        <option label="10" value="10"/>
        <option label="20" value="20"/>
        <option label="50" value="50"/>
        <option label="100" value="100" />
        <option label="150" value="150"/>
        <option label="200" value="200"/>
        <option label="250" value="250"/>
      </options>
    </param>
    <param field="Mode3" label="Minimal fan speed [0-1024]" width="50px" required="true" default="800" />
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
import os
from subprocess import Popen, PIPE
import shlex

class BasePlugin:
  logLevel = 0                # logLevel
  
  temperature = -1
  actualpwm = -1
  
  maxtemperature = 45
  mintemperature = 30
  port = -1
  pwmstep = 10
  minpwm = 100
  
  initialized = False
 
  def onStart(self):
    try:
      self.logLevel = int(Parameters["Mode6"])
    except:
      self.Log("Debuglevel '"+Parameters["Mode6"]+"' is not an integer", 1, 3)
    
    try:
      self.maxtemperature = int(Parameters["Address"])
    except:
      self.Log("Temperature fan maximal speed '"+Parameters["Address"]+"' is not an integer", 1, 3)
    
    try:
      self.mintemperature = int(Parameters["Mode4"])      
    except:
      self.Log("Temperature fan minimal speed '"+Parameters["Mode4"]+"' is not an integer", 1, 3)  
   
    try:
      self.pwmstep = int(Parameters["Mode5"])
    except:
      self.Log("Minimal PWM step '"+Parameters["Mode5"]+"' is not an integer", 1, 3)

    try:
      self.minpwm = int(Parameters["Mode3"])
      if self.minpwm  > 1024 or self.minpwm  < 0:
        self.Log("Minimal fan speed must be between 0 and 1024 and is "+str(self.minpwm)+", set to 100", 1, 3)   
        self.minpwm = 100;
    except:
      self.Log("Minimal fan speed '"+Parameters["Mode3"]+"' is not an integer", 1, 3)    

    try:
      self.port = int(Parameters["Port"])
    except:
      self.Log("Port '"+Parameters["Port"]+"' is not an integer", 1, 3)      
      
    if self.mintemperature > self.maxtemperature:
      self.Log("Minimal temp is larger ("+str(self.mintemperature)+") than maximal temperature ("+str(self.maxtemperature)+"), temperatures swapped",1, 2)  
      tmp = self.mintemperature
      self.mintemperature = self.maxtemperature
      self.maxtemperature = tmp
      
    if self.logLevel == 10:
      Domoticz.Debugging(1)
    self.Log("onStart called", 9, 1)
    
    Domoticz.Heartbeat(int(Parameters["Mode2"]))
      
    if (len(Devices) == 0):
      Domoticz.Device(Name="Free space", Unit=1, TypeName="Custom", Image=3, Options={"Custom": ("1;" + Parameters["Mode1"])}).Create()
      Domoticz.Device(Name="Temperature", Unit=2, Type=80, Subtype=5, Switchtype=0, Image=0).Create()
    elif 1 in Devices:
      Devices[1].Update(0, "0", Options={"Custom": ("1;" + Parameters["Mode1"])})
      
    # setup GPIO
    if (self.port >= 0):

        
      cmd = 'sudo gpio -g mode '+str(self.port)+' pwm'
      exitcode, out, err = self.ExecuteCommand(cmd)
      self.Log("Initalized fan with '"+cmd+"'", 6, 1)
      self.Log("Fan speed ["+str(self.minpwm)+",1024] in "+str(self.pwmstep)+" step(s) between ["+str(self.mintemperature)+","+str(self.maxtemperature)+"]. Starting fan at max speed to make it rotate",1, 2)  
      self.setPWM(1024, True)
              
    self.DumpConfigToLog()
    
    return

  def onStop(self):
    if self.port >= 0:
    
      cmd = 'sudo gpio -g mode '+str(self.port)+' in'
      exitcode, out, err = self.ExecuteCommand(cmd)
      self.Log("Stopped: Executed command '"+cmd+"', result:"+str(exitcode), 6, 1)
    else:
      self.Log("Stopped", 9, 1)
    return

  def onConnect(self, Connection, Status, Description):
    self.Log("onConnect "+Connection.Address+":"+Connection.Port+" Status: "+ str(Status)+", Description:"+str(Description), 7, 1)

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
    self.Log("onHeartbeat called", 9, 1)
    try:
      # size
      proces = os.popen("df -k | grep -vE '^Filesystem|tmpfs|cdrom' | awk '{ print $6 \" \" $4 }'")
      data = proces.read()
      proces.close()
      
      # / 1.5g
      # /boot ...
      for line in data.split("\n"):
        koloms = line.split(' ')
        if koloms[0] == '/':
          size = float(koloms[1])
          
          if (size > 0):
            
            if Parameters["Mode1"] == "Gb":
              size = size / 1048576
            elif Parameters["Mode1"] == "Mb":
              size = size / 1024
            
            self.UpdateDevice(1, 0, round(size,1))
          break 
      
      
      # temperature
      proces = os.popen("cat /sys/class/thermal/thermal_zone0/temp")
      data = proces.read()   
      proces.close()
      self.temperature = round(int(data) / 1000,1)
      
      self.UpdateDevice(2, 0, self.temperature )
      
      self.updatePWM()
        
    except Exception as e:
      self.Log("OnHeartbeat Error: "+ str(e),1,3)
      
    return
    
  
  
####################### Specific helper functions for plugin #######################  
  def setPWM(self, pwmvalue, force=False):
    if pwmvalue > 1024:
      pwmvalue = 1024
    elif pwmvalue < self.minpwm:
      pwmvalue = self.minpwm
     
    # whole integers only
    pwmvalue = int(round(pwmvalue))
    
    if self.actualpwm != pwmvalue and self.port >=0:
      if (self.actualpwm + self.pwmstep) <= pwmvalue or (self.actualpwm - self.pwmstep) >= pwmvalue or force:
        # must update 
        self.Log("Update PWM from "+str(self.actualpwm)+"/1024 to "+str(pwmvalue)+"/1024. Current temperature "+str(self.temperature), 4, 2)
        self.actualpwm = pwmvalue
        
        cmd = 'sudo gpio -g pwm '+str(self.port)+' '+str(self.actualpwm)
        exitcode, out, err = self.ExecuteCommand(cmd)
        self.Log("Executed command '"+cmd+"'", 7, 1)
   
    return
  
  def updatePWM(self):
    # calculates new PWM value based on temperature
    
    if (self.temperature <= self.mintemperature):
      self.setPWM(self.minpwm, True)
    elif (self.temperature >= self.maxtemperature):
      self.setPWM(1024, True)
    else:
      deltaT = self.maxtemperature - self.mintemperature;
      deltaPWM = 1024-self.minpwm
      
      pwm = (deltaPWM) * ((self.temperature -self.mintemperature) / deltaT) + self.minpwm;
      self.setPWM(pwm)

    return
 
  def ExecuteCommand(self, cmd):
    
    args = shlex.split(cmd)

    proc = Popen(args, stdout=PIPE, stderr=PIPE)
    out, err = proc.communicate()
    out = out.decode("utf-8") 
    err = err.decode("utf-8") 
    
    exitcode = proc.returncode
    
    if (exitcode != 0):
      self.Log("Failed to execute '"+cmd+"': result:"+str(exitcode)+", out:'"+out+"', err:'"+err+"'", 3, 2)
   
    
    return exitcode, out, err

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

