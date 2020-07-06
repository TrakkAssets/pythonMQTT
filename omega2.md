# Trakk IoT setup for Omega2+

The following setup will be required to get an Omega2+ up and running, and connected to Trakk Assets

## Recommended: setup to run from external storage

The omega2 has limited storage space. We recommend that you utilised an external storage device SD card (Omega2+) or USB (via mini dock) and setup for boot. Follow tutorial on onion.io to setup an external storage overlay.

[Boot from external storage](https://docs.onion.io/omega2-docs/boot-from-external-storage.html)

Ensure to check that the filesystem has mounted correctly

`$ df -h`

You should see your external storage mounted to /overlay

eg: `/dev/mmcblk0p1  14.5G  40.2M  13.7G  0%  /overlay`

## Install linux packages

Install and configure required packages; 
- python3 and pip
- python3-cryptography; required for pyjwt
- git; if you want to deploy your code via a repository

Update 'opkg' feeds to include OpenWRT

`$ vi /etc/opkg/distfeeds.conf`

Uncomment the line starting

`src/gz openwrt_packages http://do...`

Install packages

`$ opkg install python3 python3-pip python3-cryptography`

`$ opkg install git git-http`

Configure git

`$ git config --global user.name "FIRST_NAME LAST_NAME"`

`$ git config --global user.email "EMAIL_ADDRESS"`

Upgrade pip and setuptools

`$ pip3 install --upgrade pip setuptools wheel`

## Clone the our repository or your branch

`$ git clone https://mappazzoIOT@bitbucket.org/trakkassets/iot_devices.git iot_devices`

## Install script dependancies

For example mqttDevice.py has paho-mqtt, pyjwt and pyjwt-crypto as dependancies. Install commands are generally outlined at the at top of each script.

`pip3 install paho-mqtt`

`pip3 install pyjwt`

`pip3 install pyjwt[crypto]`

## Install the private key file

Generate the key pair on your PC

`$ openssl genpkey -algorithm RSA -out rsa_private.pem -pkeyopt rsa_keygen_bits:2048`

`$ openssl rsa -in rsa_private.pem -pubout -out rsa_public.pem`

Copy the private key `rsa_private.pem` to the Omega2:

`$ scp ./rsa_private.pem root@omega-XXXX.local:/root/iot_devices/python/rsa_private.pem`

Remember to upload the public key `rsa_public.pem` into Trakk Assets when registering your device.

## Set to 'auto run' on Omega2

Edit the rc.local file to start scripts on load

`$ vi /etc/rc.local`

By example, you would insert the following line to read data using the DHT sensor script

`python3 /root/iot_devices/python/dht.py &`

Note that your script is likely to work on an infinate loop and so you must not forget to add the ampersand (&) to the end of the command.