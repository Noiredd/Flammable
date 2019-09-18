import os
import inspect
import json
import shutil

CONFIG_FILE = 'config.json'

def validate_data_path(data_path):
  """Make sure the requested data path will be okay for use.

  Return False when:
    path does not exist AND cannot be created with mkdir
    path cannot be written to
  otherwise, creates the folder and returns True.
  Additionally, will issue a textual warning if the folder is not empty.
  """
  if os.path.isdir(data_path):
    try:
      open(os.path.join(data_path, 'test'), 'w').close()
    except:
      print("Error: this path is not writable!")
      return False
    os.remove(os.path.join(data_path, 'test'))
  else:
    try:
      os.mkdir(data_path)
    except:
      print("Error: this path does not exist and cannot be created!")
      return False
  if os.listdir(data_path):
    print("Warning: the requested folder is not empty!")
  return True

def load_config(config_path):
  """Loads existing config file."""
  with open(config_path, 'r') as config_file:
    config = json.loads(config_file.read())
  return config

def new_config(config_path):
  """Creates a new config file. Asks the user for things."""
  print("Where would you like to store the experiments data?")
  print("Your current path is: {}".format(os.getcwd()))
  data_path = input()
  data_path = os.path.abspath(data_path)
  if not validate_data_path(data_path):
    exit(-1)
  print("This path evaluates to: {}".format(data_path))
  config = {'data_path': data_path}
  with open(config_path, 'w') as config_file:
    config_file.write(json.dumps(config))
  return config

def get_config():
  """Tries to load config, creates a new one upon failure."""
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
