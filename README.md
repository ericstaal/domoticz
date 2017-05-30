# Domoticz #

Script contains stand alone scripts which must be executed after booting `/etc/rc.local` or something like it.
All script have comments and the settings are stored on the top of each script.

## scripts/hosola.php ##
Script to read out a Hosola inverter. Create VAC / VDC Power and temperature sensors and use these device indexes. Script only logs these but can log more (see script for details)

Usage:
Add script to `/etc/rc.local`


## scripts/doorbell.py ##
Doorbell script which reads falling flank and rising flank. If margins are good (not too long / short) it will be reported to Domoticz. Requires a virtual doorsensor.

Eletronic schem to connect 8VAC to Raspberry:
[https://github.com/ericstaal/domoticz/blob/master/doorbell_scheme.png](https://github.com/ericstaal/domoticz/blob/master/doorbell_scheme.png "Scheme")

Usage:
Add script to `/etc/rc.local`

## scripts/checkonline.py ##
Script to check if IP adres is pingable can be used with a virtual WOL switch

Usage:
Add to `/etc/rc.local`:
    
    sudo /scriptlocation/checkonline.py IP SWITCHIDX INTERVAL COOLDOWN 