function cwsSendSetup(src, evt, varargin)

global cws

hSI = src.hSI;

setup.kind = 'setup';
setup.nchannels = length(hSI.hChannels.channelSave);
setup.nplanes = hSI.hStackManager.numSlices;
setup.frameRate = hSI.hRoiManager.scanVolumeRate;
setup.si_path = hSI.hScan2D.logFilePath;
setup.framesPerPlane = floor(hSI.hStackManager.numVolumes / hSI.hStackManager.numSlices);

cws.send(jsonencode(setup));