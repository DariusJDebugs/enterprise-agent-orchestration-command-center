# Secure Configuration and Secrets

`APP_ENV=production` enables a strict configuration gate when `ENFORCE_SECURE_CONFIG=true`. Startup is rejected when the HMAC secret is weak, trusted hosts are unrestricted or an enabled external provider lacks its URL/model/API key.

Secrets should be supplied through protected file mounts using `AUDIT_HMAC_SECRET_FILE` and `LLM_API_KEY_FILE`. The production Compose file demonstrates a Docker secret file for the audit HMAC key.

Never commit `.env.production`, the `secrets/` directory, customer documents, API keys, database files or backups. Rotate the audit secret only with an explicit audit-retention plan because existing chain verification depends on the original key.
