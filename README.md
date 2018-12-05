# Domoticz #

Script contains stand alone scripts which must be executed after booting `/etc/rc.local` or something like it.
All script have comments and the settings are stored on the top of each script.

## scripts/doorbell.py ##
Doorbell script which reads falling flank and rising flank. If margins are good (not too long / short) it will be reported to Domoticz. Requires a virtual doorsensor.

Eletronic schem to connect 8VAC to Raspberry:
[https://github.com/ericstaal/domoticz/blob/master/doorbell_scheme.png](https://github.com/ericstaal/domoticz/blob/master/doorbell_scheme.png "Scheme")

Usage:
Add script to `/etc/rc.local`

## plugins ##
All written according the new format see https://www.domoticz.com/wiki/Developing_a_Python_plugin

## plugins/lg ##
Control LG 2011 smart TV. Basic operational since interface is ilimited. Power on is not supported on TV so you can to turn it on by hand. Has a input selector an buttons for volume/channel. Also display channel name

## plugins/hosola ##
Python plugin to read out hosola / omnik solar inverters. Auto detect which phases are connected

## plugins/hyperion ##
HYperion plugin to select a static color a a effect. Effects are loaded during startup

## plugins/ledenet ##
Plugin for ledenet / Ufo RGBW led controller. Able to use fixed (static) colros but also effect and custom effects

## plugins/marantz ##
Plugin to control amrantz / denon receiver. Adjusted from original option to display radio channel name and to make input selection configurable

## plugins/raspbbery ##
Reads temperature and disk space, sble to control a PWM fan based on the temperature

