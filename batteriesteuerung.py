#!/usr/bin/env python3

import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import struct, time, socket
from pyModbusTCP.client import ModbusClient #für sma Wechselrichter
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

# SMA Wechselrichter ----------------------------------------------------------------
SERVER_HOST_SBS50 = "192.168.2.115"    #SMA Wechselrichter
SERVER_PORT_SBS50 = 502               #SMA Wechselrichter

sma_SBS50 = ModbusClient(host=SERVER_HOST_SBS50, port=SERVER_PORT_SBS50, unit_id=6, debug=False, auto_open=True)

#Modbus-Befehle aus: https://files.sma.de/downloads/MODBUS-HTML_SBxx-1VL-40_V12.zip
Metering_GridMs_TotWOut         = 30867 #Einspeiseleistung
Metering_GridMs_TotWIn          = 30865 #Leistung Bezug
Bat_TmpVal                      = 30849 #Temperatur
Bat_ChaStt                      = 30845 #SOC
Bat_ChakWhStt                   = 32233 #aktueller Batterieenergieinhalt
BatChrg_CurBatCha               = 31393 #Momentane Batterieladung
BatDsch_CurBatDsch              = 31395 #Momentane Batterieentladung
Inverter_WModCfg_WCtlComCfg_WCtlComAct = 40151 #801/802

CmpBMS_GridWSpt                 = 40801 #Sollwert der Netzaustauschleistung
CmpBMS_OpMod                    = 40236 #303: Aus (Off)//308: Ein (On)//1438: Automatik (Auto)//2289: Batterie laden (BatChaMod)//2290: Batterie entladen (BatDschMod)//2424: Voreinstellung (Dft)
CmpBMS_BatChaMinW               = 40793
CmpBMS_BatChaMaxW               = 40795
CmpBMS_BatDschMinW              = 40797
CmpBMS_BatDschMaxW              = 40799


#MQTT Dimmer ----------------------------------------
MQTT_SERVER = "192.168.2.43"

INTERVAL_SECS = 30   #Wartezeit in der Endlosschleife


def sma_reader_SBS50():
    Metering_GridMs_TotWOut_read		= sma_SBS50.read_holding_registers(Metering_GridMs_TotWOut, 2) #Netzbezug
    sma_SBS50_einspeiseleistung_netz	= Metering_GridMs_TotWOut_read[1]
    Metering_GridMs_TotWIn_read		    = sma_SBS50.read_holding_registers(Metering_GridMs_TotWIn, 2) # Netzeinspeisung
    sma_SBS50_bezugsleistung_netz	    = Metering_GridMs_TotWIn_read[1]
    Bat_ChaStt_read		                = sma_SBS50.read_holding_registers(Bat_ChaStt, 2)   #SOC
    sma_SBS50_SOC                       = Bat_ChaStt_read[1]
    Bat_ChakWhStt_read		            = sma_SBS50.read_holding_registers(Bat_ChakWhStt, 2)    #Kapazität
    sma_SBS50_Bat_ChakWhStt             = Bat_ChakWhStt_read[1]
    BatChrg_CurBatCha_read		        = sma_SBS50.read_holding_registers(BatChrg_CurBatCha, 2) #Ladeleistung
    CurBatCha                           = BatChrg_CurBatCha_read[1]
    BatDsch_CurBatDsch_read		        = sma_SBS50.read_holding_registers(BatDsch_CurBatDsch, 2) #Entladeleistung
    CurBatDsch                          = BatDsch_CurBatDsch_read[1]
    Bat_TmpVal_read		                = sma_SBS50.read_holding_registers(Bat_TmpVal, 2) #Temperatur
    Bat_Temperatur                      = Bat_TmpVal_read[1]
    return sma_SBS50_einspeiseleistung_netz, sma_SBS50_bezugsleistung_netz, sma_SBS50_SOC, sma_SBS50_Bat_ChakWhStt, CurBatCha, CurBatDsch, Bat_Temperatur

