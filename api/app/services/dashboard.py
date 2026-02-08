from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.radar import expiring_registrations, new_company_ranking, weekly_category_trends
from app.schemas.api import DashboardResponse, DashboardTopItem, DashboardTrendItem


def build_dashboard(db: Session) -> DashboardResponse:
    trends = weekly_category_trends(db)
    ranking = new_company_ranking(db)
    expiring = expiring_registrations(db)

    return DashboardResponse(
        weekly_category_trends=[
            DashboardTrendItem(week=str(item[0]), category=item[1], count=item[2]) for item in trends
        ],
        new_company_ranking=[DashboardTopItem(label=item[0], count=item[1]) for item in ranking],
        expiring_registrations=[DashboardTopItem(label=item[0], count=item[1]) for item in expiring],
    )
