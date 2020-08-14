function sendHi()

        py_path = 'C:/Users/FrankenSI/.conda/envs/caiman-online/python.exe';
        cm_path = 'C:/Users/FrankenSI/Documents/caiman_online/caiman_online/matlab/networking.py';
        
        cmd_send = [py_path ' ' cm_path ' hi'];

        system(cmd_send);