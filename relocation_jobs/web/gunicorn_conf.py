from __future__ import annotations

workers = 2
threads = 8
timeout = 600
accesslog = "-"
errorlog = "-"
preload_app = False


def post_fork(server, worker):
    from relocation_jobs.core.db import reset_connection_pool_after_fork

    reset_connection_pool_after_fork()
