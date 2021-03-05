#!/home/pi/stromzaehler/venv_pi/bin/python3
#-*- coding:utf-8 -*-

import socket, time, datetime, platform, os
import csv
import struct
import influxdb
import ezrdata              #meine Funktion zum Auslesen der Fußbodenheizung
import ds18b20data          #meine Funktion zum Heizungssensoren lesen
import verbraucherschalten  #meine Funktion zum Verbraucher schalten
import urllib.request


# Konstanten
#PV-klein
SPANNUNG_PV = bytes.fromhex('01040000000271cb') #Spannung V
STROM_PV =    bytes.fromhex('0104000600069009') #Strom A
LEISTUNG_PV = bytes.fromhex('0104000C000C300C') #Leistung w
VERBRAUCH_PV = bytes.fromhex('010400480048702A') #Verbrauch kWh
EINSPEISUNG_PV  = bytes.fromhex('0104004a004a502b') #Einspeisung kWh
PF_PV =  bytes.fromhex('0104001E001E1004') #Power factor PV -

#PV-SMA
SPANNUNG_PV2 = bytes.fromhex('0304000000027029') #Spannung V
STROM_PV2 =    bytes.fromhex('03040006000691EB') #Strom A
LEISTUNG_PV2 = bytes.fromhex('0304000C000C31EE') #Leistung W
VERBRAUCH_PV2 = bytes.fromhex('03040048004871C8') #Verbrauch kWh
EINSPEISUNG_PV2  = bytes.fromhex('0304004a004a51C9') #Einspeisung kWh
PF_PV2 =  bytes.fromhex('0304001E001E11E6') #Power factor PV -

#Netzzähler
SPANNUNG1 = bytes.fromhex('02040000000271F8') #Spannung V
SPANNUNG2 = bytes.fromhex('020400020002D038') #Spannung V
SPANNUNG3 = bytes.fromhex('0204000400023039') #Spannung V

STROM1 =    bytes.fromhex('020400060006903A') #Strom A
STROM2 =    bytes.fromhex('020400080006F1F9') #Strom A
STROM3 =    bytes.fromhex('0204000a00065039') #Strom A

LEISTUNG =  bytes.fromhex('020400340034B020') #Leistung
LEISTUNG1 = bytes.fromhex('0204000C000C303F') #Leistung 1
LEISTUNG2 = bytes.fromhex('0204000E000C91FF') #Leistung 2
LEISTUNG3 = bytes.fromhex('02040010000CF1F9') #Leistung 3

VERBRAUCH = bytes.fromhex('0204004800487019') #Verbrauch
EINSPEISUNG= bytes.fromhex('0204004a004a5018') #Einspeisung

PF1 = bytes.fromhex('0204001E001E1037') #power factor Phase 1
PF2 = bytes.fromhex('020400200020F02B') #power factor Phase 2
PF3 = bytes.fromhex('020400220022D02A') #power factor Phase 3

WARTEN_AUF_ANTWORT_SEKUNDEN = 5

SERVER_DATA_DIR = '/home/pi/stromzaehler/data'
WINDOWS_DATA_DIR = 'testdata'

INTERVAL_SECS = 1



