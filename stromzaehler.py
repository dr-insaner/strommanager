#!/home/pi/stromzaehler/venv_pi/bin/python3
#-*- coding:utf-8 -*-

import socket, time, datetime, platform, os
import csv
import struct
import influxdb
import paho.mqtt.publish as publish
import paho.mqtt.client as mqtt
import verbraucherschalten  #meine Funktion zum Verbraucher schalten
from pyModbusTCP.client import ModbusClient #für sma Wechselrichter


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

WARTEN_AUF_ANTWORT_SEKUNDEN = 1

SERVER_DATA_DIR = '/home/pi/stromzaehler/data'
WINDOWS_DATA_DIR = 'testdata'

# SMA Wechselrichter ----------------------------------------------------------------
SERVER_HOST = "192.168.2.84"    #SMA Wechselrichter
SERVER_PORT = 502               #SMA Wechselrichter
#Modbus-Befehle aus: https://files.sma.de/downloads/MODBUS-HTML_SBxx-1VL-40_V12.zip
register_Operation_Health       = 30201 #35: Fehler (Alm) 303: Aus (Off) 307: Ok (Ok) 455: Warnung (Wrn)
register_Operation_DrtStt       = 30219 #Grund der Leistungsreduzierung 557: Uebertemperatur (TmpDrt) 884: nicht aktiv (NoneDrt) 1705: Frequenzabweichung (HzDrt) 3520: Spannungsabweichung (VDrt) 3554: Blindleistungsprioritaet (VArDmdDrt) 3556: Hohe DC-Spannung (DcVolMaxDrt) 4560: Externer Vorgabe (WSptMaxDrt) 4561: Externe Vorgabe 2 (WSptMax2Drt) 16777213: Information liegt nicht vor (NaNStt)
register_Operation_StandbyStt   = 33001 #Standby-Status 1393: Warte auf PV-Spannung (WaitPV) 1394: Warte auf gueltiges AC-Netz (WaitGri) 2531: Energiesparmodus (EnSavMod) 16777213: Information liegt nicht vor (NaNStt)
register_Operation_RunStt       = 33003 #Betriebsstatus 295: MPP (Mpp) 443: Konstantspannung (VolDCConst) 1463: Backup (Bck) 1469: Herunterfahren (Shtdwn) 2119: Abregelung (Drt) 16777213: Information liegt nicht vor (NaNStt)
Inverter_WModCfg_WCnstCfg_W_RO  = 30837 #Wirkleistungsbegrenzung in W
Inverter_WModCfg_WCnstCfg_WNom_RO=30839 #Wirkleistungsbegrenzung in %
Inverter_WModCfg_WMod           = 30835 #Betriebsart Wirkleistungsvorgabe
Inverter_WModCfg_WCtlComCfg_WNom= 40016 #Normierte Wirkleistungsbegrenzung durch Anlagensteuerung
leistungsbegrenzung = 100 # in %

bets = 2

counter = 0

c = ModbusClient(unit_id=3)
c.host(SERVER_HOST)
c.port(SERVER_PORT)
#--------------------------------------------------------------------------------------

#MQTT Dimmer ----------------------------------------
MQTT_SERVER = "192.168.2.150"
MQTT_PATH = "/home/pwr_soll_1"


