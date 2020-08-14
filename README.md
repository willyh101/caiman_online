# OnlineAn

A psuedo-online implentation of the [CaImAn](https://github.com/flatironinstitute/CaImAn)  seeded batch algorithm for holography. Interfaces with [ScanImage](http://scanimage.vidriotechnologies.com/) and optionally a DAQ via websockets.
 

### Requirements:

* Anaconda3/Miniconda
* MatlabWebSocket (currently optional)
* ScanImage


### Installation

1. Download and install [Anaconda 3](https://www.anaconda.com/products/individual). Click YES to add conda to PATH. If you already have anaconda/python installed, just add conda to PATH. It's not actually required just useful.

1. Clone my [caiman_online](https://github.com/willyh101/caiman_online) repo from GitHub. Be sure to use command-line git or GitHub desktop to clone it, instead of just copying the files so you can get important updates and whatnot.

1. Open Anaconda prompt and change to the directory where you put caiman_online (`cd path/to/caiman/folder`)

1. Install caiman-online with:  `conda env create -f environment.yml`. This will install caiman, python, and all other packages you need to set up and run the websocket servers, do analysis, etc. This can take a few minutes, especially while 'solving environment'.

1. Activate the environment `conda activate caiman-online`

1. Install the caiman_online package by running `pip install -e .`

1. From the terminal, run `python setup_matlab.py`. This creates the callback functions needed for ScanImage and fills in the paths neeeded based on your PC. You can specify a path for it if you want, otherwise it installs in caiman_online/matlab. In the end, it just needs to be in SI path to work. 

1. Set the callbacks up in scanimage as user functions. `caimanAcqDone` is acqDone, `caimanSessionDone` is acqAbort, and `sendSetup` is acqArmed. 

1. You'll need to setup the rig_run_file.py for your rig, but mostly those settings are sent over websocket from SI when acqModeArmed happens (when you hit LOOP). See that file for details. Then just run the python file in an editor or via commandline. Once it says ready to launch, you can start scanimage on loop.

1. OPTIONAL (for now): Download the most recent [MatlabWebsocket](https://github.com/jebej/MatlabWebSocket) from GitHub. Follow their install instructions.