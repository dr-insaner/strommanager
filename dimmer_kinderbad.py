#!/usr/bin/env python3

import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import struct, time, socket
from pyModbusTCP.client import ModbusClient #für sma Wechselrichter
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS
import numpy

# SMA Wechselrichter ----------------------------------------------------------------
SERVER_HOST_SB15 = "192.168.2.84"    #SMA Wechselrichter
SERVER_HOST_STP80_WIFI = "192.168.2.50"  #SMA 
SERVER_HOST_STP80_LAN = "192.168.2.57"  #SMA
SERVER_HOST_SB36 = "192.168.2.94"  #SMA
SERVER_PORT_SB15 = 502               #SMA Wechselrichter
SERVER_PORT_STP80 = 508              #SMA Wechselrichter
SERVER_PORT_SB36 = 502              #SMA Wechselrichter

sma_SB15 = ModbusClient(host=SERVER_HOST_SB15, port=SERVER_PORT_SB15, unit_id=3, debug=False, auto_open=True)
sma_SB36 = ModbusClient(host=SERVER_HOST_SB36, port=SERVER_PORT_SB36, unit_id=3, debug=False, auto_open=True)
sma_STP80_WIFI = ModbusClient(host=SERVER_HOST_STP80_WIFI, port=SERVER_PORT_STP80, unit_id=4, debug=False, auto_open=True,  timeout=1.0)
sma_STP80_LAN = ModbusClient(host=SERVER_HOST_STP80_LAN, port=SERVER_PORT_STP80, unit_id=4, debug=False, auto_open=True,  timeout=5.0)

#Modbus-Befehle aus: https://files.sma.de/downloads/MODBUS-HTML_SBxx-1VL-40_V12.zip
Metering_GridMs_TotWOut         = 30867 #Einspeiseleistung
Metering_GridMs_TotWIn          = 30865
GridMs_TotW                       = 30775


#MQTT Dimmer ----------------------------------------
MQTT_SERVER = "192.168.2.43"
MQTT_PATH1 = "linuxserver/dimmer_heizstab_kinderbad/prozent_soll"
MQTT_PATH2 = "linuxserver/pwr/leistung_soll"
MQTT_PATH3 = "linuxserver/pwr/leistungpotential"
MQTT_PATH4 = "/home/pwr_soll_1"

INTERVAL_SECS = 1   #Wartezeit in der Endlosschleife


def sma_reader_SB15():
    Metering_GridMs_TotWOut_read		= sma_SB15.read_holding_registers(Metering_GridMs_TotWOut, 2)
    sma_SB15_einspeiseleistung_netz	    = Metering_GridMs_TotWOut_read[1]
    Metering_GridMs_TotWIn_read		    = sma_SB15.read_holding_registers(Metering_GridMs_TotWIn, 2)
    sma_SB15_bezugsleistung_netz	    = Metering_GridMs_TotWIn_read[1]
    GridMs_TotW_read		            = sma_SB15.read_holding_registers(GridMs_TotW, 2)
    sma_SB15_WIFI_einspeisung_AC        = GridMs_TotW_read[1]
    print("------------------------------ SB15 AC Leistung: " + str(sma_SB15_WIFI_einspeisung_AC))

    return sma_SB15_einspeiseleistung_netz, sma_SB15_bezugsleistung_netz, sma_SB15_WIFI_einspeisung_AC

def sma_reader_SB36():
    Metering_GridMs_TotWOut_read		= sma_SB36.read_holding_registers(Metering_GridMs_TotWOut, 2)
    sma_SB36_einspeiseleistung_netz	    = Metering_GridMs_TotWOut_read[1]
    Metering_GridMs_TotWIn_read		    = sma_SB36.read_holding_registers(Metering_GridMs_TotWIn, 2)
    sma_SB36_bezugsleistung_netz	    = Metering_GridMs_TotWIn_read[1]
    GridMs_TotW_read		            = sma_SB36.read_holding_registers(GridMs_TotW, 2)
    sma_SB36_WIFI_einspeisung_AC        = GridMs_TotW_read[1]
    print("------------------------------ SB36 AC Leistung: " + str(sma_SB36_WIFI_einspeisung_AC))

    return sma_SB36_einspeiseleistung_netz, sma_SB36_bezugsleistung_netz, sma_SB36_WIFI_einspeisung_AC

