import argparse
import os

from .library import library
from .identify import get_caller, is_imported

class BaseTask():
  """Base class for running and archiving any machine learning model.

  Whatever it is, it can be:
    * trained (as in: adjusting internal parameters to optimize some objective)
    * tested (as in: measuring performance of the model with some metric)
    * evaluated (as in: using the model on some new samples)
  and, as a bonus, model can be turned into an inference server, allowing fast
  predictions from some outside context (via IPC).

  This class provides a very generic interface for this, implementing:
    (1) a common command line interface for any model, which allows the user to
        define their model once and then run it in any "mode" they require with
        no changes to the code,
    (2) a history organization facility, which stores the "current" snapshot of
        user code in a git repository, which allows tracking the history of the
        experiment development.

  User should either subclass BaseTask directly (defining "train", "test" etc.)
  or import some existing implementation (backend.PytorchTask), create instance
  and run "main" at the end of their script. Everything else is handled by this
  class.
  """

  _library_import = False
  _imported_object = None

  def __init__(self):
    self.experiment = None
    self.snapshot = None

  # All backends have to implement these

  def train(self):
    raise NotImplementedError

  def test(self):
    raise NotImplementedError

  def eval(self, input):
    raise NotImplementedError

  def server(self):
    raise NotImplementedError

  # Interface

  def main(self, message=None):
    """Detect run mode and pass execution to a dedicated method.

    Script defining the specific task could be executed in 3 different ways:
    * directly called from the command line (most likely the experiment is
      being worked on),
    * by importlib during an import from the Library (common thing when running
      past versions of the experiment),
    * or by a direct import by the user in some other script.
    """
    # Detect being imported and behave accordingly if it's a library import
    if is_imported():
      if self.is_library_import():
        self.api_main()
    else:
      # otherwise assume being run from the command line
      return self.cli_main(message=message)

  def cli_main(self, message):
    """Training, testing, etc. directly from the CLI.

    Communicates with the library backend to add the model to a repository.
    """
    # Get the complete path to a file from which "main" was called
    this_path = get_caller(delta=1)
    # Folder name without extension is the name of the experiment
    this_dir, _ = os.path.split(this_path)
    _, exp_name = os.path.split(this_dir)
    # Fetch the experiment instance from the library
    self.experiment = library.get_experiment(exp_name)
    if not self.experiment:
      # Try creating a new one if it doesn't exist yet
      self.experiment = library.add_experiment(exp_name)
      if not self.experiment:
        raise RuntimeError("Unable to create a new experiment \"{}\".".format(exp_name))
    # Connect the instance with the local repository
    self.experiment.link_local_repo(this_path)
    # Check what command was requested via CLI
    args = self.cli_parse()
    if args.command == 'train':
      return self.cli_train(args=args, message=message)

  def cli_parse(self):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(prog='MAGEM')
    parser.add_argument('command', choices=['train']) # XXX just for now
    parser.add_argument('--force', action='store_true')
    return parser.parse_args()

  def cli_train(self, args, message):
    """Training command logic."""
    # Check for changes in the repository
    is_changed = self.experiment.check_changes()
    if is_changed:
      # Request creation of a new commit and snapshot
      self.snapshot = self.experiment.make_snapshot(message=message)
      self.train()
    elif args.force:
      # Forcing means retraining the last snapshot
      self.snapshot = self.experiment.get_last_snapshot()
      self.snapshot.reset()
      self.train()
    else:
      # By default, training is not allowed unless there were some changes
      print("No changes detected. If you wish to retrain the last version, run with --force")
      return

  def api_main(self):
    """Export the instance for external use through the library."""
    self.register_instance(self)

  @classmethod
  def is_library_import(cls):
    return BaseTask._library_import

  @classmethod
  def init_import(cls):
    BaseTask._library_import = True

  @classmethod
  def register_instance(cls, instance):
    BaseTask._imported_object = instance

  @classmethod
  def retrieve_instance(cls):
    instance = BaseTask._imported_object
    BaseTask._imported_object = None
    BaseTask._library_import = False
    return instance
