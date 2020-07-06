
# For dht sensor on omega2 install:
# opkg install dht-sensor

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from timers import TimeoutFunction, IntervalFunction
from mqttDevice import TrakkMQTT

path = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(path + '/temp'):
    os.makedirs(path + '/temp')

def _log(text):
  with open(path + '/temp/log.txt', 'a') as f:
    f.write(text + '\n')
  print(text)

class Sensor:
  debug = False
  _config = None
  _loop = None

  def __init__(self):
    _log('SENSOR INIT; {}, {}'.format(os.path.abspath(__file__), datetime.now(timezone.utc).isoformat()))
    
    # load config
    conf_path = path + '/config.json'
    if(os.path.exists(conf_path)):
      with open(conf_path) as json_file:
        j = json.load(json_file)
        self.configure(j['sensor'])

  def _readDevice (self):
    if('gpio' in self._config and 'type' in self._config):
      try:
        device_command = ['dht-sensor', str(self._config['gpio']), self._config['type'], 'json']
        # dummy command for testing on PC
        # device_command = ['echo', '{ "temperature": 22.0000, "humidity": 24.10000 }']

        deviceReading = json.loads(subprocess.check_output(device_command))
        deviceReading['ts'] = datetime.now(timezone.utc).isoformat()
        if self.debug: _log('SENSOR EVENT; ' + json.dumps(deviceReading))
        with open(path + '/temp/events.txt', 'a') as f:
          f.write(json.dumps(deviceReading) + '\n')
      except subprocess.CalledProcessError as e:
        _log('ERROR; Subprocess error: \n')
        _log(e.output)

  def _setLoop (self): 
    interval = 30000
    if('interval' in self._config): interval = self._config['interval']
    _log('SENSOR LOOP; {} ms'.format(interval))
    if(self._loop): self._loop.interval(interval)
    else: self._loop = IntervalFunction(self._readDevice, interval)

  def configure (self, cfg: dict):
    if(not self._config): 
      self._config = { 
        'interval': 30000
      }
    for k in cfg:
      self._config[k] = cfg[k]
      if(k == 'debug'): self.debug = bool(cfg[k])
    _log('SENSOR SET CONFIG; {}'.format(cfg))
    if('interval' in cfg and self._loop): self._setLoop()
  
  def command (self, cmd: [str, dict]):
    if(isinstance(cmd, dict)):
      _log('SENSOR RECEIVED UNKNOWN CMD; {}'.format(cmd))
    elif(isinstance(cmd, str)):
      if(cmd == 'READ'):
        if(self.debug): _log('SENSOR CMD READ; ')
        self._readDevice()
      else:
        _log('SENSOR RECEIVED UNKNOWN CMD; {}'.format(cmd))

  def state (self) -> dict: 
    s = {
      'sensor': self._config
    }
    if(self.debug): _log('SENSOR STATE; {}'.format(self._config))
    return s

  def start (self):
    self._setLoop()
  
  def stop (self):
    if(self._loop): self._loop.cancel()



if __name__ == "__main__":
  _log('--- START TRAKK IOT --- ' + datetime.now(timezone.utc).isoformat())
  sensor = Sensor()
  sensor.start()
  mqttClient = TrakkMQTT(sensor)
  mqttClient.start()
  def run():
    if(sensor.debug): _log('CHECK RUN LOOPS')
    if(not sensor._loop.running): 
      _log('SENSOR RUN LOOP INACTIVE')
      sensor.start()
    if(not mqttClient._loop.running): 
      _log('DEVICE RUN LOOP INACTIVE')
      mqttClient.start()
  IntervalFunction(run, 30000)
    