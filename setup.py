from distutils.core import setup

setup(
  name='Flammable',
  version='1.0-alpha.1',
  description='Framework of machine learning abstractions for model management and basic logging of experiments.',
  author='Przemysław Dolata',
  author_email='przemyslaw.dolata@outlook.com',
  packages=['flammable'],
  requires=['gitpython', 'torch'],
  )

# Run for the first time to perform initial configuration
# Ensure we're calling the installed version, not the local (source)
import sys
sys.path = [path for path in sys.path if 'flammable' not in path]
import flammable
