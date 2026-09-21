from __future__ import annotations

from flask import Flask

from relocation_jobs.web.routes import (
    admin,
    auth,
    board,
    catalog,
    companies,
    credits,
    fetch,
    health,
    job_pages,
    jobs,
    mcp,
    payments,
    public,
    remote,
    team_docs,
)


def register_routes(app: Flask) -> None:
    for module in (
        admin,
        auth,
        board,
        catalog,
        companies,
        credits,
        fetch,
        health,
        job_pages,
        jobs,
        mcp,
        payments,
        public,
        remote,
        team_docs,
    ):
        module.register(app)
