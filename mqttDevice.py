# pip3 install paho-mqtt
# pip3 install pyjwt
# pip3 install pyjwt[crypto]

import paho.mqtt.client as mqtt
import jwt

import os
import subprocess

import json
from datetime import date, datetime, timedelta, timezone
import random
from timers import TimeoutFunction, IntervalFunction
path = os.path.dirname(os.path.abspath(__file__))
if not os.path.exists(path + '/temp'):
    os.makedirs(path + '/temp')

def now_ms(): 
  return int(datetime.now(timezone.utc).timestamp()*1000)

def _log(text):
  with open(path + '/temp/log.txt', 'a') as f:
    f.write(text + '\n')
  print(text)

class ClientState:
  MINIMUM_BACKOFF_TIME = 1
  MAXIMUM_BACKOFF_TIME = 32
  lastPublishTime = now_ms()
  shouldBackoff = False
  backoffTime = 1
  publishChain = False
  connected = False
  tokenExp = now_ms()
  initialised = False

class Config:
  deviceId = None
  projectId = 'trakkasset'
  registryId = 'asset-devices'
  region = 'asia-east1'
  privateKeyFile = 'rsa_private.pem'
  algorithm = 'RS256'
  tokenExpMins = 60
  msgInterval = 500
  debug = False

  interval = 30000
  
  topics = None
    
  def __init__ (self):
    with open(path + '/config.json') as config_file:
      config = json.load(config_file)
    device = {}
    if('device' in config):
      for k in config['device']:
        device[k] = config['device'][k]
    if('sensor' in config):
      if('interval' in config['sensor']): device['interval'] = config['sensor']['interval']
    self.change(device)
    
  def change (self, config):
    for k in config:
      setattr(self, k, config[k])
    _log('DEVICE SET CONFIG: {}'.format(config))
    if('deviceId' in config): self._setTopics()

  def _setTopics (self):
    class Topics:
      event = '/devices/{}/events'.format(self.deviceId)
      state = '/devices/{}/state'.format(self.deviceId)
      command = '/devices/{}/commands'.format(self.deviceId)
      config = '/devices/{}/config'.format(self.deviceId)
    self.topics = Topics()
  
  def client_id (self):
    client_id = 'projects/{}/locations/{}/registries/{}/devices/{}'.format(self.projectId, self.region, self.registryId, self.deviceId)
    return client_id

