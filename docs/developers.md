I highly recommend keeping a virtual environment for development of Flammable.
If you don't, your development version will interfere with your production version
(i.e. where you keep your actual experiments).
**This might (will) lead to a complete loss of data.**

I use virtualenv for this.
So, after cloning the repo:

`git clone https://github.com/Noiredd/Flammable.git`  
`cd Flammable`  
`virtualenv venv`

(From here on I assume you're in the root directory of the repository, i.e. you see `README.md`.)

Activate the development environment:

`source venv/bin/activate`

And install the requirements:

`pip install -r requirements.txt`

Now you can verify that this instance of Flammable is indeed different than your "production" one:

`python -c "import flammable"`

Since you're running it for the first time (as it doesn't see the configuration file),
it will ask you for a path to the global repository.
This is where test cases will be ran, so use any path that is not within any Git repository.

Verify that it's different than your production repo:

`python -c "import flammable; print(flammable.library.storage_path)"`

First thing you might want to do is to run the unit tests.
Simply:

`python -m unittest discover`
