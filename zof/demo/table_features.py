import zof

APP = zof.Application('table_features', exception_fatal=True)

DESC = zof.compile('''
type: REQUEST.DESC
''')

TABLE_FEATURES = zof.compile('''
type: REQUEST.TABLE_FEATURES
msg: []
''')


async def table_features_match_fields1():
    """Get set of all fields available in OF matches.
    """
    fields = set()
    tfm_count = 0
    entry_count = 0

    async for tfm in TABLE_FEATURES.request():
        tfm_count += 1
        for tfm_entry in tfm['msg']:
            entry_count += 1
            for field in tfm_entry['match']:
                fields.add(field)

    print('Processed %d entries in %d TableFeatures messages' % (entry_count,
                                                                 tfm_count))
    return fields


async def table_features_match_fields2():
    """Get set of all fields available in OF matches.
    """
    fields = set()
    tfm_count = 0
    entry_count = 0

    tfm = await TABLE_FEATURES.request()
    tfm_count += 1
    for tfm_entry in tfm['msg']:
        entry_count += 1
        for field in tfm_entry['match']:
            fields.add(field)

    print('Processed %d entries in %d TableFeatures messages' % (entry_count,
                                                                 tfm_count))
    return fields


@APP.message('channel_up')
async def channel_up(event):
    info = await DESC.request()
    print('Description: %s %s' % (info['msg']['hw_desc'],
                                  info['msg']['sw_desc']))

    fields = await table_features_match_fields1()
    for field in sorted(list(fields)):
        print(field)

    fields2 = await table_features_match_fields2()
    assert fields2 == fields

    zof.post_event({'event': 'EXIT'})


if __name__ == '__main__':
    zof.run()
