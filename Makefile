.PHONY: up down migrate seed smoke test test-unit test-ui test-e2e gen-api logs

up:
	docker compose up -d --build

down:
	docker compose down

# Повторный прогон миграций и seed (идемпотентно)
migrate:
	docker compose run --rm migrate

seed: migrate

# Сквозная проверка API: онбординг -> расчёт -> решение -> цепочка аудита
smoke:
	python scripts/smoke.py $${SMOKE_BASE_URL:-http://localhost:8000}

test:
	cd backend && python -m pytest tests --cov=app

test-unit:
	cd backend && python -m pytest tests/unit

# Типы + unit-тесты + сборка фронтенда
test-ui:
	cd frontend && npm run typecheck && npm test && npm run build

# E2E против поднятого стека (make up). Нужны E2E_SUPER_EMAIL / E2E_SUPER_PASSWORD
# и E2E_BASE_URL (по умолчанию http://localhost:8082)
test-e2e:
	cd frontend && npx playwright install chromium && npx playwright test

# После изменения API: выгрузить OpenAPI и перегенерировать типы клиента
gen-api:
	cd backend && python -m scripts.dump_openapi
	cd frontend && npm run gen:api

logs:
	docker compose logs -f api
