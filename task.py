import sys

from ignite.engine import Events, create_supervised_trainer, create_supervised_evaluator

from .library import library
from .experiment import LocalView
from .identify import get_caller, is_imported

class Task():
  def __init__(self, model):
    self.model = model
    self.repo = None
    self.identity = None
    # determine capabilities depending on the passed arguments and defined functions

  def train(self):
    raise NotImplementedError

  def eval(self, input):
    raise NotImplementedError

  def validate(self, inputs):
    raise NotImplementedError

  def daemon(self):
    raise NotImplementedError
  
  def main(self, comment=None):
    """Decide what to do depending on how it was called.

    Script defining the task could've either been simply executed or imported.
    Behaviour in either case is significantly different. If the script is being
    executed, command line arguments might have been passed that control action
    to take, or a menu should be printed for the user to manually select it. If
    the script was imported, there are two possibilities: either the library is
    accessing a model snapshot (user is using the API), in which case the model
    should be served via a special channel (since the library can't and doesn't
    know how is the model literally named in the user's script), OR the user is
    importing the model themselves manually, in which case no additional action
    should be taken, as the user is in charge of retrieving the model by name.
    """
    # detect being imported
    if is_imported():
      # If it's the library who imports us, give it a handle to ourselves.
      # In other case - do nothing.
      if library.is_importing:
        library.import_task = self
      else:
        pass
      # No matter who, stop processing at this point.
      return
    # If it's not an import, the script must've been run manually. In this case
    # add self to library, acquire identity and run a selected task.
    self.repo = LocalView(get_caller())
    self.repo.commit(message=comment if comment else "no comment")
    self.identity = self.repo.get_identity()
    # Check if there are any CLI arguments or should we print a menu.
    try:
      command = self._args()
    except IndexError:
      command = self._menu()
    # Wherever the command came from, act accordingly. TODO.
    if command == 'train':
      self.train()
    elif command == 'daemon':
      self.daemon()
    else:
      print('Unknown command')

  def _args(self):
    """Check sys.argv to choose the action.

    For now the simplest possible check, TODO maybe use argparse
    """
    command = sys.argv[1]
    return command

  def _menu(self):
    """Prints a menu and queries the user for action."""
    print("Hello.")
    command = input("What would you like to do?")
    return command
