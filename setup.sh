# Using a Raspberry Pi OS Lite (32-bit) (Bullseye 2022-04-04) base image

# Update the OS
sudo apt-get update -y; sudo apt-get upgrade -y

# Install utilities. Needed for Raspberry Pi OS Lite
sudo apt-get install git pip vim -y
sudo apt-get install python3-dev python-dev python-setuptools python3-setuptools cl-cffi python3-cffi libffi6 cython3 python3-scipy python3-smbus python3-rpi.gpio python3-numpy python3-serial python3-pybind11 -y

# Install GrovePi bits
## Ignore errors when the script is building scipy
## Runing GrovePi scripts using python3 after this works
curl -kL dexterindustries.com/update_grovepi | bash

# Manual Step: Enable I2C with raspi-config

# Install sunlight sensor packages
sudo pip3 install seeed-python-si114x

# Install AWS SDKs
sudo apt-get install python3-boto3 cmake libssl-dev -y
sudo pip3 install awsiotsdk