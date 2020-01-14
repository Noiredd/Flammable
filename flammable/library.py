import os

from .config import Config
from .experiment import Experiment

class Library():
  """Controls and owns all the experiments.

  Each experiment has its own folder in the storage (storage_path).
  Layout of this folder is defined in the Experiment class itself.
  """
  def __init__(self):
    """Load all the experiments."""
    self.config = Config()
    self.storage_path = self.config['data_path']
    self.experiments = self.load_experiments()

  def load_experiments(self):
    """Load experiments from every folder found in the storage_path."""
    candidates = [(f.path, f.name) for f in os.scandir(self.storage_path) if f.is_dir()]
    experiments = {}
    for path, name in candidates:
      try:
        experiment = Experiment(path)
      except:
        continue
      else:
        experiments[name] = experiment
    return experiments

  def add_experiment(self, name):
    """Create a new experiment with a given name."""
    if name not in self.experiments.keys():
      repo = Experiment.new(os.path.join(self.storage_path, name))
      self.experiments[name] = repo
      return repo
  
  def get_experiment(self, name):
    """Retrieve an experiment by name if it exists."""
    return self.experiments.get(name, None)


library = Library()

# Simple prevention against double instantiation. Of course, one can still do
#   lib2 = library.__class__()
# but... why?
del Library
