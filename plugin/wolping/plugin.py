# WOL ping plugin. 
#
# Author: elgringo
# Tested only on raspberry PI
#

"""
<plugin key="WOLping" name="WOL/Pinger" author="elgringo" version="1.0.0" externallink="https://github.com/ericstaal/domoticz">
    <description>
WOL pinger<br/><br/>
Periodic check if a host is online via PING or ARPING. When enabled send a WOL packet (if defined).<br/>
Port - Port for WOL<br/>
Mac adres - MAC adress with or without separators<br/>
Interval - Time in seconds to check if the host is online<br/>
Max missed - Number of pings which may be missed before a host is offline<br/>
File location - Directory where files are temporty stored<br/>
Mode - Ping or Arping<br/>
    </description>
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
import re
import os
import socket
import struct
import subprocess

class BasePlugin:
    
    regexMac = re.compile('^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
    regexOnline = re.compile('1 packets transmitted, 1 (packets |)received')
    regexIp = re.compile('^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
    ip = None
    mac = None
    tempFile = None
    allowMissed = 1
    missed = 0
    wolport = 7
    arping = True
    lastState = False
    
    def __init__(self):
      pass
      
   
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
        Domoticz.Error("'"+Parameters["Address"]+"' is not a valid IP adress." )
      
      self.arping = (Parameters["Mode5"] == "arping")
      self.tempFile = Parameters["Mode4"] + "ping_"+Parameters["Address"]
      Domoticz.Log ( "Temp file: " + self.tempFile)
      try:
        self.wolport = int(Parameters["Port"])
      except Exception as e:
        Domoticz.Log("Port is not a number: "+ Parameters["Port"])
      try:
        self.allowMissed = int(Parameters["Mode3"])
      except Exception as e:
        Domoticz.Log("Max missed is not a number: "+ Parameters["Mode3"])
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

    def onCommand(self, Unit, Command, Level, Hue):
      CommandStr = str(Command);
      
      # Calculate color and send update to devices
      if ( CommandStr == "On"):
        # send WOL
        self.sendWOL()

    def sendWOL(self):
      # only if WOL exists
      if not (self.mac is None):
        Domoticz.Debug("Send WOL to MAC: "+ self.mac)
        data = b'FFFFFFFFFFFF' + (self.mac * 20).encode()
        send_data = b'' 

        # Split up the hex values and pack.
        for i in range(0, len(data), 2):
          send_data += struct.pack('B', int(data[i: i + 2], 16))

        # Broadcast it to the LAN.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(send_data, ('255.255.255.255', self.wolport))
    
    def onHeartbeat(self):
      
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
            self.missed = 0 # reset miss counter
            Devices[1].Update( 1, "On") # update
            self.lastState = True 
        else:
          if self.lastState:
            self.missed = self.missed + 1
            if self.missed > self.allowMissed:
              Devices[1].Update( 0, "Off")
              self.lastState = False
            
      if self.arping:
        #ARPING
        command = 'sudo arping -c1 -W 1 '+ self.ip  + ' > '+self.tempFile+' &'
      else:
        #PING
        command = 'ping -c 1 -n -s 1 -q '+ self.ip  + ' > '+self.tempFile+' &'
      subprocess.call(command , shell=True)
      Domoticz.Debug(command)
       

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

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