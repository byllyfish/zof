# zof uses the following Exception hierarchy:
#
#     Exception (built into Python)
#       +-- zof.ControllerException
#       |     +-- zof.TimeoutException
#       |     +-- zof.RPCException
#       |     +-- zof.ErrorException
#       |     +-- zof.DeliveryException
#       +-- zof.ControlFlowException
#             +-- zof.StopPropagationException
#             +-- zof.ExitException
#             +-- zof.PreflightUnloadException


class ControllerException(Exception):
    """Base class for exceptions thrown by Controller class."""

    def __init__(self, xid):
        super().__init__()
        self.xid = xid
        self.message = ''


class TimeoutException(ControllerException):
    """Exception that indicates an RPC or OpenFlow request has timed out."""

    def __init__(self, xid, timeout):
        super().__init__(xid)
        self.timeout = timeout

    def __str__(self):
        return '[TimeoutException xid=%s timeout=%s]' % (self.xid,
                                                         self.timeout)


class RPCException(ControllerException):
    """Exception that indicates an error response to an RPC request."""

    def __init__(self, event):
        super().__init__(event.id)
        self.message = event.error.message
        self.code = event.error.code

    def __str__(self):
        return '[RPCException xid=%s message=%s]' % (self.xid, self.message)


class ErrorException(ControllerException):
    """Exception that indicates an OpenFlow error reply."""

    def __init__(self, event):
        super().__init__(event.xid)
        self.event = event

    def __str__(self):
        return '[ErrorException xid=%s event=%s]' % (self.xid, self.event)


class DeliveryException(ControllerException):
    """Exception that indicates an OpenFlow message couldn't be delivered."""

    def __init__(self, event):
        super().__init__(event.xid)
        self.event = event

    def __str__(self):
        return '[DeliveryException xid=%s event=%s]' % (self.xid, self.event)


class ControlFlowException(Exception):
    """Base class for control flow exceptions used in zof."""


class StopPropagationException(ControlFlowException):
    """Exception class used by an app to prevent handlers in other apps from
    executing.
    """

    def __str__(self):
        return '[StopPropagationException]'


class ExitException(ControlFlowException):
    """Internal exception class used to stop the controller."""

    def __init__(self, exit_status=0):
        super().__init__()
        self.exit_status = exit_status

    def __str__(self):
        return '[ExitException exit_status=%d]' % self.exit_status


class PreflightUnloadException(ControlFlowException):
    """Exception class used by an app unload itself. This exception should
    only be raised in a 'preflight' event handler.
    """

    def __str__(self):
        return '[PreflightUnloadException]'