def _WertParsen(antwort):
  #return round(float(np.frombuffer(bytes(reversed(antwort[3:7])),dtype=np.float32)),1)
  return round(float(struct.unpack('f', bytes(reversed(antwort[3:7])))[0]),2)

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
            #Stromzähler PV
            self.dec_spannung_pv = self.HoleWert(SPANNUNG_PV) #Rohwert aus Zähler
            self.dec_strom_pv = self.HoleWert(STROM_PV) #Rohwert aus Zähler
            self.dec_leistung_pv = -1*self.HoleWert(LEISTUNG_PV) #Rohwert aus Zähler
            self.dec_verbrauch_pv = self.HoleWert(VERBRAUCH_PV) #Rohwert aus Zähler
            self.dec_einspeisung_pv = self.HoleWert(EINSPEISUNG_PV) #Rohwert aus Zähler [kWh]
            self.dec_pf_pv = self.HoleWert(PF_PV) #Rohwert aus Zähler

            #Stromzähler PV2
            self.dec_spannung_pv2 = self.HoleWert(SPANNUNG_PV2) #Rohwert aus Zähler
            self.dec_strom_pv2 = self.HoleWert(STROM_PV2) #Rohwert aus Zähler
            self.dec_leistung_pv2 = -1*self.HoleWert(LEISTUNG_PV2) #Rohwert aus Zähler
            self.dec_verbrauch_pv2 = self.HoleWert(VERBRAUCH_PV2) #Rohwert aus Zähler
            self.dec_einspeisung_pv2 = self.HoleWert(EINSPEISUNG_PV2) #Rohwert aus Zähler
            self.dec_pf_pv2 = self.HoleWert(PF_PV2) #Rohwert aus Zähler

            #Stromzähler Netz
            self.dec_spannung1 = self.HoleWert(SPANNUNG1) #Rohwert aus Zähler
            self.dec_spannung2 = self.HoleWert(SPANNUNG2) #Rohwert aus Zähler
            self.dec_spannung3 = self.HoleWert(SPANNUNG3) #Rohwert aus Zähler

            self.dec_strom1 = self.HoleWert(STROM1) #Rohwert aus Zähler
            self.dec_strom2 = self.HoleWert(STROM2) #Rohwert aus Zähler
            self.dec_strom3 = self.HoleWert(STROM3) #Rohwert aus Zähler
#soldierende Leistungen am Netzzählers, bedeutet die PV-Leistung ist schon abgezogen
            self.dec_leistung = self.HoleWert(LEISTUNG)  #Rohwert aus Zähler
            self.dec_leistung1 = self.HoleWert(LEISTUNG1) #Rohwert aus Zähler
            self.dec_leistung2 = self.HoleWert(LEISTUNG2) #Rohwert aus Zähler
            self.dec_leistung3 = self.HoleWert(LEISTUNG3) #Rohwert aus Zähler

            self.dec_verbrauch = self.HoleWert(VERBRAUCH)  #Rohwert aus Zähler
            self.dec_einspeisung = self.HoleWert(EINSPEISUNG)  #Rohwert aus Zähler

            self.dec_pf1 = self.HoleWert(PF1)  #Rohwert aus Zähler
            self.dec_pf2 = self.HoleWert(PF2)  #Rohwert aus Zähler
            self.dec_pf3 = self.HoleWert(PF3)  #Rohwert aus Zähler

            self.dec_leistung_pv_ges = (self.dec_leistung_pv + self.dec_leistung_pv2)
            self.dec_leistung_verbrauch = self.dec_leistung + self.dec_leistung_pv_ges #[W] Gesamtleistung aus Netz und PV / im Haushalt verbrauchte Leistung

            #Berechnungen zu PV Kennzahlen
            if (self.dec_leistung_pv_ges) > 0:
                if self.dec_leistung > 0: #Leistung wird aus Netz bezogen [W]
                    self.dec_eigenverbrauch = self.dec_leistung_pv_ges #im Falle von PV Leistung wird komplett selber verbraucht
                    self.dec_autarkie_ratio = 100.0 * self.dec_eigenverbrauch / (self.dec_leistung + self.dec_eigenverbrauch)
                if self.dec_leistung < 0: #Einspeisung
                    self.dec_eigenverbrauch = self.dec_leistung_verbrauch #im Falle von Netzeinspeisung (je nach Vorzeichen dec_leistung, noch nicht relevant)
                    self.dec_autarkie_ratio = 100.0
                self.dec_eigenverbrauch_ratio = 100.0 * self.dec_eigenverbrauch / self.dec_leistung_pv_ges# wird >100% 
                


            if (self.dec_leistung_pv_ges) == 0:
                self.dec_eigenverbrauch = 0.0
                self.dec_eigenverbrauch_ratio = 100.0
                self.dec_autarkie_ratio = 0.0

            self.dec_eigenverbrauch_summe = self.dec_einspeisung_pv + self.dec_einspeisung_pv2 - self.dec_einspeisung #[kWh]
            self.dec_gespart_summe = self.dec_eigenverbrauch_summe*0.25
            ausgaben = 350+336+540+1000+100+100
            #50€ FI und Sicherung
            #100€ Zwei Richtungszähler
            #180€ Wechselrichter klein und Zubehör ErEne
            #20€ Stecker Amazon =350
            #336€ Aluprofile Aufständerung
            #540, SMA Sunny Boy 1.5 Wechselrichter
            #1000, Heckert Module und 100 m Kabel
            #100 Winkel Schrauben
            #100 Klemmen Module und Klemmen Querstangen
            self.dec_gewinn_summe = self.dec_eigenverbrauch_summe*0.25-(ausgaben)

            


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
                    stromz.dec_verbrauch, stromz.dec_einspeisung,
                    stromz.dec_spannung_pv, stromz.dec_strom_pv, stromz.dec_leistung_pv,
                    stromz.dec_verbrauch_pv, stromz.dec_einspeisung_pv,
                    stromz.dec_spannung_pv2, stromz.dec_strom_pv2, stromz.dec_leistung_pv2,
                    stromz.dec_verbrauch_pv2, stromz.dec_einspeisung_pv2,
                    stromz.dec_leistung_pv_ges, stromz.dec_eigenverbrauch, stromz.dec_eigenverbrauch_ratio, stromz.dec_autarkie_ratio,
                    stromz.dec_eigenverbrauch_summe, stromz.dec_gespart_summe, stromz.dec_gewinn_summe, stromz.dec_leistung_verbrauch,
                    stromz.dec_pf_pv, stromz.dec_pf_pv2, stromz.dec_pf1, stromz.dec_pf2, stromz.dec_pf3])

    except Exception as e:
        print("Fehler beim Strom Daten als CSV speichern", e)