def sma_reader_STP80():
    Metering_GridMs_TotWOut_read_LAN		= sma_STP80_LAN.read_holding_registers(Metering_GridMs_TotWOut, 2)
    Metering_GridMs_TotWIn_read_LAN		    = sma_STP80_LAN.read_holding_registers(Metering_GridMs_TotWIn, 2)
    Metering_GridMs_TotWOut_read_WIFI		= sma_STP80_WIFI.read_holding_registers(Metering_GridMs_TotWOut, 2)
    Metering_GridMs_TotWIn_read_WIFI		= sma_STP80_WIFI.read_holding_registers(Metering_GridMs_TotWIn, 2)
    GridMs_TotW_read_WIFI		= sma_STP80_WIFI.read_holding_registers(GridMs_TotW, 2)
    GridMs_TotW_read_LAN		= sma_STP80_LAN.read_holding_registers(GridMs_TotW, 2)

    if Metering_GridMs_TotWOut_read_LAN is None and Metering_GridMs_TotWOut_read_WIFI is None:
        print("STP80 WIFI und LAN nicht verfügbar.")
        sma_STP80_einspeiseleistung_netz = 0
        sma_STP80_bezugsleistung_netz = 0
        sma_STP80_einspeisung_AC = 0
    if Metering_GridMs_TotWOut_read_LAN is None and Metering_GridMs_TotWOut_read_WIFI is not None:
        sma_STP80_WIFI_einspeiseleistung_netz	= Metering_GridMs_TotWOut_read_WIFI[1]
        sma_STP80_WIFI_bezugsleistung_netz	    = Metering_GridMs_TotWIn_read_WIFI[1]
        sma_STP80_WIFI_einspeisung_AC           = GridMs_TotW_read_WIFI[1]
        print("STP80 WIFI verfügbar. Einspeiseleistung: " + str(sma_STP80_WIFI_einspeiseleistung_netz))
        sma_STP80_einspeiseleistung_netz = sma_STP80_WIFI_einspeiseleistung_netz
        sma_STP80_bezugsleistung_netz   = sma_STP80_WIFI_bezugsleistung_netz
        sma_STP80_einspeisung_AC   = sma_STP80_WIFI_einspeisung_AC
    if Metering_GridMs_TotWOut_read_LAN is not None and Metering_GridMs_TotWOut_read_WIFI is None:
        sma_STP80_LAN_einspeiseleistung_netz	= Metering_GridMs_TotWOut_read_LAN[1]
        sma_STP80_LAN_bezugsleistung_netz	    = Metering_GridMs_TotWIn_read_LAN[1]
        sma_STP80_LAN_einspeisung_AC           = GridMs_TotW_read_LAN[1]
        print("STP80 LAN verfügbar. Einspeiseleistung: " + str(sma_STP80_LAN_einspeiseleistung_netz))
        sma_STP80_einspeiseleistung_netz = sma_STP80_LAN_einspeiseleistung_netz
        sma_STP80_bezugsleistung_netz = sma_STP80_LAN_bezugsleistung_netz
        sma_STP80_einspeisung_AC   = sma_STP80_LAN_einspeisung_AC
    if Metering_GridMs_TotWOut_read_LAN is not None and Metering_GridMs_TotWOut_read_WIFI is not None:
        sma_STP80_LAN_einspeiseleistung_netz	= Metering_GridMs_TotWOut_read_LAN[1]
        sma_STP80_LAN_bezugsleistung_netz	    = Metering_GridMs_TotWIn_read_LAN[1]
        sma_STP80_LAN_einspeisung_AC           = GridMs_TotW_read_LAN[1]
        print("STP80 LAN und WIFI verfügbar. Einspeiseleistung: " + str(sma_STP80_LAN_einspeiseleistung_netz))
        sma_STP80_einspeiseleistung_netz = sma_STP80_LAN_einspeiseleistung_netz
        sma_STP80_bezugsleistung_netz = sma_STP80_LAN_bezugsleistung_netz
        sma_STP80_einspeisung_AC   = sma_STP80_LAN_einspeisung_AC
    
    print("------------------------------ STP80 AC Leistung: " + str(sma_STP80_einspeisung_AC))
    return sma_STP80_einspeiseleistung_netz, sma_STP80_bezugsleistung_netz, sma_STP80_einspeisung_AC

