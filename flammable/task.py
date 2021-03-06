import argparse
import os

from .identify import get_caller, is_imported
from .library import library
from .snapshot import DummySnapshot

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
    # By default, start with no link to the owner, but already have a fake
    # snapshot instance, just in case of direct (non-CLI) usage. If needed,
    # this will be replaced with a full Snapshot later.
    self.experiment = None
    self.snapshot = DummySnapshot()

  # All backends have to implement these

  def train(self):
    raise NotImplementedError

  def test(self):
    raise NotImplementedError

  def eval_path(self, input_path, output_path):
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
    """Parse command line input and execute the entire logic.

    Uses the library backend to retrieve or create an Experiment instance that
    this task belongs to, along with the local repository where the user is
    working on it. Then makes a series of checks to execute the logic depending
    on the specific command passed by the user. There are 4 main commands, this
    is their (short and rough - see specific functions for details) overview:
      * "train":  if there were changes in task code, commit them, create a new
                  snapshot, and start training; otherwise exit, unless some
                  special flag (--retrain, --force) was passed,
      * "test":   if there were no changes in task code, or a special --ignore
                  flag was passed, get the last snapshot and test it; otherwise
                  exit,
                  TODO: keep task state (e.g. initialized, trained, tested, not
                  tested etc.) to ensure we're not testing an untrained model;
                  TODO: reintroduce --retest flag;
      * "eval":   logic is the same as in "test",
                  TODO: rework after completing the above 2 todos;
      * "server": TBD
      + "amend":  only commits changes (if any) onto an existing snapshot,
      + "status": checks the status of the repository/snapshot,
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
    # Check which command was requested via CLI
    args = self.cli_parse()
    if args.command == 'train':
      return self.cli_train(args=args, message=message)
    elif args.command == 'test':
      return self.cli_test(args=args)
    elif args.command == 'eval':
      return self.cli_eval(args=args)
    elif args.command == 'server':
      raise NotImplementedError("This is not ready yet, TODO!")

  def cli_parse(self):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(prog='FLAMMABLE')
    parser.add_argument('command', choices=['train', 'test', 'eval'])
    parser.add_argument('infile', nargs='?', help="[Evaluation only]\
      Path to the input file.")
    parser.add_argument('outfile', nargs='?', help="[Evaluation only]\
      Path to the output file.")
    parser.add_argument('other', nargs='*', help='(unused)')
    tflags = parser.add_mutually_exclusive_group(required=False)
    tflags.add_argument('--retrain', action='store_true', help="[Training only]\
      Reset the existing snapshot and train it from scratch.")
    tflags.add_argument('--force', action='store_true', help="[Training only]\
      Create a new snapshot even if there were no changes in the code.")
    parser.add_argument('--ignore', action='store_true', help="[Testing only]\
      Ignore that the code was changed since the training, test anyway.")
    return parser.parse_args()

  def cli_train(self, args, message):
    """Training command logic.

    The main assumption is that a Snapshot instance represents a single trained
    version of the experiment (as the code looked like at some point in time).
    A single version of the code can be trained multiple times, but each of the
    resulting models is encapsulated by a separate Snapshot instance. Therefore
    we employ the following logic:
      * if there were changes in the code: commit them, create a Snapshot, run
        "train",
      * if there were no changes but --retrain was given: fetch the previous
        Snapshot, reset it, and run "train" on it again,
      * if there were no changes but --force was given: create a new Snapshot
        referring to the most recent commit, and run "train".
    """
    # Check for changes in the repository
    is_changed = self.experiment.check_changes()
    if is_changed:
      # Request creation of a new commit and snapshot, and train
      self.snapshot = self.experiment.make_snapshot(message=message)
      self.train()
    elif args.retrain:
      # Reset and train the last snapshot
      self.snapshot = self.experiment.get_last_snapshot()
      self.snapshot.reset()
      self.train()
    elif args.force:
      # Force creating a new snapshot, and train
      self.snapshot = self.experiment.make_snapshot(message=message)
      self.train()
    else:
      # By default, training is not allowed unless there were some changes
      print("No changes detected.",
            "If you wish to train a new snapshot anyway, run with --force.",
            "If you wish to retrain the last snapshot, run with --retrain.")
      return

  def cli_test(self, args):
    """Testing command logic.

    As with the "cli_train", logic is bound with the current state of the repo.
    Usually, a model is first trained and later tested - code is not expected
    to change between the two operations. Of course, it may happen that after
    calling "train" on a model, some modifications have been made. Or even that
    another Snapshot has been created and trained. But since in such situations
    it is amgibuous which version should be brought to test, the recommended
    usage is to import the specific Snapshot to test via API. When using the
    CLI, it is assumed that the code hasn't changed between train and test. So:
      * if there were no changes in the code: get the last Snapshot, run "test",
      * if there were changes but --ignore was given: get the last Snapshot, run
        "test".
    """
    # Check for changes in the repository
    is_changed = self.experiment.check_changes()
    if not is_changed or args.ignore:
      # Test the last Snapshot
      self.snapshot = self.experiment.get_last_snapshot()
      self.test()
    else:
      print("Changes detected. Which snapshot do you wish to test?",
            "If you wish to test the last snapshot, run with --ignore.",
            "If you wish to test some other snapshot, use the python API to",
            "select and import it, and call its test() method.")

  def cli_eval(self, args):
    """Evaluation command logic.

    Logic is bound with the repo state in exactly the same way as in "cli_test".
    """
    # Check for changes in the repository
    is_changed = self.experiment.check_changes()
    if not is_changed or args.ignore:
      # Load the last Snapshot
      self.snapshot = self.experiment.get_last_snapshot()
      # Evaluate the model on given arguments
      self.eval_path(input_path=args.infile, output_path=args.outfile)
    else:
      print("Changes detected. Which snapshot do you wish to evaluate?",
            "If you wish to eval the last snapshot, run with --ignore.",
            "If you wish to eval some other snapshot, use the python API to",
            "select and import it, and call its eval() or eval_path() method.")

  def api_main(self):
    """Export the instance for external use through the library."""
    self.register_instance(self)

  # API import mechanics

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
