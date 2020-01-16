import shutil

import flammable

if flammable.library.experiments:
  print("ARE YOU SURE YOU'RE RUNNING TESTS FROM A VIRTUAL ENVIRONMENT?")
  print(
    "There are experiments in the library already. Aborting right",
    "now, in case this is your production repository. If these are",
    "remains of some previously failed test - clean up manually.",
    "Currently scanned directory:"
  )
  print(flammable.library.storage_path)
  print()
  exit(-1)
