from flask_socketio import Namespace, emit

class SIserver:
    def __init__(self):
        self.acqs_done = 0
        self.acqs_this_batch = 0
        self.acq_per_batch = 5
        self.expt.batch_size = self.acq_per_batch
        
        self.trial_lengths = []
        self.traces = []
        
    def update(self):
        """
        Updates acq counters and anything else that needs to keep track of trial counts.
        """
        if self.acqs_done == 0:
            self.expt.segment_mm3d()
            # self.expt.segment() for if you want to provide the structural image manually
        # else:
            # get data from caiman main

        self.acqs_done += 1
        self.acqs_this_batch += 1