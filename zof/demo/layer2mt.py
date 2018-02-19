import zof


APP = zof.Application('layer2mt')


@APP.bind()
class Layer2_MT:

    @APP.message('channel_up')
    @APP.message('channel_down')
    @staticmethod
    def channel_event(event):
        APP.logger.info(event)


if __name__ == '__main__':
    zof.run()
