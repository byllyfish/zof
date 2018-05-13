from zoflite.taskset import TaskSet


class Datapath:
    def __init__(self, controller, conn_id, event):
        self.zof_driver = controller.zof_driver
        self.conn_id = conn_id
        self.datapath_id = event['datapath_id']
        self.tasks = TaskSet(controller.zof_loop)

    def send(self, msg):
        """Send message to datapath."""

        msg['conn_id'] = self.conn_id
        self.zof_driver.send(msg)

    async def request(self, msg):
        """Send message to datapath and wait for reply."""

        msg['conn_id'] = self.conn_id
        return await self.zof_driver.request(msg)

    def create_task(self, coro):
        """Create managed async task associated with this datapath."""

        self.tasks.create_task(coro)

    def zof_cancel_tasks(self):
        """Cancel tasks when datapath disconnects."""

        self.tasks.cancel()
