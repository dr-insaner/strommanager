#!/home/pi/stromzaehler/venv_pi/bin/python3
#-*- coding:utf-8 -*-

import os
#import glob
import time
import urllib.request
 
os.system('modprobe w1-gpio')
os.system('modprobe w1-therm')

#leere Arrays anlegen
ID=[None]*10
einbauort=[None]*10

ID[0] = '28-0217b20c84ff'
ID[1] = '28-0217b20c5eff'
ID[2] = '28-051760bf02ff'
ID[3] = '28-051760bb2aff'
ID[4] = '28-011862d06cff'
ID[5] = '28-011862d1d2ff'
ID[6]= '28-011862c7e3ff'
ID[7]= '28-011862d39cff'
ID[8]= '28-0217b20437ff'
einbauort[0] =  'Vorlauf'
einbauort[1] =  'WarmwasserVorlauf'
einbauort[2] =  'Raumtemperatur'
einbauort[3] =  'FBVerteilerFlur'
einbauort[4] =  'FuBoHeizungNachWT'
einbauort[5] =  'FuBoHeizungVorWT'
einbauort[6] =  'SpeicherOben'
einbauort[7] =  'HeizungVorlauf'
einbauort[8] =  'SolarVorlauf'
base_dir = '/sys/bus/w1/devices/'

i=0 #Zähler für die Sensoren
#Number_Of_Files=0

def switch_zirkulationspumpe(data):
    if data[6][1]>55 and data[8][1]>55: # data[6] 'SpeicherOben' und data[8] 'SolarVorlauf'
        try:
            fp = urllib.request.urlopen("http://192.168.2.186/cm?cmnd=Power1%20ON")
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            fp.close()
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":"ON"}'
    else:
        try:
            fp = urllib.request.urlopen("http://192.168.2.186/cm?cmnd=Power1%20OFF")
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            fp.close()
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":"OFF"}'
    if mystring == '{"POWER":"OFF"}':
        pumpstate = 0
    elif mystring == '{"POWER":"ON"}':
        pumpstate = 1
    else:
        pumpstate = 9
    return pumpstate



def read_temp_raw(i):
	device_file = base_dir + ID[i] + '/w1_slave'
	#print(device_file)
	f = open(device_file, 'r')
	lines = f.readlines()
	f.close()
	return lines
    
def read_temp(i):
    lines = read_temp_raw(i)
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.1)
        lines = read_temp_raw(i)
    equals_pos = lines[1].find('t=')
    if equals_pos != -1:
        temp_string = lines[1][equals_pos+2:]
        temp_c = float(temp_string) / 1000.0
        return temp_c
        

def poll_all():
    data = []
    pair = []
    i=0
    while i<=8:
        pair = (einbauort[i], read_temp(i))
        data.append(pair) 
        i=i+1
    pumpstate = ('WW-Pumpenstatus',float(switch_zirkulationspumpe(data)))
    data.append(pumpstate)    
    return data

if __name__ == "__main__":
    data = poll_all()
    print(data)
