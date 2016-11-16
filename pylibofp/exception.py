# pylibofp uses the following Exception hierarchy:
#
#     Exception (built into Python)
#       +-- pylibofp.ControllerException
#       |     +-- pylibofp.TimeoutException
#       |     +-- pylibofp.RPCErrorException  <-- RPCException
#       |     +-- pylibofp.OFPErrorException  <-- ErrorException
#       |     +-- pylibofp.OFPDeliveryException  <-- DeliveryException
#       |     +-- pylibofp.ChannelException
#       +-- pylibofp.ControlFlowException
#             +-- pylibofp.FallThroughException
#             +-- pylibofp.BreakException
#             +-- pylibofp.ExitException


class ControllerException(Exception):
    """
    Base class for exceptions thrown by Controller class.
    """

    def __init__(self, xid):
        super().__init__()
        self.xid = xid
        self.message = ''


class TimeoutException(ControllerException):
    """
    Controller exception that indicates an RPC or OpenFlow request has timed out.
    """

    def __init__(self, xid):
        super().__init__(xid)

    def __str__(self):
        return '[TimeoutException xid=%s]' % self.xid


class RPCErrorException(ControllerException):
    """
    Controller exception that indicates an error response to an RPC request.
    """

    def __init__(self, event):
        super().__init__(event.id)
        self.message = event.error.message
        self.code = event.error.code

    def __str__(self):
        return '[RPCErrorException xid=%s message=%s]' % (self.xid,
                                                          self.message)


class OFPErrorException(ControllerException):
    """
    Controller exception that indicates an OpenFlow error response tied to an
    OpenFlow request.
    """

    def __init__(self, event):
        super().__init__(event.xid)
        self.event = event

    def __str__(self):
        return '[OFPErrorException xid=%s event=%s]' % (self.xid, self.event)


class OFPDeliveryException(ControllerException):
    """
    Controller exception that indicates a message couldn't be delivered.
    """

    def __init__(self, event):
        super().__init__(event.xid)
        self.event = event

    def __str__(self):
        return '[OFPDeliveryException xid=%s event=%s]' % (self.xid,
                                                           self.event)


class ControlFlowException(Exception):
    """
    Base class for control flow exceptions used in pylibofp.
    """


class FallThroughException(ControlFlowException):
    """
    Exception class used by an app to "fall through" a handler.
    """

    def __str__(self):
        return '[FallThroughException]'


class BreakException(ControlFlowException):
    """
    Exception class used by an app to prevent handlers in other apps from executing.
    """

    def __str__(self):
        return '[BreakException]'


class ExitException(ControlFlowException):
    """
    Internal exception class used to exit the controller (similar to `StopIteration`)
    """

    def __str__(self):
        return '[ExitException]'
