import inspect
import os

def get_caller(delta=0):
  """Find the file from which the calling function was invoked.

  Uses the inspect module to traverse upwards the call stack a number of steps.
  In the simplest case, the stack looks like this:
    [FILE]        [FUNCTION]
    identify.py   get_caller
    task.py       Task.cli_main
    task.py       Task.main
    script.py     <module>
  If "cli_main" is asking to find its caller, obviously its immediate parent is
  "main", also in task.py - this is what get_caller finds by default (delta=0).
  However, in this particular case we might know that the actually interesting
  file is located several frames higher up the stack. Passing a positive delta
  allows introducing a correction - it informs the function of how many extra
  steps should be taken before returning the caller info.
  """
  if delta < 0:
    raise RuntimeError("Delta must be positive!")
  for i, frame in enumerate(inspect.stack()):
    if i == 2 + delta:
      return os.path.abspath(frame.filename)

def is_imported():
  """Was the caller imported by another module or executed from the shell?

  In the case of shell execution, the call stack should look like this:
    [FILE]        [FUNCTION]
    identify.py   is_imported
    task.py:      Task.main
    script.py     <module>
  When importing, some more functions will appear later. They will be either
  importlib machinery (in the case of an API import), or another script's frame
  (if the user is importing in their other script). Therefore it is enough to
  check the length of a call stack to know the answer.
  """
  return len(inspect.stack()) > 3
