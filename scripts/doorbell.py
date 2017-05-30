#!/usr/bin/python2

# doorbell based on interrupt with filtering and logging

# settings
GPIO_doorbell = 26                  # BCM Pin number
domoticzidx = 29                    # ID of doorbell
domoticzserver="127.0.0.1:8080"     # IP / port domoticz
domoticzusername = "USER"           # username
domoticzpassword = "PASSWORD"       # password

mintimebetweenrings = 1             # in seconds (means bell is 2\X seconds blind after a press)
logrings = True                     # logging to stdout
minbuttonpressed = 20               # 0 = do no check, other time in milliseconds
maxbuttonpressed = 5000             # time (ms)to wait until button press is over (only used if minbuttonpressed > 0)


import RPi.GPIO as GPIO
import time
import urllib2
import json
import base64
import traceback
import sys

# Setup IO
GPIO.setwarnings(False) 
GPIO.setmode(GPIO.BCM) # BOARD does not work for pin 29
GPIO.setup(GPIO_doorbell, GPIO.IN, pull_up_down=GPIO.PUD_UP)

base64string = base64.encodestring('%s:%s' % (domoticzusername, domoticzpassword)).replace('\n', '')

def microTime():
  return int(round(time.time() * 1000))
  
def domoticzrequest (url):
  request = urllib2.Request(url)
  request.add_header("Authorization", "Basic %s" % base64string)
  response = urllib2.urlopen(request)
  return response.read()
  
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
          print "Doorbell pressed at "+ microtimeToString(timePressed)+" but not released after "+str(maxbuttonpressed)+" milliseconds, ignored."
      else:
        timeLoose = microTime()
        pressedtime = timeLoose - timePressed
        
        if (pressedtime > minbuttonpressed):
          if logrings:
            print "Doorbell pressed at "+ microtimeToString(timePressed)+" for "+str(pressedtime)+ " milliseconds, notified Domoticz."
          reportBell()
   
        else:
          if logrings:
            print "Doorbell pressed at "+ microtimeToString(timePressed)+" for "+str(pressedtime)+ " milliseconds, minimal of "+ str(minbuttonpressed) +" is required, ignored."
    else:
      if logrings:
        print "Doorbell pressed at "+ microtimeToString(timePressed)+", notified Domoticz"
      reportBell()
  except Exception as e:
    print "Error occured: "+ traceback.format_exc()


