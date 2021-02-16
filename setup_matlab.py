import sys
import os

def install(install_path=None):
    """Install the MATLAB files. By default they get stored in caiman_online/matlab, or you could
    change them by specifying path to put them somewhere in the SI MATLAB path."""
    
    path = os.path.join(os.getcwd(), 'caiman_online/networking.py').replace('\\','/')
    pypath = f'{sys.executable}'.replace('\\','/')
    
    if len(pypath.split(' ')) > 1 or len(path.split(' ')) > 1:
        raise FileNotFoundError("You can't save into a directory with spaces! Causes problems with MATLAB.")

    files = dict(
        
        caimanAcqDone = f"""function caimanAcqDone(src,evt,varargin)
        % callback on acqDone
        
        py_path = '{pypath}';
        cm_path = '{path}';
        
        cmd_send = [py_path ' ' cm_path ' acq_done'];
        
        system(cmd_send);""",

        caimanSessionDone = f"""function caimanSessionDone(src,evt,varargin)
        % callback on acqAbort
        
        py_path = '{pypath}';
        cm_path = '{path}';
        
        cmd_send = [py_path ' ' cm_path ' session_done'];
        
        system(cmd_send);""",

        sendSetup = f"""function sendSetup(src,evt,varargin)
        % callback on acqModeArmed
        
        hSI = src.hSI;

        nchannels = length(hSI.hChannels.channelSave);
        nplanes = hSI.hStackManager.numSlices;
        frameRate = hSI.hRoiManager.scanVolumeRate;
        si_path = hSI.hScan2D.logFilePath;
        framesPerPlane = floor(hSI.hStackManager.numVolumes / hSI.hStackManager.actualNumSlices);

        py_path = '{pypath}';
        cm_path = '{path}';

        cmd_send = [py_path ' ' cm_path ' setup ' ...
            num2str(nchannels) ' ' num2str(nplanes) ' ' num2str(frameRate) ' ' ...
            si_path ' ' num2str(framesPerPlane)];

        system(cmd_send);
        """,
        
        sendHi = f"""function sendHi()

        py_path = '{pypath}';
        cm_path = '{path}';
        
        cmd_send = [py_path ' ' cm_path ' hi'];

        system(cmd_send);""",
        
        sendUhOh = f"""function sendUhOh()
        py_path = '{pypath}';
        cm_path = '{path}';
        
        cmd_send = [py_path ' ' cm_path ' uhoh'];

        system(cmd_send);""",
        
        caimaninit = f"""function caimaninit()
        py_path = '{pypath}';
        cm_path = '{path}';
        
        [file, path] = uigetfile(hSI.hScan2D.logFilePath, 'MultiSelect', 'on')
        
        if isequal(file, 0)
            return
        else
            out = jsonencode(file, path);
            
        cmd_send = [pypath ' ' cm_path ' ']
            
        system(cmd_send())

        
        """
    )
    
    if install_path is None:
        install_path = './matlab'
        os.mkdir(install_path)
        
    for fname, contents in files.items():
        with open(os.path.join(install_path, fname+'.mat'), 'w') as f:
            f.write(contents)
            
if __name__ == '__main__':
    args = sys.argv[1:]
    if len(args) == 0:
        install()
    elif len(args) == 1:
        install(args)
    else:
        raise ValueError('install path is the only argument you can pass.')