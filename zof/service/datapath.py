"""
This app retrieves a datapath's ports.

This is a guard app with high precedence. This app blocks other apps from
receiving channel_up messages until all of the datapath's ports are discovered.

This app modifies message events to include the source `datapath` object.
"""

import zof
from zof.datapath import DatapathList, CHANNEL_UP_MSG, FEATURES_MSG
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
    if datapath.ready:
        event['datapath'] = datapath
        return
    datapath.user_data[CHANNEL_UP_MSG] = event
    raise _exc.StopPropagationException()


@APP.message('channel_down')
def channel_down(event):
    datapath = APP.datapaths.delete_datapath(datapath_id=event['datapath_id'])
    datapath.up = False
    if datapath.ready:
        event['datapath'] = datapath
        return
    raise _exc.StopPropagationException()


@APP.message('features_reply')
def features_reply(event):
    datapath = APP.datapaths[event['datapath_id']]
    if datapath.ready:
        event['datapath'] = datapath
        return

    datapath.user_data[FEATURES_MSG] = event
    if event['version'] > 1:
        zof.ensure_future(
            _get_ports(datapath), datapath_id=event['datapath_id'])
    else:
        datapath.add_ports(event['msg']['ports'])
        _post_channel_up(datapath)

    raise _exc.StopPropagationException()


@APP.message('port_status')
def port_status(event):
    datapath = APP.find_datapath(event['datapath_id'])
    if datapath is not None:
        event['datapath'] = datapath
        msg = event['msg']
        reason = msg['reason']
        if reason == 'DELETE':
            datapath.delete_port(port_no=msg['port_no'])
        elif reason in ('ADD', 'MODIFY'):
            datapath.add_ports([msg])
        else:
            APP.logger.warning('Unknown port_status reason: %r', event)
        return

    raise _exc.StopPropagationException()


@APP.message(any)
def other_message(event):
    datapath = APP.find_datapath(event['datapath_id'])
    if datapath is not None:
        event['datapath'] = datapath
        return

    raise _exc.StopPropagationException()


async def _get_ports(datapath):
    try:
        ports = await PORTS_REQUEST.request(
            datapath_id=datapath.datapath_id, conn_id=datapath.conn_id)
        datapath.add_ports(ports['msg'])
        _post_channel_up(datapath)
    except _exc.ControllerException as ex:
        datapath.close()
        APP.logger.warning('_get_ports failed: %s', ex)


def _post_channel_up(datapath):
    datapath.ready = True

    channel_event = datapath.user_data.pop(CHANNEL_UP_MSG)
    channel_event['event'] = 'MESSAGE'
    zof.post_event(channel_event)

    features = datapath.user_data.pop(FEATURES_MSG)
    features['event'] = 'MESSAGE'
    zof.post_event(features)
