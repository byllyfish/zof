"""
This app retrieves a datapath's ports.

This is a guard app with high precedence. This app blocks other apps from
receiving channel_up messages until all of the datapath's ports are discovered.

This app modifies message events to include the source `datapath` object.
"""

import zof
from zof.datapath import DatapathList
import zof.exception as _exc


class DatapathApp(zof.Application):
    def __init__(self):
        super().__init__('service.datapath', precedence=1000000000)
        self.datapaths = DatapathList()

    def get_datapaths(self):
        return [datapath for datapath in self.datapaths if datapath.ready]

    def find_datapath(self, datapath_id):
        try:
            datapath = self.datapaths[datapath_id]
            if datapath.ready:
                return datapath
        except KeyError:
            pass
        return None

    def find_port(self, datapath_id, port_no):
        datapath = self.find_datapath(datapath_id)
        try:
            return datapath[port_no]
        except KeyError:
            return None


APP = DatapathApp()

PORTS_REQUEST = zof.compile('type: REQUEST.PORT_DESC')


@APP.message('channel_up')
def channel_up(event):
    datapath = APP.datapaths.add_datapath(
        datapath_id=event['datapath_id'], conn_id=event['conn_id'])
    datapath.features = event['msg']['features']
    datapath.add_ports(datapath.features['ports'])
    datapath.ready = True
    event['datapath'] = datapath


@APP.message('channel_down')
def channel_down(event):
    datapath = APP.datapaths.delete_datapath(datapath_id=event['datapath_id'])
    datapath.up = False
    if datapath.ready:
        event['datapath'] = datapath
        return

    raise _exc.StopPropagationException()


@APP.message('port_status')
def port_status(event):
    datapath = APP.find_datapath(event['datapath_id'])
    if datapath is not None:
        msg = event['msg']
        reason = msg['reason']
        if reason == 'DELETE':
            datapath.delete_port(port_no=msg['port_no'])
        elif reason in ('ADD', 'MODIFY'):
            datapath.add_ports([msg])
        else:
            APP.logger.warning('Unknown port_status reason: %r', event)
        if datapath.ready:
            event['datapath'] = datapath
            return

    raise _exc.StopPropagationException()


@APP.message(any)
def other_message(event):
    datapath = APP.find_datapath(event['datapath_id'])
    if datapath is not None and datapath.ready:
        event['datapath'] = datapath
        return

    raise _exc.StopPropagationException()
