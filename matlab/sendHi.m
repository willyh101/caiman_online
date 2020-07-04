function sendHi()

computer_name =  'Will';
env_name = 'caiman-online';

py_path = ['C:\Users\' computer_name '\Anaconda3\envs\' env_name '\python.exe'];
cmd_send = [py_path ' send_hi.py'];

system(cmd_send);