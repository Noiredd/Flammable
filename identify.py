import inspect
import os

def get_caller(delta=0):
  """Find the file from which the calling function was invoked.
  
  Traverses upwards the call stack via inspect, stopping as soon as it finds
  an invocation from outside *this* module. There should be at least 3 frames
  in the stack:
    this module: identify.get_caller
    outer module: whoever called identify.get_caller()
    module of interest: whoever called the caller
  other things potentially follow.

  Optional argument "delta" allows identifying caller's caller, or caller's
  caller's caller: pass a positive integer to travel that many steps further
  up the call stack.
  """
  for i, frame in enumerate(inspect.stack()):
    if i == 2 + delta:
      break
  return os.path.abspath(frame.filename)

def is_imported():
  """Was the caller imported by another module or executed from the shell?

  In the case of shell execution, the call stack should look like this:
    this module: is_imported
    task.py: Task.main
    outer script: <module>
  When importing, various importlib functions will appear later. Therefore
  it is enough to check the length of a call stack to know the answer.
  """
  return len(inspect.stack()) > 3
