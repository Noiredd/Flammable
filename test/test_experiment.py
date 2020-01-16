"""Tests for the Experiment class, mostly git-related."""

import os
import shutil
import tempfile
import unittest

import flammable

INITIAL_FILE = """\
from flammable import Task

class TestTask(Task):
  def train(self):
    pass

test = TestTask(None)
test.main('initial')
"""

class TestNewExperiment(unittest.TestCase):
  """Tests creation of a new experiment from scratch."""
  @classmethod
  def setUpClass(self):
    self.sandbox = tempfile.TemporaryDirectory(prefix='flm')
    _, self.exp_name = os.path.split(self.sandbox.name)
    self.script_path = os.path.join(self.sandbox.name, 'test.py')
  
  @classmethod
  def tearDownClass(self):
    # Clean up the sandbox directory, but also the global repository
    self.sandbox.cleanup()
    shutil.rmtree(os.path.join(flammable.library.storage_path, 'sandbox'))

  def test_0_initialState(self):
    """Ensure the library is empty before we begin."""
    self.assertDictEqual(flammable.library.experiments, {})

  def test_1_createExperiment(self):
    """Create a new experiment, test if it shows up in the library."""
    # Prepare directory for the new local repository
    self.test_repo_path = os.path.join(self.sandbox.name, 'sandbox')
    os.mkdir(self.test_repo_path)

    # Create a file
    script_path = os.path.join(self.test_repo_path, 'test.py')
    with open(script_path, 'w') as test_script:
      test_script.write(INITIAL_FILE)

    # Call it, executing all the tested mechanics
    os.system('python {} train'.format(script_path))

    # Reload the library to see how we've done
    flammable.library.load_experiments()
    self.assertIn('sandbox', flammable.library.experiments.keys())

  def test_commit(self):
    """Check whether a commit has been correctly created."""
    experiment = flammable.library.get_experiment('sandbox')
    commits = [commit.message for commit in experiment.repo.iter_commits()]
    self.assertEqual(len(commits), 1)
    self.assertEqual(commits[0], 'initial')

  def test_remote(self):
    """Check the status of the global repository."""
    experiment = flammable.library.get_experiment('sandbox')
    commits = [commit.message for commit in experiment.global_repo.iter_commits()]
    self.assertEqual(len(commits), 1)
    self.assertEqual(commits[0], 'initial')


if __name__ == "__main__":
  unittest.main()
