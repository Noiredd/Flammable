# Flammable
Flammable is a **f**ramework of machine **l**earning **a**bstractions for **m**odel **m**anagement and **b**asic **l**ogging of **e**xperiments (for Pytorch).

TLDR: build your experiment by defining only specific functions in abstract algorithms for basic tasks
and then have Git snapshot your code, automatically matching it with any artifacts it produces.

Skip to [installation instructions](docs/installation.md) or [notes for developers](docs/developers.md).

## Basics
There are two root assumptions behind Flammable.
1. Your machine learning experiments are code, and code *evolves* over time, producing different but important results every time.  
2. All machine learning models are essentially the same no matter what you do specifically: they are entities that are first *trained*, usually later *tested* and sometimes eventually *evaluated* (or "deployed").

Flammable captures these ideas by providing two tools: one for automatically tracking **development of an experiment** and another for encapsulating the **basic algorithms** of "training", "testing" and "evaluation".

## Model abstractions
Training a model looks exactly the same if you look from a high enough level of abstraction -
no matter if you do image classification or segmentation, or text understanding, or reinforcement learning.
Flammable makes this concept tangible by providing a basic meta-algorithm for "training a model".
In the most abstract way possible, it reduces to the following steps:
* create a data source
* create an optimization criterion
* create an optimizer
* iterate over the data source some number of times
  * prepare a data sample
  * perform a forward pass for this sample, obtaining some output
  * compute a loss value for this output and the original sample
  * perform a backward pass
  * update the model parameters

Flammable offers a simple abstract class that embodies this "master algorithm", separating each step into a function.
This allows you to use an existing abstract algorithm and redefine only these particular steps where your problem becomes *specific*,
instead of writing the entire algorithm from scratch.

The same idea is applied to "testing" and "evaluation" of a model.
See [`backend.py`](flammable/backend.py) and each of the separate mixin classes for details.

## Developing your experiments
Your experiments are code.
Except, as opposed to typical software development, your code produces some concrete results that are important in themselves:
learned model parameters, loss metrics, test results, example predictions.
All of them need to be stored every time you run your experiment,
and all of them need to be bound to a specific version of the code at that time.

Flammable uses **Git** to track version history of your experiment.
Every time you run it, Flammable creates a commit that exactly captures *that* state of your code.
Additionally, it creates a separate directory for any artifacts your experiment might produce.
This way you have total control over which logs/images/parameter files are saved where, and never again mix them up.

See modules [`experiment.py`](flammable/experiment.py) and [`task.py`](flammable/task.py) for details.

## How it all connects
Flammable provides a base class, `flammable.Task`, that combines all these ideas.
It comes equipped with `train`, `test` and `eval` methods to directly execute respective algorithms.

The most important method is however `main`, which allows you to define your script once,
and then execute its specific *aspect* using the command line interface.
Simply define your experiment as a class inheriting from `flammable.Task` and end your script with a call to `main`.
Like this:

```python
# my_script.py
class MyTask(flammable.Task):
  def __init__(self):
    model = torch.nn.Sequential(
      # ...
    )
    super(MyTask, self).__init__(model)

  def get_training_data(self):
    dataset = my_data_module.get_data('path/to/data/')
    return torch.utils.data.DataLoader(dataset)
  # ...

task = MyTask()
task.main()
```

And call using:  
`python my_script.py train`

Flammable takes care of creating a commit, calling `train`, managing your experiment data etc.

`main` is smart enough that it will detect whenever you try to import your model, e.g. with `from my_script import task`, and it will allow you to work with it completely normally.

## TODO
Flammable is currently at an early alpha level of development, however the key features are ready.
Starting in 2020 I'll be adding some unit tests, improving the docs, and moving to adding some more features, mainly an **inference server** and an **experiment browser**.

Among some of the current limitations, you cannot test a model while it is still training - but I'm intending to make it happen in the future, too.

Additionally, even though Flammable is built with Pytorch in mind, the design is robust enough that implementing a backend for other Python-based ML frameworks should be pretty simple.
