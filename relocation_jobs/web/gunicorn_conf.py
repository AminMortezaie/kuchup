from __future__ import annotations

# ponytail: one worker on the 2GB host; raise if the box gets more RAM
workers = 1
threads = 8
timeout = 600
accesslog = "-"
errorlog = "-"
preload_app = False


def post_fork(server, worker):
    from relocation_jobs.core.db import reset_connection_pool_after_fork

    reset_connection_pool_after_fork()
