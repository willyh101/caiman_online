function cwsAcqDone(src, evt, varargin)

global cws

cws.send(jsonencode('acq done'));