def strom_to_influx(dbClient, stromz, verbraucherstate):
    try:
        influxdata = {
            'measurement' : 'power',
            'fields' : {
                'spannung1' : stromz.dec_spannung1,         #Rohwert aus Zähler [V]
                'spannung2' : stromz.dec_spannung2,         #Rohwert aus Zähler [V]
                'spannung3' : stromz.dec_spannung3,         #Rohwert aus Zähler [V]
                'strom1' : stromz.dec_strom1,               #Rohwert aus Zähler [A]
                'strom2' : stromz.dec_strom2,               #Rohwert aus Zähler [A]
                'strom3' : stromz.dec_strom3,               #Rohwert aus Zähler [A]
                'leistung1' : stromz.dec_leistung1,         #Rohwert aus Zähler [W]
                'leistung2' : stromz.dec_leistung2,         #Rohwert aus Zähler [W]
                'leistung3' : stromz.dec_leistung3,         #Rohwert aus Zähler [W]
                'leistung' : stromz.dec_leistung,           #Rohwert aus Zähler [W]
                'verbrauch' : stromz.dec_verbrauch,         #Rohwert aus Zähler [kWh]
                'einspeisung' : stromz.dec_einspeisung,     #Rohwert aus Zähler [kWh]
                'spannung_pv' : stromz.dec_spannung_pv,     #Rohwert aus Zähler [V]
                'strom_pv' : stromz.dec_strom_pv,           #Rohwert aus Zähler [A]
                'leistung_pv' : stromz.dec_leistung_pv,     #Rohwert aus Zähler [W]
                'verbrauch_pv' : stromz.dec_verbrauch_pv,   #Rohwert aus Zähler [kWh]
                'einspeisung_pv' : stromz.dec_einspeisung_pv, #Rohwert aus Zähler [kWh]
                'spannung_pv2' : stromz.dec_spannung_pv2,   #Rohwert aus Zähler [V]
                'strom_pv2' : stromz.dec_strom_pv2,         #Rohwert aus Zähler [A]
                'leistung_pv2' : stromz.dec_leistung_pv2,   #Rohwert aus Zähler [W]
                'verbrauch_pv2' : stromz.dec_verbrauch_pv2, #Rohwert aus Zähler [kWh]
                'einspeisung_pv2' : stromz.dec_einspeisung_pv2, #Rohwert aus Zähler [kWh]
                'einspeisung_pv_summe' : stromz.dec_leistung_pv_ges, #[W] dec_leistung_pv+dec_leistung_pv2 -> Summe der PV Produktion
                'eigenverbrauch_pv' : stromz.dec_eigenverbrauch, #[W] -> Summe PV-Produktion - eingespeiste Leistung
                'eigenverbrauch_percent' : stromz.dec_eigenverbrauch_ratio, #[%] Anteil eigenverbrauchter PV-Leistung
                'autarkie_percent' : float(stromz.dec_autarkie_ratio), #[%] Verhältnis Strom aus Netz zu PV
                'eigenverbrauch_summe' : stromz.dec_eigenverbrauch_summe,
                'dec_gespart_summe' : stromz.dec_gespart_summe,
                'dec_gewinn_summe' : stromz.dec_gewinn_summe,
                'dec_leistung_verbrauch' : stromz.dec_leistung_verbrauch, #[W] Verbrauchte Leistung im Haushalt
                'dec_pf_pv' : stromz.dec_pf_pv,             #Rohwert aus Zähler [-]
                'dec_pf_pv2' : stromz.dec_pf_pv2,           #Rohwert aus Zähler [-]
                'dec_pf1' : stromz.dec_pf1,                 #Rohwert aus Zähler [-]
                'dec_pf2' : stromz.dec_pf2,                 #Rohwert aus Zähler [-]
                'dec_pf3' : stromz.dec_pf3,                 #Rohwert aus Zähler [-]
                'Verbraucheranzahl' : verbraucherstate      #Anzahl geschalteter Verbraucher
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
                'measurement'   :  'heat',
                'tags'          : {'name'   : room },
                'fields'        : {'target' : target,
                                   'actual' : actual,
                                   'state'  : area_state,
                                   'battery': battery,
                                   'device_state' : device_state
                }})
        dbClient.write_points(influxdata)
    except Exception as e:
        print("Fehler beim speichern in influxdb (heat)", e)

