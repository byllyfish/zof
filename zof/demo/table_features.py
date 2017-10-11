import zof


APP = zof.Application('table_features', exception_fatal=True)

TABLE_FEATURES = zof.compile('''
type: REQUEST.TABLE_FEATURES
msg: []
''')


#@APP.event('start')
#async def start(event):
#    conn_id = await zof.connect('192.168.0.4:9600')
#    tfm = await TABLE_FEATURES.request(conn_id=conn_id)
#    #APP.logger.info(tfm)
#    zof.post_event({'event': 'EXIT'})


@APP.message('channel_up')
async def channel_up(event):
    fields = set()
    count = 0
    async for tfm in TABLE_FEATURES.request():
        count += 1
        for tfm_entry in tfm['msg']:
            for field in tfm_entry['match']:
                fields.add(field)

    print('%d messages' % count)
    for field in sorted(list(fields)):
        print(field)

    zof.post_event({'event': 'EXIT'})


if __name__ == '__main__':
    zof.run()
