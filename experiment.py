import os

import git

class Experiment():
  """Manages the history and metadata of a single experiment.

  An experiment is given by a folder of a particular layout:
    exp_dir/
      repo        # git repository with experiment code snapshots
      assets      # all data produced by each version of the experiment
        fe3a3b7   # content produced by snapshot fe3a3b7
        32b6ee4
        e3cee37
        ...
      data.json   # metadata file (TODO)
  """

  def __init__(self, path):
    """Load experiment info given a path to its folder.

    Optionally allow passing Repo objects as arguments (faster sometimes).
    """
    if isinstance(path, git.repo.base.Repo):
      self.repo = path
    else:
      self.repo = git.Repo(os.path.join(path, 'repo'))
    # TODO: assert existence of all required items
    # TODO: metadata
  
  @classmethod
  def new(self, path):
    """Initialize a new experiment in a given directory.

    Creates all folders required and initializes the git repository.
    """
    os.mkdir(path)
    os.mkdir(os.path.join(path, 'repo'))
    os.mkdir(os.path.join(path, 'assets'))
    repo = git.Repo.init(os.path.join(path, 'repo'))
    return self(repo)


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
  
  def get_local(self):
    """Retrieve an existing repository or initialize a new one.

    In the latter case, also add it as a remote to the global repo.
    """
    try:
      repo = git.Repo(self.local_dir)
      print('obtained an existing repo')
    except git.exc.InvalidGitRepositoryError:
      repo = git.Repo.init(self.local_dir)
      self.global_exp.repo.create_remote('local', self.local_dir)
      print('created a new repo')
    return repo

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
    # synchronize with global repo (it's better to pull from the global side
    # rather than push from the local, because a local->global link allows
    # manipulation of the global (system-owned) repository by the user)
    link = self.global_exp.repo.remotes[0]
    link.pull('master')

  def get_identity(self):
    """Returns hexsha of the latest commit.

    task.Task uses this as its identity.
    """
    for commit in self.local_repo.iter_commits():
      # commits are stored latest-first
      return commit.hexsha


# Avoid a circular import by deferring the library load until after defining
# the classes - because library.py does import from this file as well.
# https://stackoverflow.com/a/40094439
from .library import library
