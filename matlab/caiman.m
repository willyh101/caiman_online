% starts the SI/MATLAB side of Caiman Online
% also starts the websocket client

% pathing
addpath(genpath('C:\Users\FrankenSI\Documents\caiman_online'))
addpath(genpath('C:\Users\FrankenSI\Documents\MATLAB\MatlabWebSocket\src'))

% start the WS client object
global cws

cws = CaimanClient;

% start the python server
py_path = 'C:/Users/Will/Anaconda3/envs/caiman-online/python.exe';
cm_path = 'C:/Users/Will/Lab Code/caiman_online/franken_rig_run.py';

system([py_path ' ' cm_path '&'])