"""Dashboard routes — main customer interface."""
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.routers.auth import get_current_user
from app.database import get_db

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
async def dashboard(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/auth/login", status_code=303)

    with get_db() as db:
        # Active failed payments
        active_failures = db.execute(
            "SELECT COUNT(*) as count FROM failed_payments WHERE user_id = ? AND status = 'pending'",
            (user["id"],),
        ).fetchone()["count"]

        # Recovered this month
        from datetime import datetime, timezone
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        stats = db.execute(
            """SELECT total_failed, total_recovered, total_amount_failed, total_amount_recovered
               FROM recovery_stats WHERE user_id = ? AND month = ?""",
            (user["id"], month),
        ).fetchone()

        # All-time stats
        all_time = db.execute(
            """SELECT
                 COALESCE(SUM(total_failed), 0) as failed,
                 COALESCE(SUM(total_recovered), 0) as recovered,
                 COALESCE(SUM(total_amount_failed), 0) as amount_failed,
                 COALESCE(SUM(total_amount_recovered), 0) as amount_recovered
               FROM recovery_stats WHERE user_id = ?""",
            (user["id"],),
        ).fetchone()

        # Recent activity
        recent = db.execute(
            """SELECT fp.*, dl.channel, dl.sent_at as last_contact
               FROM failed_payments fp
               LEFT JOIN dunning_log dl ON dl.failed_payment_id = fp.id
               WHERE fp.user_id = ?
               ORDER BY fp.created_at DESC LIMIT 10""",
            (user["id"],),
        ).fetchall()

    data = {
        "request": request,
        "user": user,
        "stripe_connected": bool(user.get("stripe_connect_active")),
        "active_failures": active_failures,
        "month_stats": dict(stats) if stats else {"total_failed": 0, "total_recovered": 0, "total_amount_failed": 0, "total_amount_recovered": 0},
        "all_time": dict(all_time),
        "recent": [dict(r) for r in recent],
        "recovery_rate": round(all_time["recovered"] / max(all_time["failed"], 1) * 100, 1),
    }

    return request.app.state.templates.TemplateResponse("dashboard.html", data)