#Leistungsbegrenzung des Batterie-Wechselrichters
def sma_begrenzung(sma_SBS50_SOC, hysterese):
    if sma_SBS50_SOC<85: hysterese = False
    if sma_SBS50_SOC>90 or hysterese == True:   
        print("SOC>90")    
        reduktion_charge_max = 500 #0 im Sommer, #500 im Winter
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_OpMod, [0, 1438])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMaxW, [0, reduktion_charge_max])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMaxW, [0, 5000])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_GridWSpt, [0, 0])
        #hysterese = True #im Sommer
    elif sma_SBS50_SOC>80 and sma_SBS50_SOC <= 90 and hysterese == False:
        reduktion_charge_max = -90*sma_SBS50_SOC+8200 #im Sommer
        reduktion_charge_max = -50*sma_SBS50_SOC+5000 #im Winter
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_OpMod, [0, 1438])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMaxW, [0, reduktion_charge_max])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMaxW, [0, 5000])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_GridWSpt, [0, 0])
    elif sma_SBS50_SOC>70 and sma_SBS50_SOC <= 80:
        reduktion_charge_max = -200*sma_SBS50_SOC+17000 #1000
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_OpMod, [0, 1438])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMaxW, [0, reduktion_charge_max])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMaxW, [0, 5000])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_GridWSpt, [0, 0])
    else:
        reduktion_charge_max=4000
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_OpMod, [0, 1438])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatChaMaxW, [0, reduktion_charge_max])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMinW, [0, 0])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_BatDschMaxW, [0, 4000])
        Modbus_ID_write= sma_SBS50.write_multiple_registers(CmpBMS_GridWSpt, [0, 0])
    return reduktion_charge_max, hysterese

if __name__ == "__main__":
    sma_SBS50_leistung_netz = 0
    sma_SBS50_leistung_batterie = 0
    reduktion_charge_max = 5000
    global hysterese
    hysterese = False

    i=0

    client = mqtt.Client("stromzaehler") #create new instance
    client.connect(MQTT_SERVER) #connect to broker

    client = influxdb_client.InfluxDBClient(url="http://localhost:8086", token="MJOrPQAIxCmrb2PlxImx544WXXR46NJv__um40583I-s4Zmq2xJmCjCiU4ZDJ_jFF0WmcWTh4HrKr2RsiDZovQ==", org="Home")
    write_api = client.write_api(write_options=SYNCHRONOUS)


    while True:
      try:
        sma_SBS50_einspeiseleistung_netz, sma_SBS50_bezugsleistung_netz, sma_SBS50_SOC, sma_SBS50_Bat_ChakWhStt, CurBatCha, CurBatDsch, Bat_Temperatur = sma_reader_SBS50()
        time.sleep(1)
        reduktion_charge_max, hysterese = sma_begrenzung(sma_SBS50_SOC, hysterese)

        if sma_SBS50_bezugsleistung_netz > 0:
            sma_SBS50_leistung_netz = sma_SBS50_bezugsleistung_netz
        elif sma_SBS50_einspeiseleistung_netz > 0:
            sma_SBS50_leistung_netz = -1*sma_SBS50_einspeiseleistung_netz
        else:
            sma_SBS50_leistung_netz = 0

        if CurBatCha > 0:
            sma_SBS50_leistung_batterie = CurBatCha
        elif CurBatDsch > 0:
            sma_SBS50_leistung_batterie = -1*CurBatDsch
        else:
            sma_SBS50_leistung_batterie = 0


        client = mqtt.Client("Batterie") #create new instance
        client.connect(MQTT_SERVER) #connect to broker
        client.publish("linuxserver/batterie/Leistung", sma_SBS50_leistung_batterie)
        client.publish("linuxserver/pwr/SBS50_Batterieleistung", sma_SBS50_leistung_batterie)
        client.publish("linuxserver/batterie/SOC", sma_SBS50_SOC)
        client.publish("linuxserver/batterie/Kapazität", sma_SBS50_Bat_ChakWhStt/100)
        client.publish("linuxserver/batterie/Temperatur", Bat_Temperatur/10)

        p = influxdb_client.Point("sma_SBS50_SOC").tag("Einheit", "%").tag("Quelle", "linux_server").field("sma_SBS50_SOC", sma_SBS50_SOC)
        write_api.write(bucket="home", org="Home", record=p)
        p = influxdb_client.Point("sma_SBS50_Bat_kapazitaet_akt").tag("Einheit", "kWh").tag("Quelle", "linux_server").field("sma_SBS50_Bat_kapazitaet_akt", sma_SBS50_Bat_ChakWhStt/100)
        write_api.write(bucket="home", org="Home", record=p)   
 
        
        print(
            sma_SBS50_leistung_netz, 'W Netz SBS50 // ',
            sma_SBS50_Bat_ChakWhStt/100, 'kWh Batterieinhalt // ',
            sma_SBS50_leistung_batterie, 'Watt Batterieleistungsfluss // ',
            Bat_Temperatur/10, '°C // ',
            sma_SBS50_SOC, '% SOC // ',
            reduktion_charge_max, 'Watt Ladebegrenzung')
        
        
        print("Influx schreiben")

      except Exception as e:
          print("Fehler beim verarbeiten", e)

      time.sleep(INTERVAL_SECS)
