class Logger():
  """Store sequentially incoming data with (almost) no layout assumptions.

  The only assumption is that the data come in a dict, where each value is
  named. Each sample will be appended to a list stored internally under that
  name. Finally, data can be pushed to some Snapshot, with some optional post-
  processing (currently available: only averaging or none).

  "mode" can be either a string identifying one of built-in postprocessing
  functions, or a callable to be used instead.
  Currently supported built-ins: "all", "average".
  """
  post_funs = {
    'all': lambda x: x,
    'average': lambda x: sum(x) / len(x),
  }

  def __init__(self, mode='average'):
    self.values = {}
    self.has_post_fun = (mode != 'all')
    if mode in self.post_funs.keys():
      self.postprocess = self.post_funs[mode]
    elif callable(mode):
      self.postprocess = mode
    else:
      raise KeyError("Unknown postprocessing function!")

  def log(self, losses:dict):
    """Append each named sample to a corresponding list in the internal dict."""
    for name, value in losses.items():
      if name not in self.values.keys():
        self.values[name] = []
      self.values[name].append(value)

  def store_train(self, snapshot):
    """Postprocess and dump current values into a given Snapshot's train_data."""
    with snapshot.train_storage() as transaction:
      for key, val in self.values.items():
        transaction.append(key, self.postprocess(val))

  def store_test(self, snapshot, store_raw=True):
    """Postprocess and dump current values into a given Snapshot's test_data.

    If a postprocessing function has been chosen and "store_raw" is True, the
    original values for each entry will also be stored in the Snapshot, under
    the same key but suffixed with "_data".
    """
    with snapshot.test_storage() as transaction:
      for key, val in self.values.items():
        transaction.store(key, self.postprocess(val))
        if self.has_post_fun and store_raw:
          transaction.store(key + "_data", val)

  def return_final(self):
    """Simply postprocess all the value lists and return them without storing."""
    results = {
      key: self.postprocess(val) for key, val in self.values.items()
    }
    return results
