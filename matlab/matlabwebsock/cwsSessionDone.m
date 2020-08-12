function cwsSessionDone(src, evt, varargin)

global cws

cws.send(jsonencode('session done'));