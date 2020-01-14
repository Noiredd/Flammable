import os
import inspect
import json

class Config():
  """Manages creation and retrieval of the configuration file."""
  CONFIG_FILE = 'config.json'

  def __init__(self):
    self.path = self.get_config_path()
    self.data = self.load_config()
    if not self.data:
      self.data = self.create_config()
      self.save_config(self.data)

  def get_config_path(self):
    """Return the standard absolute location of the configuration file."""
    this_path = os.path.abspath(inspect.getfile(inspect.currentframe()))
    this_dir, _ = os.path.split(this_path)
    return os.path.join(this_dir, self.CONFIG_FILE)

  def load_config(self):
    """Try to load the config dict, return None upon failure."""
    try:
      with open(self.path, 'r') as config_file:
        cfg = json.loads(config_file.read())
      return cfg
    except FileNotFoundError:
      return None
    else:
      raise ImportError("Unknown error occurred when loading the config.")

  def create_config(self):
    """Create a new configuration, querying the user for input.

    This will be executed when the framework is first run: at setup.
    """
    print("Flammable is not configured yet -- let's do that now.")
    print("Where would you like to store the experiments data?")
    print("Your current path is: {}".format(os.getcwd()))
    data_path = input()
    data_path = os.path.abspath(data_path)
    if not self.validate_data_path(data_path):
      exit(-1)  # validate_data_path has already printed a message
    print("This path evaluates to: {}".format(data_path))
    cfg = {'data_path': data_path}
    return cfg

  def validate_data_path(self, data_path):
    """Make sure the requested data path will be okay for use.

    Return False when:
      path does not exist AND cannot be created with mkdir
      path cannot be written to
    otherwise, creates the folder and returns True.
    Warns if the folder is not empty.
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

  def save_config(self, cfg):
    """Store the given config dict in the standard location."""
    with open(self.path, 'w') as config_file:
      config_file.write(json.dumps(cfg))

  def __getitem__(self, key):
    return self.data[key]
