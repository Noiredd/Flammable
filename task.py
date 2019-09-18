import sys

from ignite.engine import Events, create_supervised_trainer, create_supervised_evaluator

class Task():
  def __init__(self, model):
    self.model = model
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
    If executed, some command line arguments may or may not have been added.
    If imported, this must be detected and behavior be accordingly different.
    """
    # add self to library
    # acquire identity
    # detect being imported, return self then
    # otherwise try parsing sys args
    # if none, present the menu
  
  def _args(self):
    """Checks sys.argv to choose the action."""
    try:
      arg = sys.argv[1]
    except IndexError:
      return None
    # parse the arg (simply: "train", "eval")

  def _menu(self):
    """Prints a menu and queries the user for action."""
    print("Hello.")
    p = input("What to do?")
