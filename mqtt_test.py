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
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder

# Check if a non-default config file has been specified
if len(sys.argv) > 1:
  config_path = sys.argv[1]
else:
  config_path = "config.ini"
config = configparser.RawConfigParser()
config.read(config_path)

SI1145 = seeed_si114x.grove_si114x()

mqtt_endpoint = config['AWS_IOT_MQTT']['endpoint']
mqtt_client_id = config['AWS_IOT_MQTT']['client_id']
mqtt_certificate= config['AWS_IOT_MQTT']['certificate']
mqtt_private_key = config['AWS_IOT_MQTT']['private_key']
mqtt_root_ca = config['AWS_IOT_MQTT']['amazon_root_ca_1']
topic = config['AWS_IOT_MQTT']['topic']

event_loop_group = io.EventLoopGroup(1)
host_resolver = io.DefaultHostResolver(event_loop_group)
client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
mqtt_connection = mqtt_connection_builder.mtls_from_path(
  endpoint=mqtt_endpoint,
  cert_filepath=mqtt_certificate,
  pri_key_filepath=mqtt_private_key,
  client_bootstrap=client_bootstrap,
  ca_filepath=mqtt_root_ca,
  client_id=mqtt_client_id,
  clean_session=False,
  keep_alive_secs=6
)

print("Connecting to {} with client ID '{}'...".format(mqtt_endpoint, mqtt_client_id))

connect_future = mqtt_connection.connect()
connect_future.result()
print("Connected!")

while True:
  try:
    time.sleep(10)
    print("-------------------")

    # Moisture Sensors
    ## Min  Typ  Max  Condition
    ## 0    0    0    sensor in open air
    ## 0    20   300  sensor in dry soil
    ## 300  580  700  sensor in humid soil
    ## 700  940  950  sensor in water

    # The seeed_si114x module states that to obtain the correct value, the return from the .ReadUV function must be divided by 100

    data_dict = {
      "timestamp": datetime.now(),
      "plant": {
        "pot": {
          "soil": {
            "moisture_top_a0": grovepi.analogRead(0),
            "moisture_middle_a1": grovepi.analogRead(1),
            "moisture_bottom_a2": grovepi.analogRead(2)
          }
        },
        "env": {
          "visible_light": SI1145.ReadVisible,
          "uv_light": SI1145.ReadUV/100,
          "ir_light": SI1145.ReadIR
        }
      },
      "room" :{
        "env": {}
      }
    }

    awair_raw = requests.get(config['AWAIR']['local_api_url'])

    # Check if the Awair Local API returned content
    ## NB: Sometimes it returns HTTP200 with no content
    if awair_raw.text:
      awair_json = json.loads(awair_raw.text)
        
      # Dew point in ºC
      data_dict['room']['env']['dew_point'] = awair_json['dew_point']
      # Temperature in ºC
      data_dict['room']['env']['temp'] = awair_json['temp']
      # Relative humidity in %
      data_dict['room']['env']['rel_humid'] = awair_json['humid']
      # Absolute humidity in g/m³
      data_dict['room']['env']['abs_humid'] = awair_json['abs_humid']
      # CO2 in ppm
      data_dict['room']['env']['co2'] = awair_json['co2']
      # Total VOCs in ppb
      data_dict['room']['env']['voc_total'] = awair_json['voc']
      # Hydrogen sensor signal (unitless)
      data_dict['room']['env']['voc_h2'] = awair_json['voc_h2_raw']
      # Ethanol sensor signal (unitless)
      data_dict['room']['env']['voc_ethanol'] = awair_json['voc_ethanol_raw']
      # Particulates < 2.5 microns in size in µg/m³
      data_dict['room']['env']['pm25'] = awair_json['pm25']
    else:
      data_dict['room']['env']['dew_point'] = None
      data_dict['room']['env']['temp'] = None
      data_dict['room']['env']['rel_humid'] = None
      data_dict['room']['env']['abs_humid'] = None
      data_dict['room']['env']['co2'] = None
      data_dict['room']['env']['voc_total'] = None
      data_dict['room']['env']['voc_h2'] = None
      data_dict['room']['env']['voc_ethanol'] = None
      data_dict['room']['env']['pm25'] = None

    data_json = json.dumps(data_dict, default=str)
    print(data_json)

    mqtt_connection.publish(topic=topic, payload=data_json, qos=mqtt.QoS.AT_LEAST_ONCE)

  except KeyboardInterrupt:
    break
  except IOError:
    print ("Error")
