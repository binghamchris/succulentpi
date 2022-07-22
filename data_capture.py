#!/usr/bin/env python3
# SucculentPi Data Capture Script
## This is a simple sample script demonstrating the use to AWS IoT Core with
## a Raspberry Pi, GrovePi+ board and sensors, and a Pi Camera for data
## acquisition and upload to AWS services.
## Please note that this script is not intended to be a enterprise-grade
## production-ready implementation of the AWS SDKs, and is instead intended
## as a easy to use example for learning purposes.

# Import the required modules
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

# Create and configure the logger
## This will be used throughout the code to log status messages
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


# Read in the configuration ini file
logger.debug("Attempting to open configuration ini file")
config = configparser.RawConfigParser()
config.read("config.ini")

# Read the individual configuration items from the ini file into variables
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
awair_api_url = config['AWAIR']['local_api_url']
timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')


def close_mqtt():
  # Function to terminate the MQTT connection with AWS IoT Core
  ## One way in which this script is not production-grade is the lack of 
  ## (re)connection management and connection reuse. Opening a new connection 
  ## for each run of the script is not the most efficent approach!

  ## Use a simple 'try' block to catch any exceptions which may occur
  try:
    logger.info(f"Closing MQTT connection to {mqtt_endpoint} with client ID {mqtt_client_id}")
    disconnect_future = mqtt_connection.disconnect()
    disconnect_future.result()
  except:
    logger.error("Error closing MQTT disconnection")

def awair_sensors_null():
  # Function to set the values for all readings from an Awair device to null
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

# Define a MQTT connection to AWS IoT Core over mTLS
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

# Attempt to open an MQTT connection to AWS IoT Core
## In the event this fails for any reason terminate the script as there's no
## point in collecting sensor data if we can't send it.
## This is one area where this script is not production-grade; it does not
## provide for local storage and delayed transmission of captured data
try:
  logger.info(f"Connecting to MQTT endpoint {mqtt_endpoint} with client ID {mqtt_client_id}")
  connect_future = mqtt_connection.connect()
  connect_future.result()
  logger.info(f"Successfully established MQTT connection to {mqtt_endpoint} with client ID {mqtt_client_id}")
except:
  logger.error("MQTT connection failed")
  quit()

# Create an empty Python dictionary to store our readings
## This reflects the structure of the JSON object which will be sent via MQTT
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

# Attempt to read the GrovePi+ sensors and add those readings to the dictionary
try:
  logger.debug("Attempting to read Grove sensors")

  # Create an instance of the class needed to read the sunlight sensor
  sunlight_sensor = seeed_si114x.grove_si114x()

  # Moisture sensor values reference table, for ease of future use:
  ## Min  Typ  Max  Condition
  ## ---  ---  ---  ---------
  ## 0    0    0    sensor in open air
  ## 0    20   300  sensor in dry soil
  ## 300  580  700  sensor in humid soil
  ## 700  940  950  sensor in water

  data_dict['plant']['pot']['soil']['moisture_top_a0'] = grovepi.analogRead(0)
  data_dict['plant']['pot']['soil']['moisture_middle_a1'] = grovepi.analogRead(1)
  data_dict['plant']['pot']['soil']['moisture_bottom_a2'] = grovepi.analogRead(2)
  data_dict['plant']['env']['visible_light'] = sunlight_sensor.ReadVisible
  # The seeed_si114x module states that to obtain the correct value, the return
  # from the .ReadUV function must be divided by 100.
  data_dict['plant']['env']['uv_light'] = sunlight_sensor.ReadUV/100
  data_dict['plant']['env']['ir_light'] = sunlight_sensor.ReadIR
except:
  # If we failed to read any of the sensors, assume all the values are faulty
  # and return null readings.
  logger.error("Error reading Grove sensors; setting sensor readings to null")
  data_dict['plant']['pot']['soil']['moisture_top_a0'] = None
  data_dict['plant']['pot']['soil']['moisture_middle_a1'] = None
  data_dict['plant']['pot']['soil']['moisture_bottom_a2'] = None
  data_dict['plant']['env']['visible_light'] = None
  data_dict['plant']['env']['uv_light'] = None
  data_dict['plant']['env']['ir_light'] = None

# Attempt to read the Awair device's local API
try:
  logger.debug("Attempting to acquire data from the Awair API")
  awair_raw = requests.get(awair_api_url)

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
    # If the Awair local APi returned no data, set all readings to null
    awair_sensors_null()
except:
  # If any errors occurred while trying to query the Awair local API,
  # set all readings to null
  logger.error("Error reading Awair API")
  awair_sensors_null()
  
# Attempt to acquire an image using the IR camera
try:
  logger.debug("Attempting to capture camera image")
  # Due to the switch to libcamera in Raspberry Pi OS Bullseye, the Python 
  # PiCamera module no longer works. Just make a system/CLI call instead
  os.system(f"libcamera-still -e png -o /tmp/{timestamp}.png")
  # Attempt to upload the image to S3
  ## Another area where this script is not production-grade; no error checking
  ## or resiliency measures for the upload.
  s3 = boto3.client('s3', aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key)
  temp = s3.upload_file(f"/tmp/{timestamp}.png", s3_bucket, f"{s3_upload_path}/{timestamp}.png")
  # Add the S3 URL of the image to the dictionary
  data_dict['plant']['images']['infrared'] = f"https://{s3_bucket}.s3.eu-central-1.amazonaws.com/{s3_upload_path}/{timestamp}.png"
  # Delete the local copy of the image
  os.system(f"rm -f /tmp/{timestamp}.png")
except:
  # If any errors occured while trying to acquire the image, set the
  # image URL in the dictionary to null.
  logger.error("Error capturing or uploading camera image")
  data_dict['plant']['images']['infrared'] = None

# Attempt to send the dictionary via the MQTT connection to AWS IoT Core
try:
  logger.info("Attempting to send data via MQTT connection")
  # Convert the Python dictionary to a JSON object
  data_json = json.dumps(data_dict, default=str)
  logger.debug(f"Sending: {data_json}")
  # Send the JSON object via the MQTT Connection
  mqtt_connection.publish(topic=topic, payload=data_json, qos=mqtt.QoS.AT_LEAST_ONCE)
  logger.info("Data sent successfully via MQTT connection")
except:
  # If any errors occurred, close the MQTT connection and terminate the script
  logger.error("Error sending data via the MQTT connection")
  close_mqtt()
  quit()

# If everything worked OK, close the MQTT connection
close_mqtt()