import datetime
import importlib
import json
import os
import random
import sys

import git

from .snapshot import Snapshot

class Experiment():
  """Manages the history and metadata of a single experiment.

  An experiment is given by a folder of a particular layout:
    exp_dir/
      repo/       # git repository with experiment code
      snapshots/  # detailed data and assets produced by each snapshot
        20190926-123819-ebyjb/
        20190926-124033-xvznd/
        ...

  This object controls the global repository of the experiment, as well as the
  snapshot storage in the form of individual folders. It does not manage data
  directly, leaving that job to each Snapshot instance, which it only spawns.
  Additionally, if given a path to the local repository, it can handle commits
  and pushes between local and global repositories. This allows creating Snap-
  shots.
  """

  GIT_EXCLUDE = ['.git', '__pycache__']

  @classmethod
  def new(self, path):
    """Initialize a new experiment in a given directory.

    Creates all folders required and initializes the git repository.
    Most likely to be called by the library in its configured repo folder.
    """
    os.mkdir(path)
    os.mkdir(os.path.join(path, 'repo'))
    os.mkdir(os.path.join(path, 'snapshots'))
    repo = git.Repo.init(os.path.join(path, 'repo'))
    return self(path)

  def __init__(self, path):
    """Load experiment info given a path to its folder."""
    if not self.verify(path):
      raise RuntimeError('Not a valid Experiment directory.')
    self.repo_path = os.path.join(path, 'repo')
    self.repo = git.Repo(self.repo_path)
    self.global_repo = self.repo
    self.snap_path = os.path.join(path, 'snapshots')
    self.local_path = None
    self.local_file = None
    self.local_repo = None
    self.changed_files = None
    self.removed_files = None
    self.snapshot_names, self.snapshot_ids = self.find_snapshots()

  def verify(self, path):
    """Ensure the given path points to a well-formed experiment directory."""
    if not os.path.isdir(os.path.join(path, 'repo')):
      return False
    if not os.path.isdir(os.path.join(path, 'snapshots')):
      return False
    return True

  def find_snapshots(self):
    """Go through the snapshots folder and return the list of valid subfolders."""
    names = []
    ids = set()
    for item in os.scandir(self.snap_path):
      if item.is_dir:
        names.append(item.name)
        ids.add(item.name.split('-')[-1])
    return sorted(names), ids

  def get_snapshot(self, name_or_id):
    """Return a Snapshot instance by its name or ID, if one exists."""
    if name_or_id in self.snapshot_names:
      return Snapshot(os.path.join(self.snap_path, name_or_id))
    elif name_or_id in self.snapshot_ids:
      # find name which matches the given ID
      for name in self.snapshot_names:
        if name_or_id in name:
          return self.get_snapshot(name)
    else:
      return None

  def get_last_snapshot(self):
    """Return the most recently created Snapshot instance."""
    name = self.snapshot_names[-1]
    return self.get_snapshot(name)

  def import_snapshot(self, snapshot:Snapshot):
    """Retrieve the Task that was executed at the given snapshot.

    This alters the global repository by performing a checkout and a reset.
    No data will be lost, as long as it has been committed.
    """
    if snapshot.uid not in self.snapshot_ids:
      raise RuntimeError('This snapshot does not belong to the Experiment!')
    Task.init_import()
    # check out the relevant commit
    self.repo.head.reference = self.repo.commit(snapshot.commit_sha)
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
    # before returning the object, link it with the Snapshot instance
    task_object.snapshot = snapshot
    return task_object

  def has_local_repo(self):
    """Is there a valid instance of the local repository?"""
    return all((self.local_path, self.local_file, self.local_repo))

  def link_local_repo(self, caller):
    """Set up the local repository in the directory of the calling script.

    Fetches an existing repository if present, otherwise initializes a new
    one and connects it with the global version (via global's remote).
    """
    self.local_path, self.local_file = os.path.split(caller)
    try:
      repo = git.Repo(self.local_path)
    except git.exc.InvalidGitRepositoryError:
      # TODO: ensure there is not a mismatch between this repo and global
      repo = git.Repo.init(self.local_path)
      self.global_repo.create_remote('local', self.local_path)
    finally:
      self.local_repo = repo

  def check_changes(self):
    """Check for changes in the local repository.

    Requires a live instance of a local repository (link_local_repo).
    """
    if not self.has_local_repo():
      raise RuntimeError("No local repository connected. Aborting...")
    self.changed_files = []
    self.removed_files = []
    # modified files
    diff = self.local_repo.index.diff(None)
    for d in diff:
      if d.change_type == 'D':
        self.removed_files.append(d.a_path)
      elif d.a_path == d.b_path:
        self.changed_files.append(d.a_path)
      else:
        UserWarning("Diff a_path != b_path ({} vs {})".format(d.a_path, d.b_path))
        self.changed_files.append(d.a_path)
        self.changed_files.append(d.b_path)
    # new files
    for f in self.local_repo.untracked_files:
      if f in self.GIT_EXCLUDE:
        continue
      if any(f.startswith(rule) for rule in self.GIT_EXCLUDE):
        continue
      self.changed_files.append(f)
    # return just the answer (don't make the lists public)
    if self.changed_files or self.removed_files:
      return True
    else:
      return False

  def make_snapshot(self, message):
    """Commit code changes and create a new snapshot.

    If check_changes hasn't been called yet (this can be checked: changed and
    removed file lists will be None), will call it. Otherwise will reuse old
    results.
    Requires a live instance of a local repository (link_local_repo).
    """
    if not self.has_local_repo():
      raise RuntimeError("No local repository connected. Aborting...")

    # Scan for changes if we haven't already
    if self.changed_files is None or self.removed_files is None:
      self.check_changes()

    # Commit code
    if self.changed_files or self.removed_files:
      # add to staging area
      if self.changed_files:
        self.local_repo.index.add(self.changed_files)
      if self.removed_files:
        self.local_repo.index.remove(self.removed_files)
      # commit to the local repository
      self.local_repo.index.commit(message)
      # pull from the global side
      remote = self.global_repo.remotes[0]
      remote.pull('master')

    # Create the snapshot
    # generate a unique ID for the snapshot
    uid = generate_id()
    while uid in self.snapshot_ids:
      uid = generate_id()
      # probability of ending this loop is the lower, the more IDs are already
      # recorded, until there are 11881376 snapshots and it will never complete
    # get a reference to the related (most recent) commit
    for commit in self.repo.iter_commits():
      break
      # they're stored latest-first - stopping after the first iteration leaves
      # said reference under "commit"
    # get its SHA
    hexsha = commit.hexsha
    # generate the timestamp from the commit datetime
    commit_time = commit.committed_datetime
    time_offset = commit_time.utcoffset()
    local_time = commit_time - time_offset
    timestamp = '{}{:0>2}{:0>2}-{:0>2}{:0>2}{:0>2}'.format(
      local_time.year,
      local_time.month,
      local_time.day,
      local_time.hour,
      local_time.minute,
      local_time.second
    )
    # create the locating subfolder for the snapshot
    snapshot_name = '{}-{}'.format(timestamp, uid)
    snapshot_path = os.path.join(self.snap_path, snapshot_name)
    os.mkdir(snapshot_path)
    # create the object
    snapshot = Snapshot.create(
      root_path=snapshot_path,
      uid=uid,
      commit_sha=hexsha,
      timestamp=timestamp,
      filename=self.local_file,
      comment=message,
    )
    # add to the registry
    self.snapshot_names.append(snapshot_name)
    self.snapshot_ids.add(uid)
    return snapshot


def generate_id():
  B = 26
  N = 5
  return ''.join(
    chr(ord('a') + random.randint(0, B-1)) for _ in range(N)
  )

# Avoid a circular import by deferring the Task load until after defining
# the classes - because task.py might import from this file as well.
# https://stackoverflow.com/a/40094439
from .task import BaseTask as Task
