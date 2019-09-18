import os
import inspect
import json
import shutil

CONFIG_FILE = 'config.json'

def load_config(config_path):
  with open(config_path, 'r') as config_file:
    config = json.loads(config_file.read())
  return config

def new_config(config_path):
  """Creates a new config file. Asks the user for things."""
  print("Where would you like to store the experiments data?")
  print("Your current path is: {}".format(os.getcwd()))
  data_path = input()
  data_path = os.path.abspath(data_path)
  print("This path evaluates to: {}".format(data_path))
  config = {'data_path': data_path}
  with open(config_path, 'w') as config_file:
    config_file.write(json.dumps(config))
  return config

def get_config():
  this_path = os.path.abspath(inspect.getfile(inspect.currentframe()))
  this_dir, _ = os.path.split(this_path)
  config_path = os.path.join(this_dir, CONFIG_FILE)
  if os.path.exists(config_path):
    if os.path.isfile(config_path):
      return load_config(config_path)
    else:
      shutil.rmtree(config_path)
  return new_config(config_path)

config = get_config()
