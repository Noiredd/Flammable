import os

import torch

from .task import BaseTask

class PytorchTask(BaseTask):
  """Basic, abstract skeleton of a PyTorch ML model.

  Following the basic assumption, there are 3 "states" that a model can be in.
  Those are: training, testing and evaluation. This class implements these in a
  modular, abstract way, requiring the user to define only the most fundamental
  functions for their model, but allowing them to override the default behavior
  on any level. This is done by defining a meta-algorithm for each state.

  Easiest to explain this on an example. Let's do it for "training" function.
  The most high level algorithm for training is:
    * create the data source
    * create the optimization criterion
    * create the optimizer
    * repeat the following for N epochs:
      * repeat the following for each data point (or batch)
        * pre-process the data sample
        * perform the forward pass for this sample, obtaining some output
        * perform the backward pass for this output and known label, obtaining
          some loss metric
        * update the model parameters accordingly
  PytorchTask encapsulates each of these behaviors in a specific function. Only
  the first 3 need to be defined by the user (along with the model itself), the
  rest is already implemented but in a very basic way (see metod "train"). User
  dealing with a simple task can therefore start experimenting right away. When
  the task becomes more complex, user can alter the algorithm on any level they
  want, simply by overriding the respective function.
  If the forward pass is no longer a trivial model __call__ but requires a more
  sophisticated procedure, one overrides forward_pass and everything will "just
  work". If a single learning "step" is no longer a simple function like above,
  the whole thing can be overridden. Even the "train" function can be redefined
  if need arises.

  Same concept applies to testing and evaluation behaviors (see the functions).
  """
  def __init__(self, model):
    super(PytorchTask, self).__init__()
    # Constituent objects
    self.model = model
    self.optim = None
    self.criterion = None
    self.train_data = {
      'snapshots': [],
      'metrics': {},
    }
    # Hyperparameters
    self.device = None
    self.epochs = None