class TrakkMQTT:
  events = []
  eventsSent = []
  state = False
  client = None
  sensor = None
  cmd = {}
  _loop = None

  def __init__ (self, sensor = None):
    _log('DEVICE INIT.')
    if(sensor): self.sensor = sensor
    self.config = Config()
    self.client = mqtt.Client(client_id=self.config.client_id(), clean_session=False)
    self.client.tls_set(keyfile=self.config.privateKeyFile)
    self.client.state = ClientState()
    self.client.on_connect = self._on_connect
    self.client.on_publish = self._on_publish
    self.client.on_disconnect = self._on_disconnect
    self.client.on_message = self._on_message
    self.client.state.initialised = True
    with open(path + '/cmd.json') as cmd_file:
      self.cmd = json.load(cmd_file)

  def _createJwt(self):
    token = {
      'iat': datetime.now(timezone.utc),
      'exp': datetime.now(timezone.utc) + timedelta(minutes = self.config.tokenExpMins),
      'aud': self.config.projectId
    }
    self.client.state.tokenExp = token['exp'].timestamp() * 1000
    if(self.config.privateKeyFile.startswith('.')):
      privateKeyFile_path = path + self.config.privateKeyFile[1:]
    elif(self.config.privateKeyFile.startswith('/')):
      privateKeyFile_path = self.config.privateKeyFile
    else:
      privateKeyFile_path = path + '/' + self.config.privateKeyFile

    with open(privateKeyFile_path, 'r') as f:
      privateKey = f.read()
    return jwt.encode(token, privateKey, algorithm = self.config.algorithm)

  def _endClient(self):
    _log('DEVICE MQTT CLIENT; Closing connection')
    self.client.disconnect()
    self.client.loop_stop()
    self.client.state.publishChain = False
    self.client.state.connected = False

  def _publishEvent(self):
    if(not self.client.state.connected):
      _log('DEVICE; waiting for client...')
      def tryAgain():
        if(self.client.state.connected):
          self._publishEvent()
        else:
          _log('DEVICE; Still no client... giving up')
          self._endClient()
      TimeoutFunction(tryAgain, 5000)
    else:
      if(len(self.events) > 0):
        payload = None
        # convert bool or tuple to compatible types
        if(isinstance(self.events[0], bool)): self.events[0] = int(self.events[0])
        if(isinstance(self.events[0], tuple)): self.events[0] = list(self.events[0])
        
        if(isinstance(self.events[0], (str, int, float))): payload = self.events[0]
        elif(isinstance(self.events[0], (list, dict))): payload = json.dumps(self.events[0])
        else: _log("DEVICE; Event data of type {} is not acceptable, must be: str, int, float, list, dict, tuple, bool".format(type(self.events[0])))

        if(payload != None):
          publish = self.client.publish(self.config.topics.event, payload, qos = 1)
          self.eventsSent.append({ 
            'mid': publish.mid, 
            'payload': self.events[0], 
            'ts0': now_ms()
          })
          del self.events[0]
          self.client.state.lastPublishTime = now_ms()

      elif(len(self.eventsSent) > 0):
        if(self.eventsSent[0]['ts0'] < now_ms() - 5000):
          if(self.config.debug): _log('DEVICE; Retry event[mid]:' + str(self.eventsSent[0]['mid']))
          payload = None
          delay = self.eventsSent[0]['ts0'] - now_ms()
          if(isinstance(self.eventsSent[0]['payload'], (str, int, float))):
            payload = str(self.eventsSent[0]['payload']) + ',' + delay
          elif(isinstance(self.eventsSent[0]['payload'], (list))):
            payload = self.eventsSent[0]['payload'] + [delay]
            payload = json.dumps(payload)
          elif(isinstance(self.eventsSent[0]['payload'], dict)):
            payload = self.eventsSent[0]['payload'].copy()
            payload['_delay'] = delay
            payload = json.dumps(payload)
          else: _log("DEVICE; Unexpected type in eventsSent[0]['payload']")

          if(payload != None):
            publish = self.client.publish(self.config.topics.event, payload, qos = 1)
            # update mid
            self.eventsSent[0]['mid'] = publish.mid
            # move first event to back
            self.eventsSent = self.eventsSent[1:] + self.eventsSent[0:1]
            self.client.state.lastPublishTime = now_ms()
      if(self.state):
        if(self.config.debug): _log('DEVICE SENDING STATE; {}'.format(self.state))
        payload = json.dumps(self.state)
        self.client.publish(self.config.topics.state, payload, qos = 1)
        self.state = False
      self._publishAsync()

  def _publishAsync(self):
    if(len(self.events) == 0):
      eventsFilePath = path + '/temp/events.txt'
      if os.path.exists(eventsFilePath):
        # load to memory
        with open(eventsFilePath, 'r') as f:
            for line in f:
                try:
                    jsonEvent = json.loads(line)
                    self.events.append(jsonEvent)
                except ValueError:
                    self.events.append(line)
        # remove the file
        os.remove(eventsFilePath)

      # stateFilePath = path + '/state.txt'
      # if os.path.exists(stateFilePath):
      #   with open(stateFilePath, 'r') as f:
      #     self.state = f.read()
      #   os.remove(stateFilePath)


    if(self.client.state.backoffTime >= self.client.state.MAXIMUM_BACKOFF_TIME):
      _log('DEVICE; Backoff time is too high.')
      self._endClient()
      return
    elif(len(self.events) == 0 and self.client.state.lastPublishTime != 0 and 
      now_ms() - self.client.state.lastPublishTime > self.config.interval * 2):
      _log('DEVICE; Nothing coming into queue.')
      self._endClient()
      return
    else:
      self.client.state.publishChain = True
      publishDelayMs = self.config.msgInterval - min((0, (now_ms() - self.client.state.lastPublishTime)))
      if(self.client.state.shouldBackoff):
        publishDelayMs = 1000 * (self.client.state.backoffTime + random.random())
        self.client.state.backoffTime *= 2
      TimeoutFunction(self._publishEvent, publishDelayMs)

  def _on_connect(self, client, userdata, flags, rc):
    if(rc == 0):
      client.state.connected = True
      client.subscribe(self.config.topics.command + '/#', qos=0)
      client.subscribe(self.config.topics.config, qos=1)
      _log('DEVICE MQTT CLIENT; Connected')
      if(not client.state.publishChain): 
        self._publishAsync()
    elif(rc == 1):
      _log('DEVICE MQTT CLIENT; Connection refused: incorrect protocol version')
    elif(rc == 2):
      _log('DEVICE MQTT CLIENT; Connection refused: invalid client identifier')
    elif(rc == 3):
      _log('DEVICE MQTT CLIENT; Connection refused: server unavailable')
    elif(rc == 4):
      _log('DEVICE MQTT CLIENT; Connection refused: bad username or password')
    elif(rc == 5):
      _log('DEVICE MQTT CLIENT; Connection refused: not authorised')
    else:
      _log('DEVICE MQTT CLIENT; Connection failed: unknown error')

  def _on_message(self, client, userdata, msg):
    if(bool(msg.payload)):
      payload = None
      try:
        payload = json.loads(str(msg.payload.decode('utf-8')))
      except:
        payload = str(msg.payload.decode('utf-8'))
      
      if(msg.topic == self.config.topics.config):      
        _log("DEVICE RECEIVED CONFIG; {}".format(payload))
        if(isinstance(payload, dict)):
          dc = {}
          sc = {}
          if('device' in payload): dc = payload['device']
          if('sensor' in payload):
            sc = payload['sensor']
            if('interval' in sc):
              dc['interval'] = sc['interval']
          if('debug' in payload):
            if(not 'debug' in dc): dc['debug'] = payload['debug']
            if(not 'debug' in sc): sc['debug'] = payload['debug']
          if('interval' in payload):
            if(not 'interval' in dc): dc['interval'] = payload['interval']
            if(not 'interval' in sc): sc['interval'] = payload['interval']
          if(self.sensor): self.sensor.configure(sc)
          self.config.change(dc)
          if('interval' in dc): self.start()
        TimeoutFunction(self._getState, 2000)
      if(msg.topic.startswith(self.config.topics.command)):
        subtopic = msg.topic[len(self.config.topics.command):]
        if(not subtopic): subtopic = '#'
        if(self.config.debug): _log("DEVICE RECEIVED COMMAND {}; {}".format(subtopic, payload))
        if(subtopic == '/DEVICE'):
          self.command(payload)
        elif(subtopic == '/SENSOR'):
          if(self.sensor): self.sensor.command(payload)
        elif(subtopic == '#'):
          if(isinstance(payload, dict)):
            if('device' in payload): self.command(payload['device'])
            if('sensor' in payload and self.sensor): self.sensor.command(payload['sensor'])
          elif(isinstance(payload, str)):
            self.command(payload)
            if(self.sensor): self.sensor.command(payload)
    else:
      _log('DEVICE RECEIVED; {}, BLANK PAYLOAD'.format(msg.topic))

  def _on_disconnect(self, unused_client, unused_userdata, rc):
    if(rc != 0): 
      # Unexpected disconnect occurred, the next loop iteration will wait with
      # exponential backoff.
      self.client.state.shouldBackoff = True
      _log('DEVICE MQTT CLIENT; Disconnect error: ' + mqtt.error_string(rc))
    self.client.state.connected = False
    _log('DEVICE MQTT CLIENT; Disconnected')
    
  def _on_publish(self, unused_client, unused_userdata, mid):
    self.client.state.shouldBackoff = False
    self.client.state.backoffTime = self.client.state.MINIMUM_BACKOFF_TIME
    ind = None 
    for i, e in enumerate(self.eventsSent):
      if(e['mid'] == mid):
        if(self.config.debug): _log('DEVICE PUBLISHED; ' + str(e['payload']))
        ind = i
        del self.eventsSent[i]
    if(ind == None):
      _log('DEVICE ERROR; could not find published mid:' + id)

  def _setClient(self):
    secFromExpire = (self.client.state.tokenExp - now_ms()) / 1000
    if((not self.client.state.connected) or secFromExpire < 60):
      self.client.state.lastPublishTime = now_ms()
      if(self.client.state.connected):
        _log('DEVICE; Refreshing token after before expires in {} seconds'.format(secFromExpire))
        self.client.disconnect()
        self.client.state.connected = False
        TimeoutFunction(self._setClient, 2000)
      else:
        _log('DEVICE MQTT CLIENT; Attempt connect')
        self.client.loop_stop()
        self.client.username_pw_set( username = 'unused', password = self._createJwt() )
        try: 
          self.client.connect('mqtt.googleapis.com', port=8883, keepalive=900)
        except:
          _log('DEVICE MQTT CLIENT; Could not connect')
        self.client.loop_start()
  
  def _getState(self):
    if(self.sensor):
      s = self.sensor.state()
    else:
      s = {}
    s['device'] = {
      'tokenExpMins': self.config.tokenExpMins,
      'msgInterval': self.config.msgInterval,
      'debug': self.config.debug
    }
    _log('STATE {}'.format(s))
    self.state = s

  def start (self):
    interval = 30000
    if(hasattr(self.config, 'interval')): interval = min(self.config.interval, 600000)
    _log('DEVICE CLIENT LOOP; {} ms'.format(interval))
    if(self._loop): self._loop.interval(interval)
    else: self._loop = IntervalFunction(self._setClient, interval)
  
  def stop (self):
    if(self._loop): self._loop.cancel()
  
  def command (self, cmd):
    if(isinstance(cmd, dict)):
      _log('DEVICE RECEIVED UNKNOWN CMD: {}'.format(cmd))
    elif(isinstance(cmd, str)):
      if(cmd in self.cmd):
        _log('DEVICE SYSTEM CMD; ' + cmd)
        run = subprocess.run(self.cmd[cmd], capture_output=True, text=True)
        if(run.stdout): _log(run.stdout)
        if(run.stderr): _log(run.stderr)
      else:
        _log('DEVICE RECEIVED UNKNOWN CMD: {}'.format(cmd))

if __name__ == "__main__":
  mqttClient = TrakkMQTT()
  mqttClient.start()