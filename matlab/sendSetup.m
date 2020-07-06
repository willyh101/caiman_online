function sendSetup(src,evt,varargin)
% make sure caiman_online/networking is on path

% needs to get nchannels and nvols from SI handle
nchannels = 2;
nvols = 3;

computer_name =  'Will';
env_name = 'caiman-online';

py_path = ['C:\Users\' computer_name '\Anaconda3\envs\' env_name '\python.exe'];
cmd_send = [py_path ' networking.py setup ' num2str(nchannels) ' ' num2str(nvols)];

system(cmd_send);