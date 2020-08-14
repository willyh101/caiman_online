function sendSetup(src,evt,varargin)
        % callback on acqModeArmed
        
        hSI = src.hSI;

        nchannels = length(hSI.hChannels.channelSave);
        nplanes = hSI.hStackManager.actualNumSlices;
        frameRate = hSI.hRoiManager.scanVolumeRate;
        si_path = hSI.hScan2D.logFilePath;
        framesPerPlane = floor(hSI.hStackManager.numVolumes / hSI.hStackManager.actualNumSlices);

        py_path = 'C:/Users/FrankenSI/.conda/envs/caiman-online/python.exe';
        cm_path = 'C:/Users/FrankenSI/Documents/caiman_online/caiman_online/matlab/networking.py';

        cmd_send = [py_path ' ' cm_path ' setup ' ...
            num2str(nchannels) ' ' num2str(nplanes) ' ' num2str(frameRate) ' ' ...
            si_path ' ' num2str(framesPerPlane)];

        system(cmd_send);
        