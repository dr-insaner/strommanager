import socket, time, datetime, platform, os
import struct

#PV-klein
SPANNUNG_PV = bytes.fromhex('01040000000271cb') #Spannung V
STROM_PV =    bytes.fromhex('0104000600069009') #Strom A
LEISTUNG_PV = bytes.fromhex('0104000C000C300C') #Leistung w
VERBRAUCH_PV = bytes.fromhex('010400480048702A') #Verbrauch kWh
EINSPEISUNG_PV  = bytes.fromhex('0104004a004a502b') #Einspeisung kWh
PF_PV =  bytes.fromhex('0104001E001E1004') #Power factor PV -
BAUDRATE_PV = bytes.fromhex('0104001E001E1004') #Power factor PV -

#PV-SMA
SPANNUNG_PV2 = bytes.fromhex('0304000000027029') #Spannung
STROM_PV2 =    bytes.fromhex('03040006000691EB') #Strom
LEISTUNG_PV2 = bytes.fromhex('0304000C000C31EE') #Leistung
VERBRAUCH_PV2 = bytes.fromhex('03040048004871C8') #Verbrauch
EINSPEISUNG_PV2  = bytes.fromhex('0304004a004a51C9') #Einspeisung
PF_PV2 =  bytes.fromhex('0304001E001E11E6') #Power factor PV


LEISTUNG =  bytes.fromhex('020400340034B020') #Leistung
VERBRAUCH = bytes.fromhex('0204004800487019') #Verbrauch
EINSPEISUNG = bytes.fromhex('0204004a004a5018') #Einspeisung
PF1 = bytes.fromhex('0204001E001E1037') #power factor Phase 1
PF2 = bytes.fromhex('020400200020F02B') #power factor Phase 2
PF3 = bytes.fromhex('020400220022D02A') #power factor Phase 3

WARTEN_AUF_ANTWORT_SEKUNDEN = 3


INTERVAL_SECS = 3

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
            self.dec_spannung_pv = self.HoleWert(SPANNUNG_PV)
            self.dec_strom_pv = self.HoleWert(STROM_PV)
            self.dec_leistung_pv = -1*self.HoleWert(LEISTUNG_PV)
            self.dec_verbrauch_pv = self.HoleWert(VERBRAUCH_PV)
            self.dec_einspeisung_pv = self.HoleWert(EINSPEISUNG_PV)
            self.dec_pf_pv = self.HoleWert(PF_PV)

            self.dec_spannung_pv2 = self.HoleWert(SPANNUNG_PV2)
            self.dec_strom_pv2 = self.HoleWert(STROM_PV2)
            self.dec_leistung_pv2 = -1*self.HoleWert(LEISTUNG_PV2)
            self.dec_verbrauch_pv2 = self.HoleWert(VERBRAUCH_PV2)
            self.dec_einspeisung_pv2 = self.HoleWert(EINSPEISUNG_PV2)
            self.dec_pf_pv2 = self.HoleWert(PF_PV2)

            self.dec_leistung = self.HoleWert(LEISTUNG)
            self.dec_verbrauch = self.HoleWert(VERBRAUCH)
            self.dec_einspeisung = self.HoleWert(EINSPEISUNG)
            self.dec_pf1 = self.HoleWert(PF1)
            self.dec_pf2 = self.HoleWert(PF2)
            self.dec_pf3 = self.HoleWert(PF3)

            if self.dec_leistung_pv > 0:
                if self.dec_leistung_pv < self.dec_leistung:
                    self.dec_eigenverbrauch = self.dec_leistung_pv #im Falle von PV Leistung wird komplett selber verbraucht
                if self.dec_leistung_pv > self.dec_leistung:
                    self.dec_eigenverbrauch = self.dec_leistung_pv + self.dec_leistung #im Falle von Netzeinspeisung (je nach Vorzeichen dec_leistung, noch nicht relevant)
                self.dec_eigenverbrauch_ratio = 100* self.dec_eigenverbrauch / self.dec_leistung_pv
                self.dec_autarkie_ratio = 100* self.dec_eigenverbrauch / self.dec_leistung

            if self.dec_leistung_pv == 0:
                self.dec_eigenverbrauch = 0
                self.dec_eigenverbrauch_ratio = 100
                self.dec_autarkie_ratio = 0

            if self.dec_leistung_pv2 > 0:
                if self.dec_leistung_pv2 < self.dec_leistung:
                    self.dec_eigenverbrauch2 = self.dec_leistung_pv2 #im Falle von PV Leistung wird komplett selber verbraucht
                if self.dec_leistung_pv2 > self.dec_leistung:
                    self.dec_eigenverbrauch2 = self.dec_leistung_pv2 + self.dec_leistung #im Falle von Netzeinspeisung (je nach Vorzeichen dec_leistung, noch nicht relevant)
                self.dec_eigenverbrauch_ratio2 = 100* self.dec_eigenverbrauch2 / self.dec_leistung_pv2
                self.dec_autarkie_ratio2 = 100* self.dec_eigenverbrauch2 / self.dec_leistung

            if self.dec_leistung_pv2 == 0:
                self.dec_eigenverbrauch2 = 0
                self.dec_eigenverbrauch_ratio2 = 100
                self.dec_autarkie_ratio2 = 0

            self.dec_eigenverbrauch_summe = self.dec_einspeisung_pv + self.dec_einspeisung_pv2 - self.dec_einspeisung
            self.dec_gespart_summe = self.dec_eigenverbrauch_summe*0.25
            ausgaben=350 
            #50€ FI und Sicherung
            #100€ Zwei Richtungszähler
            #180€ Wechselrichter und Zubehör ErEne
            #20€ Stecker Amazon
            self.dec_gewinn_summe = self.dec_eigenverbrauch_summe*0.25-(ausgaben)



        except Exception as e:
            print("Fehler beim Strom Daten holen", e)

if __name__ == "__main__":

    stromz = StromZaehler()
    while True:
      try:
        stromz.update()
        print('PV1')
        print(
            stromz.dec_leistung_pv, 'W,',
            stromz.dec_spannung_pv, 'V,',
            stromz.dec_strom_pv, 'A,',
            stromz.dec_einspeisung_pv, 'kWh,',
            stromz.dec_verbrauch_pv, 'kWh')
        print('PV2')
        print(
            stromz.dec_leistung_pv2, 'W,',
            stromz.dec_spannung_pv2, 'V,',
            stromz.dec_strom_pv2, 'A,',
            stromz.dec_einspeisung_pv2, 'kWh,',
            stromz.dec_verbrauch_pv2, 'kWh')
        print(
            stromz.dec_leistung, 'W,',
            stromz.dec_einspeisung, 'kWh,',
            stromz.dec_verbrauch, 'kWh')
        print('PV-Summe')
        print(
            stromz.dec_eigenverbrauch_summe, 'kWh,',
            stromz.dec_gespart_summe, '€,',
            stromz.dec_gewinn_summe, '€')

        print(
            stromz.dec_eigenverbrauch, 'W,',
            stromz.dec_eigenverbrauch_ratio, '%,',
            stromz.dec_autarkie_ratio, '%')

        print(
            stromz.dec_pf1, '- PF1,',
            stromz.dec_pf2, '- PF2,',
            stromz.dec_pf3, '- PF3,',
            stromz.dec_pf_pv, '- PF_PV')

      except Exception as e:
          print("Fehler beim verarbeiten", e)

      time.sleep(INTERVAL_SECS)
