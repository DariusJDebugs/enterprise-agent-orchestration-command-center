# Security Policy

## Supported release

Security fixes are applied to the latest `v3.x` pilot-beta release.

## Reporting

Do not disclose suspected vulnerabilities, credentials, sensitive documents, or exploit details in a public issue. Use the private communication channel designated by the deploying organization or the challenge platform, and include:

- affected version and component;
- impact and prerequisites;
- minimal reproduction steps;
- recommended containment, when known.

## Repository safety

Never commit real credentials, `.env` files, secret files, databases, uploads, backups, customer documents, private paths, or raw local-machine evidence. Run:

```bash
python scripts/release_hygiene.py --check
```

before every public push or release.

## Deployment boundary

This repository is a pilot-ready beta. Before real enterprise data is used, deployers must configure authenticated identity, TLS, a central secret manager, centralized immutable logs, dependency/image scanning, backup retention, malware/content-disarm controls, customer-specific privacy review, and an independent security assessment.
