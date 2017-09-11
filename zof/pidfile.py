import os


class PidFile:
    """Concrete class that represents a PID file."""

    def __init__(self, pid_path):
        self.pid_path = pid_path
        self.exists = False

    def read(self):
        """Read PID file."""
        with open(self.pid_path) as pid_file:
            return int(pid_file.read())

    def write(self):
        """Write PID file."""
        if self.exists or not self.pid_path:
            return
        with open(self.pid_path, 'w') as pid_file:
            pid_file.write(str(os.getpid()))
            self.exists = True

    def remove(self):
        """Remove PID file."""
        if not self.exists:
            return
        try:
            os.unlink(self.pid_path)
        finally:
            self.exists = False

    def __enter__(self):
        self.write()

    def __exit__(self, *args):
        self.remove()
