class UserProcessError(Exception):
    pass

class FailedToSendEmail(UserProcessError):
    pass

class InvalidCode(UserProcessError):
    pass

class ProcessDisabled(UserProcessError):
    pass

class ProcessInProgress(UserProcessError):
    pass

class ProcessNotInProgress(UserProcessError):
    pass

class ProcessComplete(UserProcessError):
    pass
