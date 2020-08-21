# OnlineAn

A psuedo-online implentation of the [CaImAn](https://github.com/flatironinstitute/CaImAn)  seeded batch algorithm for holography. Interfaces with [ScanImage](http://scanimage.vidriotechnologies.com/) and optionally a DAQ via websockets.


## Installation

1. Download and install [miniconda](https://docs.conda.io/en/latest/miniconda.html) or [Anaconda 3](https://www.anaconda.com/products/individual). Click YES to add conda to PATH. It's not actually required just useful in general.

1. Clone my [caiman_online](https://github.com/willyh101/caiman_online) repo from GitHub. Be sure to use command-line git or GitHub desktop to clone it, instead of just copying the files so you can get important updates and whatnot. **Please be sure to install into a folder with no spaces anywhere in the path.** This breaks how MATLAB calls the python scripts. `setup_matlab.py` will prevent you from installing if that's the case. If you need to reinstall, do `conda env remove --name caiman-online`, delete the repo, re-clone, and then try again.

1. Open Anaconda prompt and change to the directory where you put caiman_online (`cd path/to/caiman/folder`)

1. Install caiman-online with:  `conda env create -f environment.yml`. This will install caiman, python, and all other packages you need to set up and run the websocket servers, do analysis, etc. This can take a few minutes, especially while 'solving environment'.

1. Activate the environment `conda activate caiman-online`

1. Install the caiman_online package by running `pip install -e .` (the . is intentional)

1. From the terminal, run `python setup_matlab.py`. This creates the callback functions needed for ScanImage and fills in the paths neeeded based on your PC. You can specify a path for it if you want, otherwise it creates and installs in ./matlab. In the end, it just needs to be in SI path to work. 

1. Set the callbacks up in scanimage as user functions. `caimanAcqDone` is acqDone, `caimanSessionDone` is acqAbort, and `sendSetup` is acqArmed. 

1. You'll need to setup the rig_run_file.py for your rig, but mostly those settings are sent over websocket from SI when acqModeArmed happens (when you hit LOOP). See that file for details. Then just run the python file in an editor or via commandline. Once it says ready to launch, you can start scanimage on loop.

1. OPTIONAL (for now): Download the most recent [MatlabWebsocket](https://github.com/jebej/MatlabWebSocket) from GitHub. Follow their install instructions. This can send data from the DAQ to the caiman app, like stim conditions, powers, etc.

## A brief how-to:

### Pre-experiment setup

The main thing to do is setting up a rig run file with your specific settings. PLEASE DO NOT EDIT ANY EXISTING RIG RUN FILES.

* See `simulate_run.py` and/or `franken_rig_run.py` for example. The only parameters you really need are the ip address of the host computer (eg. the computer you are running CaimanOnline on) and a port number (can be anything). If you aren't hooking up the DAQ to CaimanOnline, then it can just run on `localhost`.

* Specify a location for `srv_folder`. This doesn't have to be a server folder, but it's where the .mat files get saved to.

* Specify where the makeMasks3D.mat file is in `template_path`. For ease, I just added a line to mm3d that also saves the output to the same folder everytime (and just overwrites the old one).

* Beyond this, everything should be auto-generated, **except for number of planes** (see below).

* Instead of manually entering all of the values, the `sendSetup` callback triggered on acqArmed sends _almost_ all of the needed information. The one current big is that you will need to specify the number of planes you use. `sendSetup` does send this information over, but not before the initial segmentation takes place.

* If you don't run `sendSetup` for some reason, then just be sure to specify all of the parameters there. Specifically, `batch_size`, `frame_rate`, `channels`, `planes`, and `tif_folder`.

* `x_start` and `x_end` are important because they remove the stim artifacts. **They need to match whatever is being use in makeMasks3D.**

### Running an experiment

1. Run makeMasks3D.m as usual. Save into the folder specified by template_path.

1. Start the online analysis by running your rig run file. Either through running the script in VSCode/Atom/etc. or call from command line (in the caiman-online environment) via `python franken_rig_run.py` (insert whatever your rig run file is)

1. Everything should boot up and be ready to go. The callbacks from ScanImage will trigger caiman to run when it gets enough data. When you hit 'abort' to stop SI, it will finish the last batch of tiffs and then stop. If it's set to run a batch every 20 tiffs, and you collect 3 tiffs, it can't/won't process those tiffs. Also, if you collect 19 tiffs, it won't process those tiffs either. So I try to be smart about when to stop the experiment so caiman gets the most data.

1. CaimanOnline will output several things. (1) a few *.mat files of traces (cell x time) and psths (trial x cell x time, NOT stim aligned) into srv_folder, and (2) several *.json files of the processed data, one for each plane and each batch of all of the raw data. The JSON data can be loaded and processed using the `json_analysis_template_new.ipynb` notebook (not complete but mostly works). The order of cells output should be the same order than makeMasks3D did them in, which is typically brighest first. So, they should match up 1-to-1 with holoRequest, but this hasn't been extensively tested, but as far as I can tell now, it's working as expected.

1. Do analysis on the processed data! There are some functions available in `caiman_online.analysis` and `caiman_online.vis`. Feel free to contribute more, just be careful about making changes to existing code since it would potentially/likely affect other users. If you want to use MATLAB, then the *.mat files would be the way to go (they are already processed).

----

## Known bugs/To-do:
- the issue with OnlineAnalysis.make_templates() being called before SI gets armed. thus, if the number of planes from the MM3D template does not match the setting in the rig run file, then it might index out-of-bounds error or not segment all of the planes. since this is used for seeding, the last plane won't have any seeds for source extraction.
- possibility that cells aren't in the same order and/or are missing if they didn't get detected. maybe put in a checker to make sure cell locs are consistent. currently, this will cause Server.save_trial_data_mat() to fail and prints an alert to the screen.
- cool looking updatable and interactive display of data as it becomes available.