def dimmer_speicher_regeln(power_netz, dimmer_pwm_1):
        ist_leistung_dimmer = int(dimmer_pwm_1**3*-0.000444 + dimmer_pwm_1**2*0.2051 + dimmer_pwm_1*-18.147 + 452.51) #aktuelle Leistung des Dimmers
        if dimmer_pwm_1 < 50: ist_leistung_dimmer = 0
        if dimmer_pwm_1 > 255: ist_leistung_dimmer = 1950

        leistung_dimmer_pot= -int(power_netz - ist_leistung_dimmer + 300) #Leistungspotenzial des Dimmers hinsichtlich netzverfügbarkeit
        
        if leistung_dimmer_pot <= 1:
            dimmer_pwm = 0
            ist_leistung_dimmer = 0
        if leistung_dimmer_pot > 1 and leistung_dimmer_pot <= 200: dimmer_pwm = 80
        if leistung_dimmer_pot > 200 and leistung_dimmer_pot <= 1700:
            dimmer_pwm = int(0.0801*leistung_dimmer_pot+82.3)
        if leistung_dimmer_pot > 1700:
            dimmer_pwm = 255 
        
        dimmer_pwm = int((dimmer_pwm + dimmer_pwm_1) / 2)

        print('Leistung Netz: {}; Ist-Leistung Speicherdimmer: {}; Leistungspot Speicherdimmer: {}; dimmer_pwm_1: {}; dimmer_pwm: {}'.format(power_netz, ist_leistung_dimmer, leistung_dimmer_pot, dimmer_pwm_1, dimmer_pwm))
        dimmer_pwm_1 = dimmer_pwm
        return dimmer_pwm_1, ist_leistung_dimmer, leistung_dimmer_pot

def running_mean(x, N):
    cumsum = numpy.cumsum(numpy.insert(x, 0, 0)) 
    return (cumsum[N:] - cumsum[:-N]) / float(N)

