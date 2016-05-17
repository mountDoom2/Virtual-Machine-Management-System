class EnvironmentException(Exception):
    def __init__(self, message=""):
        super(Exception, self).__init__(message)

        self.message = message
    
    def __str__(self):
        return self.message
    
class CommandException(Exception):
    def __init__(self, message=""):
        super(Exception, self).__init__(message)

        self.message = message
    
    def __str__(self):
        return self.message  