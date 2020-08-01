function sendSetup(src,evt,varargin)
% make sure caiman_online/networking is on path

% needs to get nchannels and nvols from SI handle
hSI = src.hSI;

nchannels = length(hSI.hChannels.channelSave);
nvols = hSI.hStackManager.numSlices;
frameRate = hSI.hRoiManager.scanVolumeRate;

computer_name =  'FrankenSI';
env_name = 'caiman';

py_path = ['C:\Users\' computer_name '\.conda\envs\' env_name '\python.exe'];
cmd_send = [py_path ' networking.py setup ' ...
    num2str(nchannels) ' ' num2str(nvols) ' ' num2str(frameRate)];

system(cmd_send);