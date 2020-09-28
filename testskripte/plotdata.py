#!/usr/bin/python3
#-*- coding:utf-8 -*-

import plotly.graph_objects as go
# import matplotlib.pyplot as plt
import os, csv, os.path, datetime

def render_data(data_dir):
    files = os.listdir(data_dir)
    print(files)
    x = []
    y = []
    for filename in files:
        if not 'csv' in filename:
            continue

        with open(os.path.join(data_dir, filename), 'rt') as csvfile:
            try: 
                reader = csv.reader(csvfile, delimiter=',', quotechar='|')
                if not reader:
                    continue
                for row in reader:
                    if not row:
                        continue
                    datum, zeit, wochentag, dec_spannung1, dec_spannung2, dec_spannung3, dec_strom1, dec_strom2, dec_strom3, dec_leistung, dec_leistung1, dec_leistung2, dec_leistung3, dec_verbrauch, dec_einspeisung = row
                    datum_p = datetime.datetime.strptime(datum + " " + zeit, "%d.%m.%y %H:%M:%S")
                    x.append(datum_p)
                    y.append(dec_verbrauch)
            except Exception as e:
                print("Error in", filename, e)

    
        
        fig = go.Figure(data=[go.Scatter(x=x, y=y)])
        fig.write_image('dashboard/figure.svg')
    # plt.plot(x,y)
    # plt.show()
   
if __name__ == "__main__":
    render_data('data')
