import os

from .config import config
from .experiment import Experiment

class Library():
  """Controls and owns all the experiments.

  Each experiment has its own folder in the storage (storage_path).
  Layouts of those folders are defined in the class Experiment.
  """
  instance = None
  @classmethod
  def set_instance(cls, instance):
    cls.instance = instance

  def __init__(self):
    """Initialize the import mechanism and load all the experiments."""
    if self.instance:
      raise RuntimeError("There can only be a single Library instantiated!")
    else:
      self.set_instance(self)
    # proceed with the launch
    self.is_importing = False # import mechanism
    self.imported_obj = None  # import mechanism
    self.storage_path = config['data_path']
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
    """Retrieve an experiment by name if it exists, otherwise create a new one."""
    repo = self.experiments.get(name, None)
    if not repo:
      repo = self.add_experiment(name)
    return repo


library = Library()
