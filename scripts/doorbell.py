#!/usr/bin/python3

# doorbell based on interrupt with filtering and logging

# settings
GPIO_doorbell = 26                  # BCM Pin number
domoticzidx = 48                    # ID of doorbell
domoticzserver="192.168.13.88:8080" # IP / port domoticz
domoticzusername = "pi"             # username
domoticzpassword = "pi"             # password

mintimebetweenrings = 1             # in seconds (means bell is 2\X seconds blind after a press)
logrings = True                     # logging to stdout
minbuttonpressed = 20               # 0 = do no check, other time in milliseconds
maxbuttonpressed = 5000             # time (ms)to wait until button press is over (only used if minbuttonpressed > 0)


import RPi.GPIO as GPIO
import time
import urllib.request 
import json
import traceback
import sys
from base64 import b64encode

# Setup IO
GPIO.setwarnings(False) 
GPIO.setmode(GPIO.BCM) # BOARD does not work for pin 29
GPIO.setup(GPIO_doorbell, GPIO.IN, pull_up_down=GPIO.PUD_UP)

inlog ='%s:%s' % (domoticzusername, domoticzpassword) 
base64string = b64encode(inlog.encode('utf-8')).decode('utf-8')

def microTime():
  return int(round(time.time() * 1000))
  
def domoticzrequest (url):
  request = urllib.request.Request(url)
  request.add_header("Authorization", "Basic %s" % base64string)
  response = urllib.request.urlopen(request)
  return response.read().decode('utf-8')
  
def microtimeToString(microtime):
  return time.strftime("%d-%m-%Y %H:%M:%S", time.localtime(microtime/1000))
  
def reportBell():
  domoticzrequest("http://" + domoticzserver + "/json.htm?type=command&param=switchlight&idx=" + str(domoticzidx) + "&switchcmd=On")
  time.sleep(mintimebetweenrings)
  domoticzrequest("http://" + domoticzserver + "/json.htm?type=command&param=switchlight&idx=" + str(domoticzidx) + "&switchcmd=Off")
  

while True:
  # Doorbell is active low, so a falling edge means the door has been pressed
  try:
    sys.stdout.flush()
    GPIO.wait_for_edge(GPIO_doorbell, GPIO.FALLING)
    timePressed = microTime()
    
    # doorbell is pressed
    if (minbuttonpressed > 0):
      result = GPIO.wait_for_edge(GPIO_doorbell, GPIO.RISING, timeout=maxbuttonpressed)
      if result is None:
        if logrings:
          print ("Doorbell pressed at "+ microtimeToString(timePressed)+" but not released after "+str(maxbuttonpressed)+" milliseconds, ignored.")
      else:
        timeLoose = microTime()
        pressedtime = timeLoose - timePressed
        
        if (pressedtime > minbuttonpressed):
          if logrings:
            print ("Doorbell pressed at "+ microtimeToString(timePressed)+" for "+str(pressedtime)+ " milliseconds, notified Domoticz.")
          reportBell()
   
        else:
          if logrings:
            print ("Doorbell pressed at "+ microtimeToString(timePressed)+" for "+str(pressedtime)+ " milliseconds, minimal of "+ str(minbuttonpressed) +" is required, ignored.")
    else:
      if logrings:
        print ("Doorbell pressed at "+ microtimeToString(timePressed)+", notified Domoticz")
      reportBell()
  except Exception as e:
    print ("Error occured: "+ traceback.format_exc())