INTERVAL_SECS = 0.5   #Wartezeit in der Endlosschleife


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
                print("Timeout, versuche es wieder (Modbus) ...", anfrage)
                time.sleep(0.01)
            except socket.error as e:
                # Something else happened, handle error, exit, etc.
                print("Anderer Socket Fehler (Modbus):", e)
                time.sleep(5)
    
    def update_leistung(self):
        try:
            self.dec_leistung = self.HoleWert(LEISTUNG)  #Rohwert aus Zähler
        except Exception as e:
            print("Fehler beim Strom Daten holen leistung", e)
            
    def update_PV1(self):
        try:
            #Stromzähler PV
            #self.dec_spannung_pv = self.HoleWert(SPANNUNG_PV) #Rohwert aus Zähler
            self.dec_spannung_pv = 233.3
            #self.dec_strom_pv = self.HoleWert(STROM_PV) #Rohwert aus Zähler
            self.dec_strom_pv = 0.01
            self.dec_leistung_pv = -1*self.HoleWert(LEISTUNG_PV) #Rohwert aus Zähler
            self.dec_verbrauch_pv = self.HoleWert(VERBRAUCH_PV) #Rohwert aus Zähler
            self.dec_einspeisung_pv = self.HoleWert(EINSPEISUNG_PV) #Rohwert aus Zähler [kWh]
            self.dec_pf_pv = self.HoleWert(PF_PV) #Phase Stromzähler PV klein  
        except Exception as e:
            print("Fehler beim Strom Daten holen PV1", e)
            
    def update_PV2(self):
        try:
            #Stromzähler PV2
            #self.dec_spannung_pv2 = self.HoleWert(SPANNUNG_PV2) #Rohwert aus Zähler
            self.dec_spannung_pv2 = 233.3
            #self.dec_strom_pv2 = self.HoleWert(STROM_PV2) #Rohwert aus Zähler
            self.dec_strom_pv2 = 0.01
            self.dec_leistung_pv2 = -1*self.HoleWert(LEISTUNG_PV2) #Rohwert aus Zähler
            self.dec_verbrauch_pv2 = self.HoleWert(VERBRAUCH_PV2) #Rohwert aus Zähler
            self.dec_einspeisung_pv2 = self.HoleWert(EINSPEISUNG_PV2) #Rohwert aus Zähler
            self.dec_pf_pv2 = self.HoleWert(PF_PV2) #Phase Stromzähler PV groß
        except Exception as e:
            print("Fehler beim Strom Daten holen PV2", e)
            
    def update_netz(self):
        try:
            #Stromzähler Netz
            #self.dec_spannung1 = self.HoleWert(SPANNUNG1) #Rohwert aus Zähler
            #self.dec_spannung2 = self.HoleWert(SPANNUNG2) #Rohwert aus Zähler
            #self.dec_spannung3 = self.HoleWert(SPANNUNG3) #Rohwert aus Zähler
            self.dec_spannung1 = 233.3 #Rohwert aus Zähler
            self.dec_spannung2 = 233.3 #Rohwert aus Zähler
            self.dec_spannung3 = 233.3 #Rohwert aus Zähler
            
            #self.dec_strom1 = self.HoleWert(STROM1) #Rohwert aus Zähler
            #self.dec_strom2 = self.HoleWert(STROM2) #Rohwert aus Zähler
            #self.dec_strom3 = self.HoleWert(STROM3) #Rohwert aus Zähler
            self.dec_strom1 = 0.01
            self.dec_strom2 = 0.01
            self.dec_strom3 = 0.01
            
            #saldierende Leistungen am Netzzählers, bedeutet die PV-Leistung ist schon abgezogen
            self.dec_leistung = self.HoleWert(LEISTUNG)  #Rohwert aus Zähler
            self.dec_leistung1 = self.HoleWert(LEISTUNG1) #Rohwert aus Zähler
            self.dec_leistung2 = self.HoleWert(LEISTUNG2) #Rohwert aus Zähler
            self.dec_leistung3 = self.HoleWert(LEISTUNG3) #Rohwert aus Zähler

            self.dec_verbrauch = self.HoleWert(VERBRAUCH)  #Rohwert aus Zähler
            self.dec_einspeisung = self.HoleWert(EINSPEISUNG)  #Rohwert aus Zähler
            
            self.dec_pf1 = self.HoleWert(PF1)  #Phase1 Stromzähler Netz
            self.dec_pf2 = self.HoleWert(PF2)  #Phase2 Stromzähler Netz
            self.dec_pf3 = self.HoleWert(PF3)  #Phase3 Stromzähler Netz
        except Exception as e:
            print("Fehler beim Strom Daten holen PV2", e)
            
    def update_calc(self):
        try:
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
            print("Fehler beim Strom Daten holen calc", e)
            
    def update(self):
        try:
            #Stromzähler PV
            #self.dec_spannung_pv = self.HoleWert(SPANNUNG_PV) #Rohwert aus Zähler
            self.dec_spannung_pv = 233.3
            #self.dec_strom_pv = self.HoleWert(STROM_PV) #Rohwert aus Zähler
            self.dec_strom_pv = 0.01
            self.dec_leistung_pv = -1*self.HoleWert(LEISTUNG_PV) #Rohwert aus Zähler
            self.dec_verbrauch_pv = self.HoleWert(VERBRAUCH_PV) #Rohwert aus Zähler
            self.dec_einspeisung_pv = self.HoleWert(EINSPEISUNG_PV) #Rohwert aus Zähler [kWh]
            self.dec_pf_pv = self.HoleWert(PF_PV) #Phase Stromzähler PV klein            

            #Stromzähler PV2
            #self.dec_spannung_pv2 = self.HoleWert(SPANNUNG_PV2) #Rohwert aus Zähler
            self.dec_spannung_pv2 = 233.3
            #self.dec_strom_pv2 = self.HoleWert(STROM_PV2) #Rohwert aus Zähler
            self.dec_strom_pv2 = 0.01
            self.dec_leistung_pv2 = -1*self.HoleWert(LEISTUNG_PV2) #Rohwert aus Zähler
            self.dec_verbrauch_pv2 = self.HoleWert(VERBRAUCH_PV2) #Rohwert aus Zähler
            self.dec_einspeisung_pv2 = self.HoleWert(EINSPEISUNG_PV2) #Rohwert aus Zähler
            self.dec_pf_pv2 = self.HoleWert(PF_PV2) #Phase Stromzähler PV groß
                        
            #Stromzähler Netz
            #self.dec_spannung1 = self.HoleWert(SPANNUNG1) #Rohwert aus Zähler
            #self.dec_spannung2 = self.HoleWert(SPANNUNG2) #Rohwert aus Zähler
            #self.dec_spannung3 = self.HoleWert(SPANNUNG3) #Rohwert aus Zähler
            self.dec_spannung1 = 233.3 #Rohwert aus Zähler
            self.dec_spannung2 = 233.3 #Rohwert aus Zähler
            self.dec_spannung3 = 233.3 #Rohwert aus Zähler
            
            #self.dec_strom1 = self.HoleWert(STROM1) #Rohwert aus Zähler
            #self.dec_strom2 = self.HoleWert(STROM2) #Rohwert aus Zähler
            #self.dec_strom3 = self.HoleWert(STROM3) #Rohwert aus Zähler
            self.dec_strom1 = 0.01
            self.dec_strom2 = 0.01
            self.dec_strom3 = 0.01
            
