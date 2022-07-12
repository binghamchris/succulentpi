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
import boto3
import os
import logging

# Create and configure logger
logging.basicConfig(filename="data_capture.log",
                    format='%(asctime)s %(message)s')
logger = logging.getLogger()
if len(sys.argv) > 1:
  if sys.argv[1] == "verbose":
    logger.setLevel(logging.DEBUG)
  else:
    logger.setLevel(logging.INFO)
else:
  logger.setLevel(logging.INFO)


# Check if a non-default config file has been specified
logger.debug("Attempting to open configuration ini file")
config = configparser.RawConfigParser()
config.read("config.ini")

logger.debug("Reading configuration from configuration ini file")
mqtt_endpoint = config['AWS_IOT_MQTT']['endpoint']
mqtt_client_id = config['AWS_IOT_MQTT']['client_id']
mqtt_certificate= config['AWS_IOT_MQTT']['certificate']
mqtt_private_key = config['AWS_IOT_MQTT']['private_key']
mqtt_root_ca = config['AWS_IOT_MQTT']['amazon_root_ca_1']
topic = config['AWS_IOT_MQTT']['topic']
aws_access_key = config['AWS_S3_IMAGES']['access_key']
aws_secret_key = config['AWS_S3_IMAGES']['secret_key']
s3_upload_path = config['AWS_S3_IMAGES']['s3_upload_path']
s3_bucket = config['AWS_S3_IMAGES']['s3_bucket_name']
timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')

def close_mqtt():
  try:
    logger.info("Closing MQTT connection")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
  except:
    logger.error("Error closing MQTT disconnection")

def awair_sensors_null():
  logger.debug("Setting Awair readings to null")
  data_dict['room']['env']['dew_point'] = None
  data_dict['room']['env']['temp'] = None
  data_dict['room']['env']['rel_humid'] = None
  data_dict['room']['env']['abs_humid'] = None
  data_dict['room']['env']['co2'] = None
  data_dict['room']['env']['voc_total'] = None
  data_dict['room']['env']['voc_h2'] = None
  data_dict['room']['env']['voc_ethanol'] = None
  data_dict['room']['env']['pm25'] = None

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

try:
  logger.debug(f"Connecting to MQTT endpoint {mqtt_endpoint} with client ID {mqtt_client_id}")
  connect_future = mqtt_connection.connect()
  connect_future.result()
  logger.info(f"Successfully established MQTT connection to {mqtt_endpoint}")
except:
  logger.error("MQTT connection failed")
  quit()

SI1145 = seeed_si114x.grove_si114x()

data_dict = {
    "timestamp": timestamp,
    "plant": {
      "pot": {
        "soil": {}
      },
      "env": {},
      "images": {}
    },
    "room" :{
      "env": {}
    }
  }

try:
  logger.debug("Attempting to read Grove sensors")
  # Moisture Sensors
  ## Min  Typ  Max  Condition
  ## 0    0    0    sensor in open air
  ## 0    20   300  sensor in dry soil
  ## 300  580  700  sensor in humid soil
  ## 700  940  950  sensor in water

  # The seeed_si114x module states that to obtain the correct value, the return from the .ReadUV function must be divided by 100
  data_dict['plant']['pot']['soil']['moisture_top_a0'] = grovepi.analogRead(0)
  data_dict['plant']['pot']['soil']['moisture_middle_a1'] = grovepi.analogRead(1)
  data_dict['plant']['pot']['soil']['moisture_bottom_a2'] = grovepi.analogRead(2)
  data_dict['plant']['env']['visible_light'] = SI1145.ReadVisible
  data_dict['plant']['env']['uv_light'] = SI1145.ReadUV/100
  data_dict['plant']['env']['ir_light'] = SI1145.ReadIR
except:
  logger.error("Error reading Grove sensors; setting sensor readings to null")
  data_dict['plant']['pot']['soil']['moisture_top_a0'] = None
  data_dict['plant']['pot']['soil']['moisture_middle_a1'] = None
  data_dict['plant']['pot']['soil']['moisture_bottom_a2'] = None
  data_dict['plant']['env']['visible_light'] = None
  data_dict['plant']['env']['uv_light'] = None
  data_dict['plant']['env']['ir_light'] = None


try:
  logger.debug("Attempting to aquire data from the Awair API")
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
    awair_sensors_null()
except:
  logger.error("Error reading Awair API")
  awair_sensors_null()
  

try:
  logger.debug("Attempting to capture camera image")
  os.system(f"libcamera-still -e png -o /tmp/{timestamp}.png")
  s3 = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key)
  temp = s3.upload_file(f"/tmp/{timestamp}.png", s3_bucket, f"{s3_upload_path}/{timestamp}.png")
  data_dict['plant']['images']['infrared'] = f"https://{s3_bucket}.s3.eu-central-1.amazonaws.com/{s3_upload_path}/{timestamp}.png"
  os.system(f"rm -f /tmp/{timestamp}.png")
except:
  logger.error("Error capturing or uploading camera image")
  data_dict['plant']['images']['infrared'] = None


try:
  logger.info("Attempting to send data via MQTT connection")
  data_json = json.dumps(data_dict, default=str)
  logger.debug(f"Sending: {data_json}")
  mqtt_connection.publish(topic=topic, payload=data_json, qos=mqtt.QoS.AT_LEAST_ONCE)
  logger.info("Data sent successfully via MQTT connection")
except:
  logger.error("Error sending data via the MQTT connection")
  close_mqtt()
  quit()


close_mqtt()