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
    jobs,
    mcp,
    preferences,
    public,
    remote,
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
        jobs,
        mcp,
        preferences,
        public,
        remote,
    ):
        module.register(app)
