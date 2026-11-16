# gfr-calculator-plus — CDSS Pilot

Поддержка решений по почечному дозированию антимикробных препаратов (ванкомицин, амикацин, колистин).
Пилот, не SaMD. **Seed-дозировки обязательно утверждает клинический фармаколог до пилота.**

## Статус

| Часть | Состояние |
|---|---|
| Клиническое ядро, fail-safe, аудит с HMAC-цепочкой | готово, протестировано |
| Multi-tenancy (RLS), JWT, RBAC, онбординг организации, смена временного пароля | готово, протестировано |
| Админка (препараты, версии правил, пользователи, CSV), дашборд | готово (API + UI) |
| Frontend (React): login, calculate, audit, admin, dashboard, `/demo` | готово, 22 E2E зелёных |
| Docker-compose (postgres + migrate + api + ui), Makefile, smoke | готово, проверено |
| Kubernetes-манифесты | отменено заказчиком |
| Architecture diagram, pitch deck, `openapi.expected.yaml` + CI, k6 | **не сделано** |

## Запуск (3 команды)

```bash
cp .env.example .env        # заполнить пароли и секреты: openssl rand -hex 32
docker compose up -d --build
make smoke                  # SUPER_ADMIN_EMAIL/PASSWORD из .env должны быть в окружении
```

Интерфейс: `http://localhost` (порт `UI_PORT`), демо без входа: `/demo`. nginx проксирует `/api`, `/docs`, `/redoc`.
Прямой доступ к API (`/metrics` для Prometheus, `/health`) — только с localhost, порт `API_PORT` (8000);
через UI адрес `/metrics` наружу не отдаётся.

## Тесты

```bash
# Backend: unit + интеграционные (в реальном PostgreSQL)
docker run -d --name cdss-test-pg -e POSTGRES_USER=cdss -e POSTGRES_PASSWORD=cdss \
  -e POSTGRES_DB=cdss_test -p 55432:5432 postgres:16-alpine
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
DATABASE_URL=postgresql+psycopg://cdss:cdss@localhost:55432/cdss_test alembic upgrade head
python -m pytest tests --cov=app

# Frontend: типы + unit + сборка
make test-ui

# E2E (Playwright + axe-core, WCAG A/AA) против поднятого стека (make up)
E2E_SUPER_EMAIL=... E2E_SUPER_PASSWORD=... make test-e2e
```

Без БД интеграционные тесты пропускаются. Backend: 203 теста, покрытие 96%. Frontend: 16 unit + 22 E2E.

## Разработка фронтенда

После любого изменения API: `make gen-api` (выгружает `frontend/openapi.json` и перегенерирует
`frontend/src/api/schema.d.ts`). Все строки интерфейса — в `frontend/src/i18n/ru.json`; несуществующий
ключ — ошибка компиляции. Версии зависимостей подобраны под Node 20.9 (Vite 5, Tailwind 3,
`@axe-core/playwright` 4.10).

## Отклонения от ТЗ (и почему)

1. **Аудит append-only.** Решение врача — отдельная запись `record_type='decision'` со ссылкой
   `parent_audit_id`. В ТЗ решение пишется `UPDATE`-ом в ту же строку, но оно входит в хеш, и
   проверка цепочки всегда показывала бы разрыв. UPDATE/DELETE запрещены триггером.
2. **Цепочка на организацию** (`chain_id = org_<id>`), а не одна `default`: иначе RLS не даёт
   организации проверить цепочку, в которой перемешаны чужие записи.
3. **Хеш покрывает больше полей**, чем перечислено в ТЗ (тип записи, parent, новая доза, `decision_at`).
4. **HMAC-ключ только в env** (в ТЗ 1.3 «в БД», в 8.4 «в env»).
5. **Логин и RLS:** поиск пользователя по email — через `SECURITY DEFINER`-функцию `auth_lookup_user`.
   API работает под ролью `cdss_app` без BYPASSRLS; `super_admin` — под владельцем схемы.
6. **Схема:** добавлены `loading_dose_per_kg` (колистин, день 1), `min/max_age_years`,
   `pregnancy_contraindicated` (ТЗ требует эти проверки, но колонок не даёт), `calc_duration_ms`
   (метрики p50/p95), `must_change_password`. Две доп. причины fail-safe: `missing_weight`,
   `invalid_anthropometry`.
7. **Seed:** шаг округления ванкомицина и амикацина 50 мг (в ТЗ по умолчанию 250 — demo-сценарии
   1350 и 1050 мг иначе недостижимы). `max_daily_dose_mg` у ванкомицина **не задан**: лимит
   2000 мг/сут из ТЗ противоречит demo-сценарию 1 (1350 мг q12h = 2700 мг/сут). Решить фармакологу.
8. Тест CKD-EPI — регрессионный (значения зафиксированы по реализации), независимой сверки с
   калькулятором NKF не было. Коэффициент возраста `0.9938` по ТЗ (в старом `main.py` был `0.9931`).
9. Временный пароль возвращается в ответе API один раз; письма в пилоте не отправляются.