def ds18b20sensoren_to_influx(dbClient, data1):
    try:
        influxdata = []
        for item in data1:
            sensor, temperature = item
            influxdata.append({
                'measurement' : 'ds18b20sensoren',
                'tags' : { 'name' : sensor },
                'fields' : {
                    'temperature' : temperature,
                }})
        dbClient.write_points(influxdata)
    except Exception as e:
        print("Fehler beim speichern in influxdb (ds18b20sensoren)", e)

""" def verbraucher_schalten(data, verbraucherstate):
    Funktion soll Zusatzverbraucher einschalten sobald ein gewisse Leistung eingespeist wird.
     Ab dieser Leistung werden alle Zusatzverbraucher eingeschaltet und dann sukzessive abgeschaltet, sobald wieder Strom aus dem Netz bezogen wird.

    Args:
        data ([type]): stromz.dec_leistung. Die Leistung am Hauptzähler

    Returns:
        [integer]: Der Rückgabewert ist die Anzahl der Zusatzverbraucher, die gerade eingeschaltet sind
    
    print('Gesamt-Leistung: {}'.format(data))
    if data<-240 and verbraucherstate == 2: #dec_leistung<-150 bei 1 Verbrauchern Verbraucher 2 einschalten
        try:
            fp = urllib.request.urlopen("http://192.168.2.177/cm?cmnd=Power1%20ON") #Badheizung
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            if mystring == '{"POWER":"ON"}':
                verbraucherstate = 3
            else:
                verbraucherstate = 13
            fp.close()
            print('Verbraucher Badheizung ein: {}'.format(verbraucherstate))
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":""}'
            verbraucherstate = 13
    if data<-100 and verbraucherstate == 1: #dec_leistung<-150 bei 1 Verbrauchern Verbraucher 2 einschalten
        try:
            fp = urllib.request.urlopen("http://192.168.2.176/cm?cmnd=Power1%20ON") #Speisekammer
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            if mystring == '{"POWER":"ON"}':
                verbraucherstate = 2
            else:
                verbraucherstate = 12
            fp.close()
            print('Verbraucher Speisekammer ein: {}'.format(verbraucherstate))
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":""}'
            verbraucherstate = 12
    if data<-100 and verbraucherstate == 0: #dec_leistung<-150 bei 0 Verbrauchern Verbraucher 1 einschalten
        try:
            fp = urllib.request.urlopen("http://192.168.2.187/cm?cmnd=Power1%20ON") #Waschküche
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            if mystring == '{"POWER":"ON"}':
                verbraucherstate = 1
            else:
                verbraucherstate = 11
            fp.close()
            print('Verbraucher Waschküche ein: {}'.format(verbraucherstate))
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":""}'
            verbraucherstate = 11



#ausschalten.............................................
    if data>50 and verbraucherstate == 1 or verbraucherstate == 11 and data>50:
        try:
            fp = urllib.request.urlopen("http://192.168.2.187/cm?cmnd=Power1%20OFF") #Waschküche
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            if mystring == '{"POWER":"OFF"}':
                verbraucherstate = 0
            else:
                verbraucherstate = 11
            fp.close()
            print('Verbraucher 1 aus: {}'.format(verbraucherstate))
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":""}'
            verbraucherstate = 11
    if data>50 and verbraucherstate == 2 or verbraucherstate == 12 and data>50:
        try:
            fp = urllib.request.urlopen("http://192.168.2.176/cm?cmnd=Power1%20OFF") #Speisekammer
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            if mystring == '{"POWER":"OFF"}':
                verbraucherstate = 1
            else:
                verbraucherstate = 12
            fp.close()
            print('Verbraucher 2 aus: {}'.format(verbraucherstate))
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":""}'
            verbraucherstate = 12
    if data>80 and verbraucherstate == 3 or verbraucherstate == 13 and data>50:
        try:
            fp = urllib.request.urlopen("http://192.168.2.177/cm?cmnd=Power1%20OFF") #Badheizung
            mybytes = fp.read()
            mystring = mybytes.decode("utf8")
            if mystring == '{"POWER":"OFF"}':
                verbraucherstate = 2
            else:
                verbraucherstate = 13
            fp.close()
            print('Verbraucher 3 aus: {}'.format(verbraucherstate))
        except OSError as err:
            print("OS error: {0}".format(err))
            mystring = '{"POWER":""}'
            verbraucherstate = 13
    return verbraucherstate
 """

