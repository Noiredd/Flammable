import os

import torch

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
    data.to(self.device)
    label.to(self.device)
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

  def step(self, sample):
    """Default meta-algorithm for a single iteration over the training dataset."""
    self.model.train()
    self.optimizer.zero_grad()
    self.sample = self.prepare_train(sample)
    self.output = self.forward_train(self.sample)
    self.loss = self.backward(self.output, self.sample)
    self.optimizer.step()
    # TODO: iteration-level book-keeping

  def epoch(self, dataset):
    """Default meaning of an 'epoch' (single iteration over the dataset)."""
    for sample in dataset:
      self.step(sample)
    # TODO: epoch-level book-keeping
    # TODO: validation pass

  def train(self):
    """Default training meta-algorithm."""
    # Initialize required components (user-defined)
    data = self.get_training_data()
    self.criterion = self.get_criterion()
    self.optimizer = self.get_optimizer()
    # Run the outer loop
    for self.epoch_i in range(self.epochs):
      self.epoch(data)
    # TODO: summary book-keeping
    # TODO: save the model file


class PytorchTask(BaseTask, PytorchTrainable):
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

  # TODO: save/read model files (and register them with Snapshot)
