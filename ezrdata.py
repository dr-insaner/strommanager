#!/home/pi/stromzaehler/venv_pi/bin/python3
import time
import urllib
import contextlib
from urllib.request import urlopen
from xml.etree.ElementTree import parse

URL2 = 'http://192.168.2.188/data/static.xml'
URL1 = 'http://192.168.2.144/data/static.xml'
INTERVAL_SECS = 60

def poll_ezr_data(url):
    try:
        with contextlib.closing(urlopen(url)) as response:
          #print(response.read().decode())
          xmldoc = parse(response)
        root = xmldoc.getroot()

        result = []
        for child in root:
            batteries = {}
            for text in child.findall('IODEVICE'):
                number = int(text.find('HEATAREA_NR').text)
                battery = int(text.find('BATTERY').text)
                devicestate = int(text.find('IODEVICE_STATE').text)
                batteries[number] = (battery, devicestate)
            for text in child.findall('HEATAREA'):
                number = int(text.attrib['nr'])
                name = text.find('HEATAREA_NAME').text
                temp = float(text.find('T_ACTUAL').text)
                target = float(text.find('T_TARGET').text)
                heatstate =  int(text.find('HEATAREA_STATE').text)
                result.append(
                    (name, temp, target, heatstate, 
                     batteries[number][0], batteries[number][1]))
        return result

    except urllib.error.HTTPError as e:
        print("Could not poll (http error)", url, e, e.read().decode())
        return []
    except Exception as e:
        print("Could not poll", url, e)
        return []

def poll_all():
    data1 = poll_ezr_data(URL1)
    data2 = poll_ezr_data(URL2)
    return data1 + data2

if __name__ == "__main__":
    data = poll_all()
    print(data)