#saldierende Leistungen am Netzzählers, bedeutet die PV-Leistung ist schon abgezogen
            self.dec_leistung = self.HoleWert(LEISTUNG)  #Rohwert aus Zähler
            self.dec_leistung1 = self.HoleWert(LEISTUNG1) #Rohwert aus Zähler
            self.dec_leistung2 = self.HoleWert(LEISTUNG2) #Rohwert aus Zähler
            self.dec_leistung3 = self.HoleWert(LEISTUNG3) #Rohwert aus Zähler

            self.dec_verbrauch = self.HoleWert(VERBRAUCH)  #Rohwert aus Zähler
            self.dec_einspeisung = self.HoleWert(EINSPEISUNG)  #Rohwert aus Zähler
            
            self.dec_pf1 = self.HoleWert(PF1)  #Phase1 Stromzähler Netz
            self.dec_pf2 = self.HoleWert(PF2)  #Phase2 Stromzähler Netz
            self.dec_pf3 = self.HoleWert(PF3)  #Phase3 Stromzähler Netz

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

def strom_to_influx(dbClient, stromz, verbraucherstate, begrenzung_pz_PV2, begrenzung_pz_PV2_absolut, dimmer1prozent):
    try:
        influxdata = {
            'measurement' : 'power',
            'fields' : {
                #'spannung1' : stromz.dec_spannung1,         #Rohwert aus Zähler [V]
                #'spannung2' : stromz.dec_spannung2,         #Rohwert aus Zähler [V]
                #'spannung3' : stromz.dec_spannung3,         #Rohwert aus Zähler [V]
                #'strom1' : stromz.dec_strom1,               #Rohwert aus Zähler [A]
                #'strom2' : stromz.dec_strom2,               #Rohwert aus Zähler [A]
                #'strom3' : stromz.dec_strom3,               #Rohwert aus Zähler [A]
                'leistung1' : stromz.dec_leistung1,         #Rohwert aus Zähler [W]
                'leistung2' : stromz.dec_leistung2,         #Rohwert aus Zähler [W]
                'leistung3' : stromz.dec_leistung3,         #Rohwert aus Zähler [W]
                'leistung' : stromz.dec_leistung,           #Rohwert aus Zähler [W]
                'verbrauch' : stromz.dec_verbrauch,         #Rohwert aus Zähler [kWh]
                'einspeisung' : stromz.dec_einspeisung,     #Rohwert aus Zähler [kWh]
                #'spannung_pv' : stromz.dec_spannung_pv,     #Rohwert aus Zähler [V]
                #'strom_pv' : stromz.dec_strom_pv,           #Rohwert aus Zähler [A]
                'leistung_pv' : stromz.dec_leistung_pv,     #Rohwert aus Zähler [W]
                'verbrauch_pv' : stromz.dec_verbrauch_pv,   #Rohwert aus Zähler [kWh]
                'einspeisung_pv' : stromz.dec_einspeisung_pv, #Rohwert aus Zähler [kWh]
                #'spannung_pv2' : stromz.dec_spannung_pv2,   #Rohwert aus Zähler [V]
                #'strom_pv2' : stromz.dec_strom_pv2,         #Rohwert aus Zähler [A]
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
                'Verbraucheranzahl' : verbraucherstate,     #Anzahl geschalteter Verbraucher
                'Begrenzung PV2' : begrenzung_pz_PV2,              #
                'Begrenzung PV2 absolut' : begrenzung_abs_PV2,       #
                'Dimmer 1 Prozent' : dimmer1prozent         #Dimmer 1 Prozent
            }}
        dbClient.write_points([influxdata])
    except Exception as e:
        print("Fehler beim Speichern in influxdb (power)", e)


