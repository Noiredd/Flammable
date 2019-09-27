import datetime
import importlib
import json
import os
import random
import sys

import git

class Experiment():
  """Manages the history and metadata of a single experiment.

  An experiment is given by a folder of a particular layout:
    exp_dir/
      repo        # git repository with experiment code snapshots
      assets      # all data produced by each snapshot of the experiment
        20190926-123819-ebyjb
        20190926-124033-xvznd
        ...
      data.json   # metadata file (TODO)
  """

  def __init__(self, path):
    """Load experiment info given a path to its folder."""
    if not self.verify(path):
      raise RuntimeError('Not a valid Experiment directory.')
    self.repo_path = os.path.join(path, 'repo')
    self.repo = git.Repo(self.repo_path)
    self.data_path = os.path.join(path, 'data.json')
    self.snapshots = self.load_data()
    # TODO: allow retrieval of snapshots by date, by ID, by whatever
    self.ids = set(snapshot.sid for snapshot in self.snapshots)

  def verify(self, path):
    """Ensure the given path points to a well-formed experiment directory."""
    if not os.path.isdir(os.path.join(path, 'repo')):
      return False
    if not os.path.isdir(os.path.join(path, 'repo')):
      return False
    if not os.path.isfile(os.path.join(path, 'data.json')):
      return False
    return True

  def load_data(self):
    """Load snapshots' metadata from a JSON file."""
    snapshots = []
    with open(self.data_path, 'r') as source:
      for line in source.readlines():
        snapshots.append(Snapshot.from_json(line.strip('\n')))
    return snapshots

  def save_data(self):
    """Save snapshots' metadata to a JSON file."""
    with open(self.data_path, 'w') as target:
      for snapshot in self.snapshots:
        target.write(snapshot.to_json())
        target.write('\n')

  def create_snapshot(self, message, filename):
    """Create an experiment snapshot and append to the list.

    TODO: This should be atomic with respect to the on-disk data file, in cases
    when multiple instances of the same Experiment are in use (perhaps the user
    trains multiple versions of the experiment at the same time).
    """
    # first we need to know the SHA of the most recent commit
    for commit in self.repo.iter_commits():
      hexsha = commit.hexsha
      break # they're stored latest-first, so we can stop immediately
    # create the object
    snapshot = Snapshot.create(
      parent=self,
      comment=message,
      hexsha=hexsha,
      filename=filename
    )
    # add to the registry
    self.snapshots.append(snapshot)
    self.save_data()
    self.ids.add(snapshot.sid)
    return snapshot

  def import_snapshot(self, snapshot):
    """Retrieves the Task that was executed at the given snapshot.

    This alters the global repository by performing a checkout and a reset.
    No data will be lost, as long as it has been committed.
    """
    if snapshot.sid not in self.ids:
      raise RuntimeError('This snapshot does not belong to the Experiment!')
    Task.init_import()
    # check out the relevant commit
    self.repo.head.reference = self.repo.commit(snapshot.hexsha)
    self.repo.head.reset(index=True, working_tree=True)
    # import the correct file from the correct location
    backup_path = sys.path
    sys.path = [self.repo_path]
    module_name, _ = os.path.splitext(snapshot.filename)
    # the imported module triggers the other end of the mechanism
    importlib.import_module(module_name)
    # return to the original master head
    self.repo.head.reference = self.repo.heads[0]
    self.repo.head.reset(index=True, working_tree=True)
    # retrieve the imported object and clean up
    task_object = Task.retrieve_instance()
    sys.path = backup_path
    return task_object

  @classmethod
  def new(self, path):
    """Initialize a new experiment in a given directory.

    Creates all folders required and initializes the git repository.
    """
    os.mkdir(path)
    os.mkdir(os.path.join(path, 'repo'))
    os.mkdir(os.path.join(path, 'assets'))
    open(os.path.join(path, 'data.json'), 'w').close()
    repo = git.Repo.init(os.path.join(path, 'repo'))
    return self(path)


