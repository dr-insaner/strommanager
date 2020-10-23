from datetime import timedelta, date
from influxdb import InfluxDBClient
import datetime as dt
import pandas as pd
import numpy as np
import time
import matplotlib.pyplot as plt

client = InfluxDBClient('localhost', 8086, 'admin', 'admin', 'home')


def find_first(feld,name):
    """queries the first record date of a giveb field in influx"""
    query = 'SELECT First('+ feld + ') from ' + name
    result = str(client.query(query)) #Antwort in String umwandeln
    try:
        zeit = result.split("[{")[1] #Resultset am Anfang rauswerfen
        zeit = zeit.split("first': ")[0] #nur die Inhalte nach mean nehmen
        zeit = zeit.split("time': '")[1]
        zeit = zeit[0:len(zeit)-5] #Klammern um Ende entfernen
        datum = zeit.split("T")[0]
        zeit = zeit.split("T")[1]
    except:
        print("Fehler in Daten beim splitten/function query hour")
    return zeit, datum



def query_hour(unixtime, feld):
    """query hour verlangt "hour, day, month, year" und gibt den mittelwert der Stunde für den Wert zurück
    """
    query = 'SELECT Mean('+ feld + ') from "power" WHERE time >' + str(unixtime) + ' AND time <='  + str(unixtime) + '+ 1h'
    result = str(client.query(query)) #Antwort in String umwandeln
    try:
        leistung = result.split("[{")[1] #Resultset am Anfang rauswerfen
        leistung = leistung.split("mean': ")[1] #nur die Inhalte nach mean nehmen
        leistung = float(leistung[0:len(leistung)-4]) #Klammern um Ende entfernen
    except:
        print("Fehler in Daten beim splitten/function query hour: " + dt.datetime.utcfromtimestamp(unixtime/1000000000).strftime('%Y-%m-%d %H:%M:%S'))
        leistung = 'NaN'
    return leistung

def influx2df(start_date, end_date, test):
    print()


if __name__ == "__main__":
    start_date= find_first("leistung","power")[1]
    start_date = dt.datetime.strptime(start_date, '%Y-%m-%d')#+ timedelta(11)
    end_date = dt.datetime.now()
    print('Bearbeite von {} bis {}'.format(start_date, end_date))

    df = pd.DataFrame()



    for n in range(int((end_date - start_date).days)-1):
        datum = start_date + timedelta(n+1)
        datum_p2= datum + timedelta(hours = 2)
        for stunde in range(24):
            unixtime = ((time.mktime(datum.timetuple()))+stunde+10777)*1000000000
            date_aus_unixtime= dt.datetime.utcfromtimestamp(unixtime/1000000000).strftime('%Y-%m-%d %H:%M:%S')
            datum= datum + timedelta(hours = 1)
            datum_p2 = datum_p2 + timedelta(hours = 1) #zwei Stunden Zeitverschiebung berücksichtigen
            leistung=query_hour(int(unixtime),"leistung")
            leistung1=query_hour(int(unixtime),"leistung1")
            leistung2=query_hour(int(unixtime),"leistung2")
            leistung3=query_hour(int(unixtime),"leistung3")
            leistung_pv=query_hour(int(unixtime),"leistung_pv")
            #print('Leistung am {} in unixtime {} aus unixtime {}:  {} Watt'.format(datum_p2,int(unixtime/1000000000), date_aus_unixtime, leistung))
            df = df.append([[datum_p2,leistung, leistung1, leistung2, leistung3, leistung_pv]], ignore_index=True)   #dataframe erstellen


    df.columns = ['datum','Leistung','Leistung1','Leistung2','Leistung3','Leistung PV']
    df['hour'] = pd.to_datetime(df['datum']).dt.hour
    df['month'] = pd.to_datetime(df['datum']).dt.month
    df['day_of_week_int'] = pd.to_datetime(df['datum']).dt.dayofweek
    df['day_of_week'] = df['datum'].dt.day_name()

    df['Leistung'] = pd.to_numeric(df['Leistung'], errors='coerce')
    df['Leistung1'] = pd.to_numeric(df['Leistung1'], errors='coerce')
    df['Leistung2'] = pd.to_numeric(df['Leistung2'], errors='coerce')
    df['Leistung3'] = pd.to_numeric(df['Leistung3'], errors='coerce')
    df['Leistung PV'] = pd.to_numeric(df['Leistung PV'], errors='coerce')
    print(df)
    ###nach Stunden auswerten
    df_leistung_mean = df.groupby('hour', as_index=False).mean(numeric_only=True)
    df_leistung_min = df.groupby('hour', as_index=False).min(numeric_only=True)
    df_leistung_max = df.groupby('hour', as_index=False).max(numeric_only=True)

    #make plots
    df_leistung_mean.plot(kind='bar',x='hour',y='Leistung')
    plt.ylabel('Leistung [W]')
    plt.xlabel('Stunde am Tag ab [h]')
    plt.savefig('Mean_power_hour_over_all.png')

    df_leistung_min.plot(kind='bar',x='hour',y='Leistung')
    plt.ylabel('Leistung [W]')
    plt.xlabel('Stunde am Tag ab [h]')
    plt.savefig('Min_power_hour_over_all.png')

    df_leistung_max.plot(kind='bar',x='hour',y='Leistung')
    plt.ylabel('Leistung [W]')
    plt.xlabel('Stunde am Tag ab [h]')
    plt.savefig('Max_power_hour_over_all.png')
    plt.clf()


    ax = plt.gca()

    df_leistung_mean.plot(kind='line',x='hour',y='Leistung',ax=ax, color='black', label='mittlere Leistung')
    df_leistung_min.plot(kind='line',x='hour',y='Leistung', color='green', ax=ax, label='minimale Leistung')
    df_leistung_max.plot(kind='line',x='hour',y='Leistung', color='red', ax=ax, label='maximale Leistung')
    df_leistung_mean.plot(kind='line',x='hour',y='Leistung PV', color='black', ax=ax, label='mittlere PV Leistung', linestyle='dashed')   
    df_leistung_min.plot(kind='line',x='hour',y='Leistung PV', color='green', ax=ax, label='minimale PV Leistung', linestyle='dashed')   
    df_leistung_max.plot(kind='line',x='hour',y='Leistung PV', color='red', ax=ax, label='maximale PV Leistung', linestyle='dashed')   

    plt.ylabel('Leistung [W]')
    plt.xlabel('Stunde am Tag ab [h]')
    plt.xticks((np.arange(0, 24, 1)))
    plt.yticks((np.arange(0, 4250, 200)))
    plt.grid()
    plt.ylim(0,2000)
    plt.savefig('power_hour_over_all.png')