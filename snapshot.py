import json
import os

class Snapshot():
  """Data and metadata of a single version of an experiment.

  Each Snapshot corresponds to a specific point in the code history (commit).
  Each Snapshot stores at most a single trained version of an experiment (with
  the exception of multiple intermediate parameter files).

  Each Snapshot lives in its own folder ("root_path"), which is however created
  (and, possibly, destroyed) by its parent - an Experiment.
  An instance can be created in two semantic ways:
    * creating a new Snapshot entity, which an Experiment does when it creates
      a new commit,
    * loading a previously created Snapshot.
  This first way must be performed using the "create" class method, passing all
  the required data. This lets the instance constructor ("__init__") to simply
  accept the path to an existing data folder and load the data.

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
    # Mutable data entries (TODO)
    # Load everything from the data  file
    if not self._create_flag:
      self.deserialize()

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
      'comment'
    ]
    data = {key: self.__dict__[key] for key in keys}
    with open(os.path.join(self.root_path, self._data_file), 'w') as file:
      json.dump(data, file)

  def reset(self):
    """Remove all data, reverting the snapshot to the zero state."""
