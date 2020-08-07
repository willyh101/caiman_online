function caimanAcqDone(src,evt,varargin)
% caiman_online/matlab must be on path

computer_name =  'FrankenSI';
env_name = 'caiman';

py_path = ['C:\Users\' computer_name '\.conda\envs\' env_name '\python.exe'];
cmd_send = [py_path ' networking.py acq_done'];

system(cmd_send);