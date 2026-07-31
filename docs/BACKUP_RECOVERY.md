# Backup and Recovery

## Create an integrity-checked backup

```bash
python scripts/backup.py --label pre-upgrade
```

The command uses SQLite's online backup API, runs `PRAGMA integrity_check`, writes a SHA-256 manifest and leaves the source database online.

## Restore

Stop writers, then run:

```bash
python scripts/restore.py data/backups/command-center-TIMESTAMP-pre-upgrade.db \
  --sha256 EXPECTED_SHA256
python scripts/migrate.py
```

Restore validates the checksum and database integrity before atomically replacing the target. After restoration, start the service and verify `/api/readiness`, mission history and the audit chain.

## Suggested pilot policy

Create daily encrypted backups, retain seven daily and four weekly copies, keep at least one copy outside the application host and perform a restore drill before onboarding live enterprise data. Exact RPO/RTO must be agreed with the deploying organization.
