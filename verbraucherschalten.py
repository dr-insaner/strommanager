
#!/home/pi/stromzaehler/venv_pi/bin/python3
#-*- coding:utf-8 -*-

import urllib.request


def verbraucher_schalten(data, verbraucherstate):
    """Funktion soll Zusatzverbraucher einschalten sobald ein gewisse Leistung eingespeist wird.
     Ab dieser Leistung werden alle Zusatzverbraucher eingeschaltet und dann sukzessive abgeschaltet, sobald wieder Strom aus dem Netz bezogen wird.

    Args:
        data ([type]): stromz.dec_leistung. Die Leistung am Hauptzähler

    Returns:
        [integer]: Der Rückgabewert ist die Anzahl der Zusatzverbraucher, die gerade eingeschaltet sind
    """
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


if __name__ == "__main__":
    verbraucherstate = verbraucher_schalten(1000, verbraucherstate) #Funktionsaufruf Leistung als Integer
    print(verbraucherstate)