if __name__ == "__main__":
    global dimmer_pwm
    dimmer_pwm = int(0)    
    global dimmer_pwm_1 
    dimmer_pwm_1 = int(0)

    ist_leistung_dimmer = 0
    leistung_dimmer_pot = 0
    sma_SB15_leistung_netz = 0

    i=0

    client = mqtt.Client("stromzaehler") #create new instance
    client.connect(MQTT_SERVER) #connect to broker

    client = influxdb_client.InfluxDBClient(url="http://localhost:8086", token="MJOrPQAIxCmrb2PlxImx544WXXR46NJv__um40583I-s4Zmq2xJmCjCiU4ZDJ_jFF0WmcWTh4HrKr2RsiDZovQ==", org="Home")
    write_api = client.write_api(write_options=SYNCHRONOUS)

    while True:
      try:
        sma_SB15_einspeiseleistung_netz, sma_SB15_bezugsleistung_netz, sma_SB15_einspeisung_AC = sma_reader_SB15()
        sma_SB36_einspeiseleistung_netz, sma_SB36_bezugsleistung_netz, sma_SB36_einspeisung_AC = sma_reader_SB36()
        sma_STP80_einspeiseleistung_netz, sma_STP80_bezugsleistung_netz, sma_STP80_einspeisung_AC = sma_reader_STP80()

        if sma_SB15_bezugsleistung_netz > 0:
            sma_SB15_leistung_netz = sma_SB15_bezugsleistung_netz
        elif sma_SB15_einspeiseleistung_netz > 0:
            sma_SB15_leistung_netz = -1*sma_SB15_einspeiseleistung_netz
        else:
            sma_SB15_leistung_netz = 0
        
        dimmer_pwm, ist_leistung_dimmer_speicher, leistung_dimmer_speicher_pot = dimmer_speicher_regeln(sma_SB15_leistung_netz, dimmer_pwm)
        
        client = mqtt.Client("stromzaehler") #create new instance
        client.connect(MQTT_SERVER) #connect to broker
        client.publish("linuxserver/pwr/leistung_soll_bad", ist_leistung_dimmer)
        client.publish("linuxserver/pwr/leistungpotential_bad", leistung_dimmer_pot)

        client.publish("linuxserver/dimmer_heizstab/speicher", dimmer_pwm)
        client.publish("linuxserver/pwr/leistung_soll_speicher", ist_leistung_dimmer_speicher)
        client.publish("linuxserver/pwr/leistungpotential_speicher", leistung_dimmer_speicher_pot)

        client.publish("linuxserver/pwr/SB15_leistung_netz", sma_SB15_leistung_netz)
        client.publish("linuxserver/pwr/SB15_einspeisung_AC", sma_SB15_einspeisung_AC)
        client.publish("linuxserver/pwr/STP80_einspeisung_AC", sma_STP80_einspeisung_AC)
        client.publish("linuxserver/pwr/SB36_einspeisung_AC", sma_SB36_einspeisung_AC)
        
        print(
            sma_SB15_leistung_netz, 'W Netz SB15 // ',
            sma_STP80_einspeiseleistung_netz, 'W Einspeisung Netz STP80 // ',
            sma_SB15_einspeisung_AC, 'W PV AC SB15 // ',
            sma_STP80_einspeisung_AC, 'W PV AC STP80')
        
        #p = influxdb_client.Point("ist_leistung_heizstab_kinderbad").tag("Einheit", "Watt").tag("Quelle", "linux_server").field("ist_leistung_heizstab_kinderbad", ist_leistung_dimmer)
        #write_api.write(bucket="home", org="Home", record=p)
        #p = influxdb_client.Point("leistung_dimmer_pot_heizstab_kinderbad").tag("Einheit", "Watt").tag("Quelle", "linux_server").field("leistung_dimmer_pot_heizstab_kinderbad", leistung_dimmer_pot)
        #write_api.write(bucket="home", org="Home", record=p)   

        p = influxdb_client.Point("ist_leistung_heizstab_speicher").tag("Einheit", "Watt").tag("Quelle", "linux_server").field("ist_leistung_heizstab_speicher", ist_leistung_dimmer_speicher)
        write_api.write(bucket="home", org="Home", record=p)
        p = influxdb_client.Point("pwm_soll_heizstab_speicher").tag("Einheit", "%").tag("Quelle", "linux_server").field("pwm_soll_heizstab_speicher", dimmer_pwm)
        write_api.write(bucket="home", org="Home", record=p)
        #p = influxdb_client.Point("leistungpotential_speicher").tag("Einheit", "Watt").tag("Quelle", "linux_server").field("leistungpotential_speicher", leistung_dimmer_speicher_pot)
        #write_api.write(bucket="home", org="Home", record=p)               #läuft über MQTT
        
        print("Influx schreiben")

      except Exception as e:
          print("Fehler beim verarbeiten", e)

      time.sleep(INTERVAL_SECS)
