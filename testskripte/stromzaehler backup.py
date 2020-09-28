#!/home/pi/stromzaehler/venv_pi/bin/python3
#-*- coding:utf-8 -*-

import socket, time, datetime, platform, os
import csv
import struct
import influxdb
import ezrdata

# Konstanten
""" SPANNUNG1 = bytes.fromhex('01040000000271cb') #Spannung
SPANNUNG2 = bytes.fromhex('010400020002d00b') #Spannung
SPANNUNG3 = bytes.fromhex('010400040002300A') #Spannung

STROM1 =    bytes.fromhex('0104000600069009') #Strom
STROM2 =    bytes.fromhex('010400080006f1ca') #Strom
STROM3 =    bytes.fromhex('0104000a0006500a') #Strom

LEISTUNG =  bytes.fromhex('010400340034b013') #Leistung
LEISTUNG1 = bytes.fromhex('0104000C000C300C') #Leistung
LEISTUNG2 = bytes.fromhex('0104000E000C91CC') #Leistung
LEISTUNG3 = bytes.fromhex('01040010000Cf1ca') #Leistung

VERBRAUCH = bytes.fromhex('010400480048702A') #Verbrauch
EINSPEISUNG= bytes.fromhex('0104004a004a502b') #Einspeisung """

SPANNUNG1 = bytes.fromhex('02040000000271F8') #Spannung
SPANNUNG2 = bytes.fromhex('020400020002D038') #Spannung
SPANNUNG3 = bytes.fromhex('0204000400023039') #Spannung

STROM1 =    bytes.fromhex('020400060006903A') #Strom
STROM2 =    bytes.fromhex('020400080006F1F9') #Strom
STROM3 =    bytes.fromhex('0204000a00065039') #Strom

LEISTUNG =  bytes.fromhex('020400340034B020') #Leistung
LEISTUNG1 = bytes.fromhex('0204000C000C303F') #Leistung-
LEISTUNG2 = bytes.fromhex('0204000E000C91FF') #Leistung
LEISTUNG3 = bytes.fromhex('02040010000CF1F9') #Leistung

VERBRAUCH = bytes.fromhex('0204004800487019') #Verbrauch
EINSPEISUNG= bytes.fromhex('0204004a004a5018') #Einspeisung


WARTEN_AUF_ANTWORT_SEKUNDEN = 5

SERVER_DATA_DIR = '/home/pi/stromzaehler/data'
WINDOWS_DATA_DIR = 'testdata'

INTERVAL_SECS = 10

def _WertParsen(antwort):
  #return round(float(np.frombuffer(bytes(reversed(antwort[3:7])),dtype=np.float32)),1)
  return round(float(struct.unpack('f', bytes(reversed(antwort[3:7])))[0]),1)

class StromZaehler:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(WARTEN_AUF_ANTWORT_SEKUNDEN)

    def HoleWert(self, anfrage):
        while True:
            try:
                self.sock.sendto(anfrage, ("192.168.2.108", 5111))
                antwort = self.sock.recv(4096)
                return _WertParsen(antwort)
            except socket.timeout as e:
                print("Timeout, versuche es wieder ...", e)
                time.sleep(1)
            except socket.error as e:
                # Something else happened, handle error, exit, etc.
                print("Anderer Socket Fehler:", e)
                time.sleep(5)

    def update(self):
        try:
            self.dec_spannung1 = self.HoleWert(SPANNUNG1)
            self.dec_spannung2 = self.HoleWert(SPANNUNG2)
            self.dec_spannung3 = self.HoleWert(SPANNUNG3)

            self.dec_strom1 = self.HoleWert(STROM1)
            self.dec_strom2 = self.HoleWert(STROM2)
            self.dec_strom3 = self.HoleWert(STROM3)

            self.dec_leistung = self.HoleWert(LEISTUNG)
            self.dec_leistung1 = self.HoleWert(LEISTUNG1)
            self.dec_leistung2 = self.HoleWert(LEISTUNG2)
            self.dec_leistung3 = self.HoleWert(LEISTUNG3)

            self.dec_verbrauch = self.HoleWert(VERBRAUCH)
            self.dec_einspeisung = self.HoleWert(EINSPEISUNG)
        except Exception as e:
            print("Fehler beim Strom Daten holen", e)

def strom_to_csv(stromz):
    try: 
        datum_file = datetime.datetime.now().strftime("%Y-%m-%d")
        datum = datetime.datetime.now().strftime("%d.%m.%y")
        zeit = datetime.datetime.now().strftime("%H:%M:%S")
        wochentag = datetime.datetime.now().strftime("%A")

        filename = "sdm530_" + datum_file + ".csv"
        if platform.system() == 'windows':
            data_file = os.path.join(WINDOWS_DATA_DIR, filename)
        else:
            data_file = os.path.join(SERVER_DATA_DIR, filename)

        with open(data_file, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(
                [datum, zeit, wochentag,
                    stromz.dec_spannung1, stromz.dec_spannung2, stromz.dec_spannung3, 
                    stromz.dec_strom1, stromz.dec_strom2, stromz.dec_strom3,
                    stromz.dec_leistung, 
                    stromz.dec_leistung1, stromz.dec_leistung2, stromz.dec_leistung3, 
                    stromz.dec_verbrauch, stromz.dec_einspeisung])

    except Exception as e:
        print("Fehler beim Strom Daten als CSV speichern", e)

def strom_to_influx(dbClient, stromz):
    try:
        influxdata = {
            'measurement' : 'power',
            'fields' : {
                'spannung1' : stromz.dec_spannung1,
                'spannung2' : stromz.dec_spannung2,
                'spannung3' : stromz.dec_spannung3,
                'strom1' : stromz.dec_strom1,
                'strom2' : stromz.dec_strom2,
                'strom3' : stromz.dec_strom3,
                'leistung1' : stromz.dec_leistung1,
                'leistung2' : stromz.dec_leistung2,
                'leistung3' : stromz.dec_leistung3,
                'leistung' : stromz.dec_leistung,
                'verbrauch' : stromz.dec_verbrauch,
                'einspeisung' : stromz.dec_einspeisung
            }}
        dbClient.write_points([influxdata])
    except Exception as e:
        print("Fehler beim Speichern in influxdb (power)", e)

def heizung_to_influx(dbClient, data):
    try:
        influxdata = []
        for item in data:
            room, actual, target, area_state, battery, device_state = item
            influxdata.append({
                'measurement' : 'heat',
                'tags' : { 'name' : room },
                'fields' : {
                    'target' : target,
                    'actual' : actual,
                    'state' : area_state,
                    'battery' : battery,
                    'device_state' : device_state
                }})
            
        dbClient.write_points(influxdata)
    except Exception as e:
        print("Fehler beim speichern in influxdb (heat)", e)


if __name__ == "__main__":
    dbClient = influxdb.InfluxDBClient(
        host='localhost', username='admin', password='none', database='home')

    stromz = StromZaehler()
    while True:
      try:
        stromz.update()

        print(
            stromz.dec_leistung, 'W,',
            stromz.dec_leistung1, 'W,',
            stromz.dec_leistung2, 'W,',
            stromz.dec_leistung3, 'W,',
            stromz.dec_verbrauch, 'kWh')

        strom_to_csv(stromz)
        strom_to_influx(dbClient, stromz)

        data = ezrdata.poll_all()
        heizung_to_influx(dbClient, data)

      except Exception as e:
          print("Fehler beim verarbeiten", e)

      time.sleep(INTERVAL_SECS)
