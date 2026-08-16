#!/usr/bin/sh
set -e
python3 -c "
from relocation_jobs.db import init_db
from relocation_jobs.catalog.repo import catalog_has_data
init_db()
if catalog_has_data():
    print('catalog ready')
else:
    print('catalog ready (empty - load countries via build_companies.py)')
"
exec gunicorn relocation_jobs.web.server:app \
  --bind "0.0.0.0:${PORT:-10000}" \
  --workers 1 \
  --threads 8 \
  --timeout 600 \
  --access-logfile - \
  --error-logfile -
