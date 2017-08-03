import zof

APP = zof.Application('app_name_here')


@APP.message('packet_in')
def packet_in(event):
    APP.logger.info('packet_in message %r', event)


@APP.message(any)
def other(event):
    APP.logger.info('other message %r', event)


if __name__ == '__main__':
    zof.run()
