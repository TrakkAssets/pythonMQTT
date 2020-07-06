# Trakk IoT Device examples

## PythonMQTT

Check that you have Python3 installed, our scripts are written and tested on Python 3.8.2

`$ python3 --version`

`Python 3.8.2`

Our Python scripts are designed to be tested on PC and setup and tested to run on the Onion Omega2 development platform. The Omega2 provides a user friendly entry level platform for IoT testing and prototyping.

Follow our addtional steps to get an Omega2+ up and running, ready to deploy your testing scripts. [Omega2+ Setup](./omega2.md)

## Approach

Event publishing scripts show our recommended approach to on-device queue, backoff and publishing to Trakk Assets via Google Cloud MQTT endpoint.

Separate scripts are included for reading sensor data and the MQTT client.
Event data received from sensors is stored in a temporary file, later to be retrieved and sent via a the MQTT class.
This approach allows maximum independance of the different scripts and allows the MQTT client to be used across multiple applications.

## Configuration

Start with a 'sensor' script (eg: `dht.py`) and a 'device' script (eg: `mqtt_device.py`) and edit them to configure your specific device. 

Configuration for both the 'device' and 'sensor' is saved in `config.json`.

A few key points to get you started:

- Scripts have configuration boolean variable `debug` that can be turned on to get verbose command line and logging output. By default scripts will log output to `./temp/log.txt`
- Trakk Assets expects to receive data in comma separated or JSON format
- To make use of separate 'sensor' and 'device' scripts setup your 'sensor' script write each telemetry event as a line in `./temp/events.txt`. The 'device' script will pickup data from that file and publish to the IoT endpoint.
- Pass the 'sensor' object to the 'device' script when it is initialised. The 'device' script will call various methods in response to server instructions and changes in device status:
  - `configure(cfg)` - will be called to pass updated sensor config
  - `command(cmd)` - will be called to pass commands from the server
  - `state ()` - will be called to obtain state / status of the sensor, for reporting back to the server
- In order to connect with Trakk servers the 'device' script must authenticate with a signed JSON Web Token. Read more below
- By default the latest configuration will be retreived from the server each time you connect and will override default values.
- For security reasons, we recommend that system level device commands are configured only in firmware eg: `cmd.json`.
- Ensure that script can be executed from an outside working directory, to aid automatic start and logging

## Device Authentication

Trakk IoT uses public key authentication (through Google Cloud). The device uses a private key to sign a JSON Web Token (JWT) which is passed to Google Cloud as proof of the device's identity.
In order to connect to our servers you will need to generate a private/public key pair. You can use 'openssl' to generate an RSA key pair using the following commands:

`$ openssl genpkey -algorithm RSA -out rsa_private.pem -pkeyopt rsa_keygen_bits:2048`

`$ openssl rsa -in rsa_private.pem -pubout -out rsa_public.pem`

Save the private key `rsa_private.pem` on your device and specify the path to this file in the 'device' config. Upload the public key `rsa_public.pem` into Trakk Assets when registering your device.

## Install script dependancies

Each script will have some code libraries as dependencies which will need to be installed. Install commands are generally outlined at the at top of each script.

For example mqttDevice.py has paho-mqtt, pyjwt and pyjwt-crypto as dependancies. 

`$ pip3 install paho-mqtt pyjwt pyjwt[crypto]`

## Test

We recommend that you always test scripts from command line with `debug` on to pickup any errors early and ensure the system is working correctly.

By example: `~$ python3 /root/iot_devices/python/dht.py`