#Leistungsbegrenzung des Wechselrichters wird in Prozent übergeben von maximaler Leistung 1500 Watt = 100%
#Wenn die Einspeisung ins Netz zu hoch ist, muss die Leistung reduziert werden
#Bsp Solar produziert 1000 Watt, verbraucht weden aber nur 600 Watt dann müsste die Leistung um 400 Watt auf 600 Watt reduziert werdem.
#Reduzierung also von  auf 40% (600 Watt) 
def sma_begrenzung(power_netz, power_pv, verbraucherstate, dimmer1prozent):
    if verbraucherstate==3 and power_netz < -10 and dimmer1prozent > 90:   
        print("geht noch")    
        reduktion_abs = int((power_pv)+power_netz)	#reduktion auf PV2-Leistung absolut + da bei Einspeisung negativ
        reduktion_abs_kor = reduktion_abs+30 #+300 #100Watt drauf, damit nicht zu viel reduziert wird/ war +100 war aber 300Watt und dimmer ging auf 50%
        reduktion_rel = int(100*reduktion_abs_kor/1500)
        print("reduktion_rel 1: {} %, Reduktion auf PV absolut: {} W".format(reduktion_rel, reduktion_abs_kor))
        if reduktion_abs_kor <=0:
            reduktion_abs_kor = 0
        elif reduktion_abs_kor >=1500:
            reduktion_abs_kor = 1500    
        if not c.is_open():
            if not c.open():
                print("unable to connect to "+SERVER_HOST+":"+str(SERVER_PORT))
        if c.is_open(): 
            print("c.is_open")
            Inverter_WModCfg_WCtlComCfg_WNom_write= c.write_single_register(Inverter_WModCfg_WCtlComCfg_WNom, reduktion_rel)
    else:
        reduktion_rel=100
        reduktion_abs_kor=1500
        Inverter_WModCfg_WCtlComCfg_WNom_write= c.write_single_register(Inverter_WModCfg_WCtlComCfg_WNom, reduktion_rel)
        #print("Inverter_WModCfg_WCtlComCfg_WNom (" + str(Inverter_WModCfg_WCtlComCfg_WNom) + ", " + str(bets) + ") -->" +str(Inverter_WModCfg_WCtlComCfg_WNom_write))
    print("Leistungsbegrenzung: {} %, Reduktion auf PV absolut: {} W".format(reduktion_rel, reduktion_abs_kor))
    return reduktion_rel, reduktion_abs_kor

