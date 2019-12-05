import os

import torch

from .logging import Logger
from .task import BaseTask

class PytorchTrainable():
  """Mixin for training-related abstractions.

  Realizes the most high-level idea of a training process, defined as follows:
    * create the data source
    * create the optimization criterion
    * create the optimizer
    * repeat the following for N epochs:
      * iterate over the data source, each time doing the following:
        * prepare the data sample
        * perform the forward pass for this sample, obtaining some output
        * perform the backward pass for this output and the original sample,
          obtaining some loss metric, and back-propagate it
        * update the model parameters
  Might be best to read it from the bottom, as the most low-level functions are
  higher up, and the most abstract algorithm is below.

  When deriving from PytorchTrainable (or rather PytorchTask) one still needs
  to implement some of the functions - see "User code" area.

  Warning: due to dependencies on several self-bound attributes and methods
  (e.g. self.forward() or self.device) this class alone makes little sense. It
  shall be used only when mixed into the PytorchTask composite class.
  """

  # User code

  def get_training_data(self):
    """User code: should return a training data loader.

    By default it is expected that the loader will yield 2-tuples containing
    a training sample and a corresponding label. This expectation is realized
    by prepare_train and forward_pass_train (see the code).
    """
    raise NotImplementedError

  def get_criterion(self):
    """User code: should return a loss function object."""
    raise NotImplementedError

  def get_optimizer(self):
    """User code: should return an optimizer object."""
    raise NotImplementedError

  # Meta-algorithm

  def prepare_train(self, sample):
    """Default sample preprocessing before feeding to the model at training."""
    data, label = sample
    data = data.to(self.device)
    label = label.to(self.device)
    return data, label

  def forward_train(self, sample):
    """Default forward pass during training."""
    data, _ = sample
    output = self.forward(data)
    return output

  def backward(self, output, sample):
    """Default backward pass."""
    _, label = sample
    loss = self.criterion(output, label)
    loss.backward()
    return loss

  def iteration(self, sample):
    """Default meta-algorithm for a single iteration over the training dataset."""
    self.model.train()
    self.optimizer.zero_grad()
    self.sample = self.prepare_train(sample)
    self.output = self.forward_train(self.sample)
    self.loss = self.backward(self.output, self.sample)
    self.optimizer.step()

  def parse_losses(self, loss):
    """Unpack whatever came out of the backward pass for automatic logging."""
    return {'loss': loss.item()}

  def epoch(self, dataset):
    """Default meaning of an 'epoch' (single iteration over the dataset).

    Additionally does some basic book-keeping using Logger.
    """
    logger = Logger('average')
    for self.iter_i, sample in enumerate(dataset):
      self.iteration(sample)
      losses = self.parse_losses(self.loss)
      logger.log(losses)
    logger.store_train(self.snapshot)
    # TODO: validation pass
    # TODO: every_n_epochs/n_iters helper functions

  def train(self):
    """Default training meta-algorithm."""
    self.model.to(self.device)
    # Initialize required components (user-defined)
    data = self.get_training_data()
    self.criterion = self.get_criterion()
    self.optimizer = self.get_optimizer()
    # Run the outer loop
    for self.epoch_i in range(self.epochs):
      self.epoch(data)
    # TODO: summary book-keeping
    self.save_model('final.pt')


class PytorchTask(PytorchTrainable, BaseTask):
  """Basic, abstract skeleton of a PyTorch-based ML model.

  Following the basic assumption, there are 3 "states" that a model can be in.
  Those are: training, testing and evaluation. This class (or rather the mixins
  that it consists of) defines these states in an abstract, modular way: by
  implementing a default meta-algorithm and breaking it down into several basic
  building block functions, each realizing a specific portion of the algorithm.
  The user can either use the simple, default version of the algorithm, or they
  can define their own. Due to the highly abstract structure, one can override
  the algorithm on any level needed, from the small changes e.g. "what it means
  to forward-propagate a data sample" to a complete rewrite of the algorithm.

  Sometimes it is only needed to add something to the existing function, not
  rewrite it from scratch. The suggested way of doing this is to override the
  function, implement the desired behavior there and then use super() to call
  the original function.

  See documentation on each individual mixin for details.
  """
  def __init__(self, model):
    super(PytorchTask, self).__init__()
    # Constituent objects
    self.model = model
    # Training-time objects
    self.criterion = None
    self.optimizer = None
    self.dataset = None
    self.epoch_i = None
    self.iter_i = None
    self.sample = None
    self.output = None
    self.loss = None
    # Hyperparameters
    self.device = None
    self.epochs = None

  # General model abstractions

  def forward(self, data):
    """Default forward pass through the model."""
    return self.model(data)

  # General utilities

  def save_model(self, filename):
    """Save the current state of the model under a given file.

    This is not just a convenience wrapper around the usual torch.save(). Most
    importantly, it registers this model file in the Snapshot's storage, which
    allows loading it by name later (and causes the physical file to be located
    in the corresponding Snapshot's folder).
    """
    path = self.snapshot.make_path(filename)
    with open(path, 'wb') as file:
      torch.save(self.model.state_dict(), file)
    self.snapshot.register_model_file(filename)

  def load_model(self, filename=None):
    """Load the model state from a given file, or load the last available one."""
    if filename:
      path = self.snapshot.make_path(filename)
      if os.path.isfile(path):
        self.model.load_state_dict(torch.load(path))
      else:
        raise RuntimeError("There is no such model file in the Snapshot folder!")
    else:
      path = self.snapshot.fetch_last_model_file()
      if path:
        self.model.load_state_dict(torch.load(path))
      else:
        raise RuntimeError("This Snapshot has no saved model files!")
