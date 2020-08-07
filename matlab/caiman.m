% starts the SI/MATLAB side of Caiman Online
% also starts the websocket client

% pathing
addpath(genpath('C:\Users\FrankenSI\Documents\caiman_online'))
addpath(genpath('C:\Users\FrankenSI\Documents\MATLAB\MatlabWebSocket\src'))

% start the WS client object
global cws

cws = CaimanClient;