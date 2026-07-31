# Docker Static Validation

The final verification confirmed the production model contains a non-root `USER 10001:10001`, a readiness health check, read-only root filesystem, all Linux capabilities dropped, `no-new-privileges` and a mounted secret file. Docker Engine was unavailable in the build environment, so a live image build/start was not executed here. `scripts/deploy.sh` performs configuration validation, build, migration, start and readiness polling in a Docker-enabled environment.
