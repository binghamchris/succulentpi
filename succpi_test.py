#!/usr/bin/env python3


import sys
import seeed_si114x
import time
import signal
import grovepi
import requests
import json
from datetime import datetime
import configparser

# Check if a non-default config file has been specified
if len(sys.argv) > 1:
  config_path = sys.argv[1]
else:
  config_path = "config.ini"
config = configparser.RawConfigParser()
config.read(config_path)

SI1145 = seeed_si114x.grove_si114x()

while True:
    try:
      time.sleep(5)
      print("-------------------")
      print(f"{datetime.now()}")

      # Moisture Sensors
      ## Min  Typ  Max  Condition
      ## 0    0    0    sensor in open air
      ## 0    20   300  sensor in dry soil
      ## 300  580  700  sensor in humid soil
      ## 700  940  950  sensor in water
      print(f"Moisture Top (A0):\t{grovepi.analogRead(0)}")
      print(f"Moisture Middle (A1):\t{grovepi.analogRead(1)}")
      print(f"Moisture Bottom (A2):\t{grovepi.analogRead(2)}")
      print(f"Visible Light:\t\t{SI1145.ReadVisible}")
      # The seeed_si114x module states that to obtain the correct value, the return from the .ReadUV function must be divided by 100
      print(f"UV Light:\t\t{SI1145.ReadUV/100}")
      print(f"IR Light:\t\t{SI1145.ReadIR}")

      # Get room measurements from the Awair Local API
      awair_raw = requests.get(config['AWAIR']['local_api_url'])

      # Check if the Awair Local API returned content
      ## NB: Sometimes it returns HTTP200 with no content
      if awair_raw.text:
        awair_json = json.loads(awair_raw.text)
        # Dew point in ºC
        print(f"Dew Point:\t\t{awair_json['dew_point']}")
        # Temperature in ºC
        print(f"Temp:\t\t\t{awair_json['temp']}")
        # Relative humidity in %
        print(f"Rel Humid:\t\t{awair_json['humid']}")
        # Absolute humidity in g/m³
        print(f"Abs Humid:\t\t{awair_json['abs_humid']}")
        # CO2 in ppm
        print(f"CO2:\t\t\t{awair_json['co2']}")
        # Total VOCs in ppb
        print(f"VOC:\t\t\t{awair_json['voc']}")
        # Hydrogen sensor signal (unitless)
        print(f"VOC H2:\t\t\t{awair_json['voc_h2_raw']}")
        # Ethanol sensor signal (unitless)
        print(f"VOC Ethanol:\t\t{awair_json['voc_ethanol_raw']}")
        # Particulates < 2.5 microns in size in µg/m³
        print(f"PM 2.5:\t\t\t{awair_json['pm25']}")
      else:
        print("Awair Local API unavailable")
      
    except KeyboardInterrupt:
        break
    except IOError:
        print ("Error")