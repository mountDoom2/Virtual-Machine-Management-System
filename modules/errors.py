"""
File: errors.py
Author: Milan Skala
Date: 2016-03-20
Brief: Additional exceptions definitions 
"""

class EnvironmentException(Exception):
    """
    Raises when there is error during Environment initialization
    """
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