class LocalView():
  """Controls a local version of the experiment and its connection with global.

  This object shall only be constructed by a Task, which will pass it a path to
  the script which was ran by the user from a local repository. This will cause
  initialization (or loading) of a local repository. Then, the object will call
  Library to provide a link with the global version of the repository. Not only
  this allows pushing commits from local to global, but also lets Task send any
  results to the global repo to be stored as metadata.
  """
  EXCLUDE = ['.git', '__pycache__']

  def __init__(self, caller):
    """Set up the local repository and obtain link with the global version."""
    self.local_dir, self.call_file = os.path.split(caller)
    _, repo_name = os.path.split(self.local_dir)
    self.global_exp = library.get_experiment(repo_name)
    self.local_repo = self.get_local()
    # TODO: assert there isn't a mismatch between repos - e.g. we're not trying
    # to overwrite a repo, or pull between desynchronized repos
    self.snapshot = None

  def get_local(self):
    """Retrieve an existing repository or initialize a new one.

    In the latter case, also add it as a remote to the global repo.
    """
    try:
      repo = git.Repo(self.local_dir)
    except git.exc.InvalidGitRepositoryError:
      repo = git.Repo.init(self.local_dir)
      self.global_exp.repo.create_remote('local', self.local_dir)
    return repo

  def make_snapshot(self, message):
    """Commit changes and synchronize the global state."""
    if self.commit(message):
      self.synchronize()
    self.snapshot = self.global_exp.create_snapshot(message, self.call_file)

  def commit(self, message):
    """Commit any changes to the local repository."""
    # check for and collect the changes
    is_changed = len(self.local_repo.index.diff(None)) > 0
    has_untracked = len([
      f for f in self.local_repo.untracked_files
      if f not in self.EXCLUDE and not any(f.startswith(ex) for ex in self.EXCLUDE)
    ]) > 0
    should_commit = is_changed or has_untracked
    # commit changes (if any) to the local repository
    if should_commit:
      self.local_repo.index.add([
        item for item in os.listdir(self.local_dir) if item not in self.EXCLUDE
      ])
      self.local_repo.index.commit(message)
    return should_commit

  def synchronize(self):
    """Synchronize with the global repository.

    It's better to pull from the global side (with local as a remote) because
    if global was local's remote, the user could (even accidentally) make some
    damage on the library side.
    """
    link = self.global_exp.repo.remotes[0]
    link.pull('master')

  def get_identity(self):
    """Returns a timestamp and internal ID of the current snapshot."""
    return '{}-{}'.format(self.snapshot.timestamp, self.snapshot.sid)


class Snapshot():
  """Metadata of a single run of an experiment.

  Each snapshot corresponds to one commit in the experiment repository. This is
  not a 1:1 relation however, as multiple snapshots can be taken at one commit.
  A snapshot represents a run of the experiment: there can be multiple repeated
  runs with the same settings, there might be several runs of different scripts
  at the same commit. User might even define their task to accept external args
  (e.g. from CLI) and perform experiments by making runs at different settings.
  All of this information is to be stored in a snapshot which provides mappings
  to specific commits and filenames, enabling later retrieval from the library.
  TODO: enable storing output information (e.g. final metrics) in the snapshot.
  """
  def __init__(self, sid, timestamp, comment, hexsha, filename):
    self.sid = sid
    self.timestamp = timestamp
    self.comment = comment
    self.hexsha = hexsha
    self.filename = filename
    self.metrics = {} # TODO, as well as settings maybe

  @classmethod
  def create(cls, parent:Experiment, comment, hexsha, filename):
    """Generate unique ID and construct a new Snapshot."""
    timestamp = cls.get_datetime()
    # ensure uniqueness of the ID
    sid = cls.generate_id()
    while sid in parent.ids:
      sid = cls.generate_id()
      # probability of ending this loop is the lower, the more IDs are already
      # recorded, until there are 11881376 snapshots and it will never complete
    # now we can build the object
    return cls(
      sid=sid,
      timestamp=timestamp,
      comment=comment,
      hexsha=hexsha,
      filename=filename
    )

  @classmethod
  def from_json(cls, string):
    """Deserialize the object from its JSON representation."""
    items = json.loads(string)
    return cls(
      sid=items[0],
      timestamp=items[1],
      comment=items[2],
      hexsha=items[3],
      filename=items[4],
    )

  def to_json(self):
    """Serialize to JSON."""
    return json.dumps([
      self.sid,
      self.timestamp,
      self.comment,
      self.hexsha,
      self.filename
    ])

  @staticmethod
  def generate_id():
    """Generate a random 5-digit base-26 number, represent as string."""
    B = 26
    N = 5
    number = random.randint(0, B**N - 1)
    digits = []
    for i in range(N):
      d = number % B
      digits.append(d)
      number -= d
      number //= B
    return ''.join(
      chr(ord('a') + d) for d in reversed(digits)
    )

  @staticmethod
  def get_datetime():
    """Return the current date & time as a string."""
    now = datetime.datetime.now()
    return '{}{:0>2}{:0>2}-{:0>2}{:0>2}{:0>2}'.format(
      now.year,
      now.month,
      now.day,
      now.hour,
      now.minute,
      now.second
    )


# Avoid a circular import by deferring the library load until after defining
# the classes - because library.py does import from this file as well.
# https://stackoverflow.com/a/40094439
from .library import library
from .task import Task
