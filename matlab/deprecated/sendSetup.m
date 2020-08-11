function sendSetup(src,evt,varargin)
% make sure caiman_online/networking is on path

% needs to get nchannels and nvols from SI handle
hSI = src.hSI;

nchannels = length(hSI.hChannels.channelSave);
nplanes = hSI.hStackManager.numSlices;
frameRate = hSI.hRoiManager.scanVolumeRate;
si_path = hSI.hScan2D.logFilePath;
framesPerPlane = floor(hSI.hStackManager.numVolumes / hSI.hStackManager.numSlices);

computer_name =  'FrankenSI';
env_name = 'caiman';

py_path = ['C:\Users\' computer_name '\.conda\envs\' env_name '\python.exe'];
cm_path = ['C:\Users\' computer_name '\Documents\caiman_online\matlab\networking.py'];
cmd_send = [py_path ' ' cm_path ' setup ' ...
    num2str(nchannels) ' ' num2str(nplanes) ' ' num2str(frameRate) ' ' ...
    si_path ' ' num2str(framesPerPlane)];

system(cmd_send);