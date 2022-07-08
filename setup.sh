# Using a Raspberry Pi OS Lite (32-bit) (Bullseye 2022-04-04) base image

# Update the OS
sudo apt-get update -y; sudo apt-get upgrade -y

# Install utilities. Needed for Raspbian Lite
sudo apt-get install git pip vim -y
sudo apt-get install python3-dev python-dev python-setuptools python3-setuptools cl-cffi python3-cffi libffi6 cython3 python3-scipy python3-smbus python3-rpi.gpio python3-numpy python3-serial python3-pybind11 -y

# Install GrovePi bits
## Ignore errors when the script is building scipy
## Runing GrovePi scripts using python3 after this works
curl -kL dexterindustries.com/update_grovepi | bash

# Manual Step: Enable I2C with raspi-config

# Install sunlight sensor packages
sudo pip3 install seeed-python-si114x

# Setup AWS IoT Device SDK
sudo apt-get install cmake libssl-dev -y
cd ~
sudo pip3 install awsiotsdk
git clone https://github.com/aws/aws-iot-device-sdk-python-v2.git

# Install BrightPi pckages
#curl -sSL https://pisupp.ly/brightpicode | bash
