function caimanAcqDone(src,evt,varargin)
% caiman_online/matlab must be on path

computer_name =  'Will';
env_name = 'caiman-online';

py_path = ['C:\Users\' computer_name '\Anaconda3\envs\' env_name '\python.exe'];
cmd_send = [py_path ' networking.py trial_done'];

system(cmd_send);