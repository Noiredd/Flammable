import os

import torch

from .logger import Logger
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
        * compute the loss value for this output and the original sample
        * perform the backward pass
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
    """Default backward pass.

    Evaluates a given criterion, backpropagates, and returns a nicely formatted
    dict with the loss values, which can be directly fed to the Logger. If the
    user deals with multiple losses or labels, they only need to override this
    one function to dictate how the losses are supposed to be evaluated and
    what do they mean.
    """
    _, label = sample
    # Evaluate the criterion
    loss = self.criterion(output, label)
    # Backpropagate
    loss.backward()
    # Name the losses for logging
    loss_values = {
      'loss': loss.item(),
    }
    return loss_values

  def iteration(self, sample):
    """Default meta-algorithm for a single iteration over the training dataset.

    Returns post-processed loss(es), ready to log.
    """
    self.model.train()
    self.optimizer.zero_grad()
    sample = self.prepare_train(sample)
    output = self.forward_train(sample)
    loss = self.backward(output, sample)
    self.optimizer.step()
    return loss

  def epoch(self, dataset):
    """Default meaning of an 'epoch' (single iteration over the dataset).

    Additionally does some basic book-keeping using Logger.
    """
    logger = Logger('average')
    for self.iter_i, sample in enumerate(dataset):
      losses = self.iteration(sample)
      logger.log(losses)
    logger.store_train(self.snapshot)

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
    # Store the final model
    self.save_model('final.pt')

  # Utilities

  def every_n_epochs(self, n, function, skip_zero=True):
    """Execute "function" but only every "n" epochs.

    "function" must accept a single argument, which will be a reference to the
    self instance.

    Call this function at every epoch - it will care of everything.
    "skip_zero" will make it ignore the first call (since it uses modulo to
    check whether it's time to make the function call, it would call after the
    first epoch, which may or may not be intended).

    Example usage:

      def infer_reference(task):
        # ...

      class MyTask(PytorchTask):
        #...
        def epoch(self, dataset):
          super(MyTask, self).epoch(dataset)
          self.every_n_epochs(10, infer_reference)
    """
    if skip_zero and self.epoch_i == 0:
      return
    if self.epoch_i % n == 0:
      function(self)


class PytorchTestable():
  """Mixin for testing-related abstractions.

  Realizes the most high-level idea of a test, defined as follows:
    * create the data source
    * create the test metric
    * iterate over the data source, each time doing the following:
      * prepare the data sample
      * perform the forward pass for this sample, obtaining some output
      * compute the metric value and store it
    * perform some post-processing to produce a final metric

  An additional layer of abstraction is introduced to separate the test logic
  from utility activities such as instantiation of the dataset or loading the
  model (weights). The main "test" function does all these, but the test logic
  itself is encapsulated in a specialized "test_on" method, which does nothing
  else. This gives the user a straightforward way to test an imported instance
  on whatever dataset they wish, from whichever model file they wish.

  Testable also provides an additional interface to simplify validating a model
  during training. The algorithm is roughly:
    * create the data source or use a cached one
    * call test_on(this data source)
    * store results in the snapshot
  and is available to the user as "validate" method.

  When deriving from PytorchTestable (or rather PytorchTask) one still needs to
  implement some of the functions - see "User code" area.

  Warning: due to dependencies on several self-bound attributes and methods
  (e.g. self.forward() or self.device) this class alone makes little sense. It
  shall be used only when mixed into the PytorchTask composite class.
  """

  # User code

  def get_testing_data(self):
    """User code: should return a testing data loader.

    Similar default expectations apply as in the case of Trainable.
    """
    raise NotImplementedError

  def get_metric(self):
    """User code: should return a callable to measure some test metric."""
    raise NotImplementedError

  # Meta-algorithm

  def prepare_test(self, sample):
    """Default sample preprocessing before feeding to the model at testing."""
    data, label = sample
    data = data.to(self.device)
    label = label.to(self.device)
    return data, label

  def forward_test(self, sample):
    """Default forward pass during training."""
    data, _ = sample
    output = self.forward(data)
    return output

  def evaluate_metrics(self, output, sample):
    """Evaluate criterion/criteria and return log-ready values.

    Corresponds to PytorchTrainable's "backward". Similarly, this allows
    evaluating complex test metrics (e.g. consisting of multiple different
    callables, or referring to multiple ground truth labels). For example:
      _, label = sample
      L2, accuracy, F1 = self.metric
      metrics = {
        'L2_loss': L2(output, label).item(),
        'accuracy': accuracy(output, label).item(),
        'F1_score': F1(output, label).item(),
      }
      return metrics
    """
    _, label = sample
    metrics = {
      'loss': self.metric(output, label).item()
    }
    return metrics

  def single_test(self, sample):
    """A single test iteration, returning formatted metric(s)."""
    sample = self.prepare_test(sample)
    with torch.no_grad():
      output = self.forward_test(sample)
      metrics = self.evaluate_metrics(output, sample)
    return metrics

  def test_on(self, dataset, snapshot=None):
    """Default testing meta-algorithm.

    Iterates over the given dataset and logs metrics' values using a Logger. If
    "snapshot" is given, will automatically postprocess and store these values
    in that snapshot. Otherwise will return the list of raw results.
    """
    logger = Logger()
    self.model.eval()
    # Initialize the metric callable now, so the user doesn't have to
    self.metric = self.get_metric()
    # Testing meta-algorithm (loop)
    for sample in dataset:
      metrics = self.single_test(sample)
      logger.log(metrics)
    # Book-keeping
    if snapshot:
      logger.store_test(snapshot)
    else:
      return logger.return_final()

  def test(self):
    """Master algorithm for testing, as executed by the CLI."""
    self.load_model()
    self.model.to(self.device)
    # Spawn data now, but the metric callable later
    data = self.get_testing_data()
    # Run the test logic (automatically stores results)
    self.test_on(data, self.snapshot)

  # Validation interface

  def get_validation_data(self):
    """User code: should return a validation data object.

    By default does the same thing as "get_testing_data", but can be overridden
    when needed. Returned object should behave the same as test data in all
    cases.
    """
    return self.get_testing_data()

  def log_validation(self, metrics):
    """Store computed validation metrics in a snapshot.

    Expects "metrics" to follow the layout defined in "evaluate_metrics".
    """
    with self.snapshot.val_storage() as transaction:
      for name, value in metrics.items():
        transaction.append(name, value)

  def validate(self, *args):
    """Perform a testing round while training.

    Accepts additional arguments to make calls from PytorchTrainable's
    "every_n_epochs" (which passes self as argument).
    """
    # Get validation data (or use cached object)
    if self.val_dataset is None:
      self.val_dataset = self.get_validation_data()
    # Execute the test
    metrics = self.test_on(self.val_dataset)
    # Store the results
    self.log_validation(metrics)


class PytorchTask(PytorchTestable, PytorchTrainable, BaseTask):
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
    self.val_dataset = None
    self.epoch_i = None
    self.iter_i = None
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