if __name__ == "__main__":
    dbClient = influxdb.InfluxDBClient(
        host='localhost', username='admin', password='none', database='home')

    stromz = StromZaehler()
    skip=1

    verbraucherstate = 0

    while True:
      try:

        stromz.update()

        print(
            stromz.dec_leistung, 'W,',
            stromz.dec_leistung1, 'W,',
            stromz.dec_leistung2, 'W,',
            stromz.dec_leistung3, 'W,',
            stromz.dec_verbrauch, 'kWh')


        #Verbraucher schalten
        print('Trocknerstatus: {}'.format(verbraucherschalten.verbraucher_schalten(stromz.dec_leistung, verbraucherstate)))
        verbraucherstate = verbraucherschalten.verbraucher_schalten(stromz.dec_leistung, verbraucherstate) #Funktionsaufruf
        strom_to_csv(stromz)
        strom_to_influx(dbClient, stromz, verbraucherstate)
        #print('strom2influx')


        #skip += 1
        if skip <= 0:      #erst mal deaktiviert, da heizung nicht mehr reagiert. war: nur jeden 20ten Durchlauf die Temperaturen lesen und in DB schreiben
            data = ezrdata.poll_all()
            heizung_to_influx(dbClient, data)
            print(data)
            
            data1 = ds18b20data.poll_all()
            ds18b20sensoren_to_influx(dbClient, data1)
            print(data1)
            skip = 1
        
      except Exception as e:
          print("Fehler beim verarbeiten", e)


      time.sleep(INTERVAL_SECS)
