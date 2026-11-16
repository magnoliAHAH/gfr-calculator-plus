"""Дашборд метрик (ТЗ 4.6, 6.6)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.dashboard_metrics import compute_metrics
from app.deps import DASHBOARD_ROLES, CurrentUser, require_roles, user_tx
from app.schemas_admin import DashboardMetrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _period(from_: datetime | None, to: datetime | None) -> tuple[datetime, datetime]:
    end = to or datetime.now(timezone.utc)
    return (from_ or end - timedelta(days=30)), end


@router.get("/metrics", response_model=DashboardMetrics, response_model_by_alias=True,
            summary="Метрики за период (по умолчанию 30 дней)")
def metrics(from_: datetime | None = Query(default=None, alias="from"), to: datetime | None = None,
            user: CurrentUser = Depends(require_roles(*DASHBOARD_ROLES))) -> dict:
    start, end = _period(from_, to)
    with user_tx(user) as conn:
        return compute_metrics(conn, user.organization_id, start, end)


@router.get("/export", summary="Экспорт метрик в CSV")
def export_csv(from_: datetime | None = Query(default=None, alias="from"), to: datetime | None = None,
               user: CurrentUser = Depends(require_roles(*DASHBOARD_ROLES))) -> Response:
    start, end = _period(from_, to)
    with user_tx(user) as conn:
        m = compute_metrics(conn, user.organization_id, start, end)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["section", "key", "value"])
    w.writerow(["period", "from", m["period"]["from"].isoformat()])
    w.writerow(["period", "to", m["period"]["to"].isoformat()])
    for k, v in m["recommendations"].items():
        w.writerow(["recommendations", k, v])
    for r in m["override_reasons_top"]:
        w.writerow(["override_reason", r["code"], r["count"]])
    for r in m["drugs_top"]:
        w.writerow(["drug", r["code"], r["count"]])
    for r in m["renal_function_histogram"]:
        w.writerow(["renal_function", r["bucket"], r["count"]])
    w.writerow(["performance", "p50_ms", m["performance"]["p50_ms"]])
    w.writerow(["performance", "p95_ms", m["performance"]["p95_ms"]])
    w.writerow(["audit_chain", "valid", m["audit_chain"]["valid"]])
    w.writerow(["audit_chain", "total_records", m["audit_chain"]["total_records"]])
    w.writerow(["failsafe_rate_pct", "", m["failsafe_rate"]])
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="dashboard.csv"'})
