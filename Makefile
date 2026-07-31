.PHONY: install run test self-test phase3-self-test seed migrate backup restore clean docker docker-prod verify

install:
	python -m pip install -r requirements-dev.txt

run:
	uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000

test:
	python -m pytest -q

self-test:
	python scripts/run_self_test.py

phase3-self-test:
	python scripts/run_phase3_self_test.py

seed:
	python scripts/seed_demo.py

migrate:
	python scripts/migrate.py

backup:
	python scripts/backup.py --label make

restore:
	@echo "Use: python scripts/restore.py path/to/backup.db --sha256 EXPECTED"

verify:
	python scripts/verify_release.py

clean:
	rm -f data/command_center.db data/command_center.db-shm data/command_center.db-wal
	rm -rf .pytest_cache **/__pycache__ release_evidence

docker:
	docker compose up --build

docker-prod:
	COMPOSE_FILE=docker-compose.production.yml ENV_FILE=.env.production ./scripts/deploy.sh
