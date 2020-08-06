# OnlineAn

A psuedo-online implentation of the [CaImAn](https://github.com/flatironinstitute/CaImAn)  seeded batch algorithm for holography. Interfaces with [ScanImage](http://scanimage.vidriotechnologies.com/) and optionally a DAQ via websockets.
 

### Requirements:

* caiman
* Anaconda3
* MatlabWebSocket


### Installation

1. Download and install [Anaconda 3](https://www.anaconda.com/products/individual). Click YES to add conda to PATH. If you already have anaconda/python installed, just add conda to PATH. It's not actually required just useful.

2. Download the most recent [MatlabWebsocket](https://github.com/jebej/MatlabWebSocket) from GitHub. Follow their install instructions.

3. Install [CaImAn](https://github.com/flatironinstitute/CaImAn) via:
```
conda create -n caiman
conda activate caiman
conda install caiman -c conda-forge
```

install via environment.yml / requirements.txt

