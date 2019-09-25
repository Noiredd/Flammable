import os

import git

from .config import config

class Library():
  """Controls and owns all the experiments.

  Content is organized in the data folder as follows:
    data/
      experiment_1/
        repo      # git repository with experiment code snapshots
        assets    # all data produced by each version of the experiment
          fe3a3b7 # content produced by snapshot fe3a3b7
          32b6ee4
          e3cee37
          ...
      experiment_another/
        repo
        assets
          ...
      ...
  """
  def __init__(self):
    """Load all known experiments."""
    self.is_importing = False # import mechanism
    self.import_task = None   # import mechanism
    self.data_path = config['data_path']
    e_names = os.listdir(self.data_path)
    e_paths = [os.path.join(self.data_path, c) for c in e_names]
    e_flags = [True for path in e_paths if os.path.isdir(path)]
    self.experiments = {
      name: Experiment(path)
      for name, path, flag in zip(e_names, e_paths, e_flags)
      if flag
    }

  def add_experiment(self, name):
    """Create a new experiment with a given name."""
    if name not in self.experiments.keys():
      repo = Experiment.new(os.path.join(self.data_path, name))
      self.experiments[name] = repo
      return repo
  
  def get_experiment(self, name):
    """Retrieve an experiment by name if it exists, otherwise create a new one."""
    repo = self.experiments.get(name, None)
    if not repo:
      repo = self.add_experiment(name)
    return repo


class Experiment():
  """Controls and owns a single global repository and all its data"""
  def __init__(self, path):
    """Load repository info from a given absolute path.

    Path is expected to contain "repo" and "assets" subfolders.
    """
    self.repo = git.Repo(os.path.join(path, 'repo'))
    try:
      iter_commits = self.repo.iter_commits()
    except ValueError:
      # can happen if there are no commits yet
      self.commits = []
    else:
      self.commits = [commit.hexsha for commit in iter_commits]
  
  @classmethod
  def new(self, path):
    """Initialize a new repository in a given directory.

    Creates all folders required.
    """
    os.mkdir(path)
    os.mkdir(os.path.join(path, 'repo'))
    os.mkdir(os.path.join(path, 'assets'))
    repo = git.Repo.init(os.path.join(path, 'repo'))
    return self(path)


class Local():
  """Represents a local, "current" version of the experiment.

  This object holds two repositories *directly*:
    the local version (self.local_repo) containing the user's work,
    the global version (self.global_repo) stored in the library.
  """
  EXCLUDE = ['.git', '__pycache__']

  def __init__(self, caller):
    """Shall be created by a Task object.

    The owner shall pass the result of a "identify.get_caller" call.
    """
    self.local_dir, _ = os.path.split(caller)
    _, self.repo_name = os.path.split(self.local_dir)
    self.local_repo = self.get_local()
    self.global_repo = self.get_global()
    self.head = None
  
  def get_local(self):
    """Retrieve an existing repository or initialize a new one."""
    try:
      repo = git.Repo(self.local_dir)
    except git.exc.InvalidGitRepositoryError:
      repo = git.Repo.init(self.local_dir)
    return repo

  def get_global(self):
    """Query the library for a global version of the repo."""
    global library
    experiment = library.get_experiment(self.repo_name)
    return experiment.repo

  def commit(self, message):
    """Commit any changes to the local repository and syncs with library."""
    # collect the changes
    is_changed = len(self.local_repo.index.diff(None)) > 0
    has_untracked = len([
      f for f in self.local_repo.untracked_files
      if f not in self.EXCLUDE and not any(f.startswith(ex) for ex in self.EXCLUDE)
    ]) > 0
    # commit changes (if any) to the local repository
    if is_changed or has_untracked:
      self.local_repo.index.add([
        item for item in os.listdir(self.local_dir) if item not in self.EXCLUDE
      ])
      self.local_repo.index.commit(message)
    else:
      return
    # synchronize with global repo
    self.sync()

  def sync(self):
    """Sync local repository with global (library) version."""
    # TODO: remove assumption that the local repo is persistent (doesn't change location)
    if not self.global_repo.remotes:
      self.global_repo.create_remote('local', self.local_dir)
    link = self.global_repo.remotes[0]
    link.pull('master')

  def get_identity(self):
    """Returns hexsha of the latest commit.

    task.Task uses this as its identity.
    """
    for commit in self.local_repo.iter_commits():
      # commits are stored latest-first
      return commit.hexsha


library = Library()
