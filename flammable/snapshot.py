import json
import os

class Snapshot():
  """Data and metadata of a single version of an experiment.

  Each Snapshot corresponds to a specific point in the code history (commit).
  Each Snapshot stores at most a single trained version of an experiment (but
  multiple intermediate model files).

  Each Snapshot lives in its own folder ("root_path"), which is however created
  (and, possibly, destroyed) by its parent - an Experiment.
  An instance can be created in two semantic ways:
    * creating a new Snapshot entity, which an Experiment does when it creates
      a new commit,
    * loading a previously created Snapshot.
  This first way must be performed using the "create" class method, passing all
  the required data. This lets the instance constructor ("__init__") accept the
  path to an existing data folder and load the data.

  This mechanism is key to Snapshot atomicity: because there can exist multiple
  live instances of a single snapshot (e.g. one is still being trained while
  the user constructs an inference server to play around with it), one instance
  writing data after the other has written as well results in race conditions.
  Therefore, a Snapshot will always reload its state (overwriting the instance
  data) before performing any writes, to ensure that a write will not corrupt
  the previously written data.
  """

  _create_flag = False
  _data_file = 'snapshot.json'

  @classmethod
  def create(cls, root_path, uid, commit_sha, timestamp, filename, comment):
    # Create a new (empty) object in a "raw creation" mode
    # (the normal initializer tries to load data which wouldn't exist yet)
    cls._create_flag = True
    instance = cls(root_path)
    cls._create_flag = False
    # Fill with initial values externally
    instance.uid = uid
    instance.commit_sha = commit_sha
    instance.timestamp = timestamp
    instance.filename = filename
    instance.comment = comment
    # Force first serialization and return the complete object
    instance.serialize()
    return instance

  def __init__(self, root_path):
    """Pass path to the containing folder."""
    self.root_path = root_path
    # Immutable data entries
    self.uid = None
    self.commit_sha = None
    self.timestamp = None
    self.filename = None
    self.comment = None
    # Mutable data entries
    self.train_data = {}  # anything produced during training, epoch by epoch
    self.val_data = {}    # results of intermediate tests during training
    self.test_data = {}   # results of a test
    self.model_files = [] # saved model parameters
    self.custom_data = {} # whatever the user might like to save
    # Load everything from the data file
    if not self._create_flag:
      self.deserialize()

  def make_path(self, filename):
    """Prepend a given filename with the absolute path to the Snapshot folder.

    Useful to control saving location of any assets produced by the model.
    """
    return os.path.join(self.root_path, filename)

  def deserialize(self):
    """Load from the associated data file, overwriting the current state."""
    with open(os.path.join(self.root_path, self._data_file), 'r') as file:
      data = json.load(file)
    for key, val in data.items():
      self.__dict__[key] = val

  def serialize(self):
    """Write all the internal data structures to a JSON file."""
    keys = [
      'uid',
      'commit_sha',
      'timestamp',
      'filename',
      'comment',
      'train_data',
      'val_data',
      'test_data',
      'model_files',
      'custom_data',
    ]
    data = {key: self.__dict__[key] for key in keys}
    with open(os.path.join(self.root_path, self._data_file), 'w') as file:
      json.dump(data, file)

  def reset(self):
    """Remove all data, reverting the snapshot to the zero state."""
    # Clear mutable data, but leave the immutables intact
    self.train_data = {}
    self.val_data = {}
    self.test_data = {}
    self.model_files = []
    self.custom_data = {}
    # Remove all the physical assets
    for item in os.scandir(self.root_path):
      os.remove(item.path)
    # Reserialize
    self.serialize()

  def train_storage(self):
    """Get a handle to train_data that writes there safely."""
    return SnapshotView(self, self.train_data)

  def val_storage(self):
    """Get a handle to val_data that writes there safely."""
    return SnapshotView(self, self.val_data)

  def test_storage(self):
    """Get a handle to test_data that writes there safely."""
    return SnapshotView(self, self.test_data)

  def custom_storage(self):
    """Get a handle to custom_data that writes there safely."""
    return SnapshotView(self, self.custom_data)

  def register_model_file(self, filename):
    """Add a given model file to the internal registry."""
    # TODO: remember about locking&reading when doing the atomic stuff
    self.model_files.append(filename)
    self.serialize()

  def fetch_last_model_file(self):
    """Return the full path to the last saved model file."""
    try:
      filename = self.model_files[-1]
      return self.make_path(filename)
    except IndexError:
      return None


class SnapshotView():
  """Context manager that allows atomic writes to the Snapshot."""
  def __init__(self, parent:Snapshot, target:dict):
    self.parent = parent
    self.data = target
    self.ready = False

  def store(self, name, value):
    """Store a value directly under the given name."""
    # ...but only when the context has been entered (and locks acquired etc.)
    if not self.ready:
      raise RuntimeError("SnapshotView is a context manager. Never use it directly!")
    # Do not ask for permission - overwrite the old entry if necessary
    self.data[name] = value

  def append(self, name, value):
    """Append a single data value to the list under a given name."""
    # ...but only when the context has been entered (and locks acquired etc.)
    if not self.ready:
      raise RuntimeError("SnapshotView is a context manager. Never use it directly!")
    # If this is the first entry under this key - create it
    try:
      target = self.data[name]
    except KeyError:
      target = []
      self.data[name] = target
    target.append(value)

  def __enter__(self):
    # Currently does nothing, but later will do locks&reads for atomic writes
    self.ready = True
    return self

  def __exit__(self, *args, **kwargs):
    # Ensure the Snapshot serializes, later will also release locks
    self.parent.serialize()
    self.ready = False


class DummySnapshot(Snapshot):
  """Ad-hoc Snapshot that is neither bound to a commit nor a folder.

  It does not serialize, it does not create nor delete anything in its folder.
  It only collects metrics like normal, allowing the user to extract and use
  them.

  This comes very handy when using a Task directly: without main(), or when
  importing it without library. If the API that connects the instance with the
  experiment (and thus the global repository and assets folder) is missing, a
  normal Snapshot instance is not created, and thus backend, via a Logger
  instance, would not be able to store anything.
  In the case of an external import (if main is still called), a Dummy instance
  is automatically created, allowing data to be collected.
  """
  def __init__(self):
    super(DummySnapshot, self).__init__('.')

  # Explicitly disable serialization
  def serialize(self):
    pass

  def deserialize(self):
    pass

  # The original reset deletes data
  def reset(self):
    self.train_data = {}
    self.val_data = {}
    self.test_data = {}
    self.model_files = []
    self.custom_data = {}