def dimmer_regeln(power_netz, dimmer1prozent_1):
        ist_leistung_dimmer = int(dimmer1prozent_1/100 * -300) #aktuelle Leistung des Dimmers
        leistung_dimmer_pot= int(power_netz + ist_leistung_dimmer) #Leistungspotenzial des Dimmers hinsichtlich netzverfügbarkeit
        dimmer1prozent = int(-100*leistung_dimmer_pot/300)
        if dimmer1prozent>100: dimmer1prozent=100
        if dimmer1prozent<0: dimmer1prozent=0
        dimmer1prozent = int((dimmer1prozent + dimmer1prozent_1) / 2)
        client = mqtt.Client("P1") #create new instance
        client.connect(MQTT_SERVER) #connect to broker
        client.publish(MQTT_PATH, str(dimmer1prozent))
        print('Leistung Netz: {}; Ist-Leistung Dimmer: {}; Leistungspot Dimmer: {}; dimmer1prozent_1: {}; dimmer1prozent: {}'.format(power_netz, -ist_leistung_dimmer, -leistung_dimmer_pot, dimmer1prozent_1, dimmer1prozent))
        dimmer1prozent_1 = dimmer1prozent
        return dimmer1prozent_1
        
if __name__ == "__main__":
    dbClient = influxdb.InfluxDBClient(
        host='localhost', username='admin', password='none', database='home')

    stromz = StromZaehler()
    skip_csv=1
    global dimmer1prozent
    dimmer1prozent = int(0)    
    global dimmer1prozent_1 
    dimmer1prozent_1 = int(0)
    leistung_dimmer = 0

    verbraucherstate = 0

    client = mqtt.Client("P1") #create new instance
    client.connect(MQTT_SERVER) #connect to broker

    client.publish(MQTT_PATH, "50")#publish

    while True:
      try:
        #stromz.update()
        stromz.update_leistung()
        dimmer1prozent = dimmer_regeln(stromz.dec_leistung, dimmer1prozent)
        stromz.update_PV1()
        stromz.update_leistung()
        dimmer1prozent = dimmer_regeln(stromz.dec_leistung, dimmer1prozent)
        stromz.update_PV2()
        stromz.update_leistung()
        dimmer1prozent = dimmer_regeln(stromz.dec_leistung, dimmer1prozent)
        stromz.update_netz()
        stromz.update_leistung()
        dimmer1prozent = dimmer_regeln(stromz.dec_leistung, dimmer1prozent)
        stromz.update_calc()


        print(
            stromz.dec_leistung, 'W,',
            stromz.dec_leistung1, 'W,',
            stromz.dec_leistung2, 'W,',
            stromz.dec_leistung3, 'W,',
            stromz.dec_verbrauch, 'kWh')

        #Verbraucher schalten
        verbraucherstate = verbraucherschalten.verbraucher_schalten(stromz.dec_leistung, dimmer1prozent, verbraucherstate) #Funktionsaufruf
     
        #Wechselrichterlimitierung
        begrenzung_pz_PV2, begrenzung_abs_PV2 = sma_begrenzung(stromz.dec_leistung, stromz.dec_leistung_pv2, verbraucherstate, dimmer1prozent)
        #begrenzung_pz_PV2=100
        #begrenzung_abs_PV2=1500
        
        #strom_to_csv(stromz)
            
        strom_to_influx(dbClient, stromz, verbraucherstate, begrenzung_pz_PV2, begrenzung_abs_PV2, dimmer1prozent)
        
      except Exception as e:
          print("Fehler beim verarbeiten", e)

      skip_csv = skip_csv+1
      time.sleep(INTERVAL_SECS)
