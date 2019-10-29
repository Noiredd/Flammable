import sys

from .experiment import LocalView
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
    self.repo = None
    self.identity = None

  # All backends have to implement these

  def train(self):
    raise NotImplementedError

  def test(self):
    raise NotImplementedError

  def eval(self, input):
    raise NotImplementedError

  def server(self):
    raise NotImplementedError

  # Common behaviors

  def main(self, comment=None):
    """Decide what to do depending on how it was called.

    Script defining the task could've either been simply executed or imported.
    Behaviour in either case is significantly different. If the script is being
    executed, the user has passed some command line arguments informing what to
    do. There are two options if the script was imported: EITHER the library is
    accessing a model snapshot (user is using the API), in which case the model
    (BaseTask descendant) is anonymous from the library's point of view, and so
    it has to be passed to it via some special channel (in this case it will be
    stored as a class-instance member, because the library has direct access to
    to class instance); ALTERNATIVELY the user is importing the model manually,
    in which case no additional action should be taken, as the user should know
    the literal name of the object they're importing.
    """
    # detect being imported
    if is_imported():
      # If it's the library who imports us, store a static (class-level) handle
      # to the current instance. In other case do nothing.
      if self.is_library_import():
        self.register_instance(self)
        # TODO: Shouldn't we in this case also link it with its parent Experiment???
        # e.g. user imports some old object to test it again
      else:
        pass
      # No matter who, stop processing at this point.
      return
    # If it's not an import, the script must've been run manually. In this case
    # add self to library, acquire identity and run a selected task.
    self.repo = LocalView(get_caller())
    self.repo.make_snapshot(message=comment if comment else "none")
    self.identity = self.repo.get_identity()
    # Parse the CLI arguments (TODO: argparse)
    command = sys.argv[1]
    if command == 'train':
      self.train()
    elif command == 'test':
      self.test()
    elif command == 'eval':
      self.eval(sys.argv[2])
    elif command == 'server':
      self.server()
    else:
      print('Unknown command')

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
