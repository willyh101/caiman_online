from termcolor import cprint

class WebSocketAlert:
    alerts = {
        'none': '*',
        'info': '[INFO]',
        'warn': '[WARNING]',
        'error': '[ERROR]',
        'success': '[INFO]'
    }
    
    colors = {
        'none': 'white',
        'info': 'yellow',
        'warn': 'orange',
        'error': 'red',
        'success': 'green'
    }
    
    def __init__(self, message, level='none'):
        self.message = message
        self.level = level
        self.color = self.colors[self.level]
        
        out = self.format()
        self.show(out)
    
    def format(self):
        return f'{self.alerts[self.level]} {self.message}'
    
    def show(self, output):
        cprint(output, self.color)
        
if __name__ == '__main__':
    WebSocketAlert('good job', 'success')