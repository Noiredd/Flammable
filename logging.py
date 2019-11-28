class Logger():
  """Store sequentially incoming data with (almost) no layout assumptions.

  The only assumption is that the data come in a dict, where each value is
  named. Each sample will be appended to a list stored internally under that
  name. Finally, data can be pushed to some Snapshot, with some optional post-
  processing (currently available: only averaging or none).
  """
  post_funs = {
    'all': lambda x: x,
    'average': lambda x: sum(x) / len(x),
  }

  def __init__(self, mode='average'):
    self.values = {}
    self.postprocess = self.post_funs[mode]

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
        transaction.store(key, self.postprocess(val))

