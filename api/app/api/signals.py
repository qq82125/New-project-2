from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.signal import (
    BatchSignalsResponse,
    SignalResponse,
    TopCompetitiveTracksResponse,
    TopGrowthCompaniesResponse,
    TopRiskRegistrationsResponse,
)
from app.services.signals_repo import (
    DEFAULT_WINDOW,
    get_entity_signal,
    get_batch_registration_signals,
    get_top_competitive_tracks,
    get_top_growth_companies,
    get_top_risk_registrations,
)

router = APIRouter(prefix='/api/signals', tags=['signals'])


@router.get('/registration/{registration_no}', response_model=SignalResponse)
def get_registration_signal(
    registration_no: str,
    as_of_date: date | None = Query(default=None, description='YYYY-MM-DD; default today'),
    db: Session = Depends(get_db),
) -> SignalResponse:
    return get_entity_signal(
        db,
        entity_type='registration',
        entity_id=str(registration_no).strip(),
        as_of_date=as_of_date,
        window=DEFAULT_WINDOW,
    )


@router.get('/track/{track_id}', response_model=SignalResponse)
def get_track_signal(
    track_id: str,
    as_of_date: date | None = Query(default=None, description='YYYY-MM-DD; default today'),
    db: Session = Depends(get_db),
) -> SignalResponse:
    return get_entity_signal(
        db,
        entity_type='track',
        entity_id=str(track_id).strip(),
        as_of_date=as_of_date,
        window=DEFAULT_WINDOW,
    )


@router.get('/company/{company_id}', response_model=SignalResponse)
def get_company_signal(
    company_id: str,
    as_of_date: date | None = Query(default=None, description='YYYY-MM-DD; default today'),
    db: Session = Depends(get_db),
) -> SignalResponse:
    return get_entity_signal(
        db,
        entity_type='company',
        entity_id=str(company_id).strip(),
        as_of_date=as_of_date,
        window=DEFAULT_WINDOW,
    )


@router.get('/top-risk-registrations', response_model=TopRiskRegistrationsResponse)
def top_risk_registrations(
    limit: int = Query(default=10, ge=1, le=100),
    as_of_date: date | None = Query(default=None, description='YYYY-MM-DD; default latest as_of_date'),
    db: Session = Depends(get_db),
) -> TopRiskRegistrationsResponse:
    return get_top_risk_registrations(db, limit=limit, as_of_date=as_of_date, window=DEFAULT_WINDOW)


@router.get('/top-competitive-tracks', response_model=TopCompetitiveTracksResponse)
def top_competitive_tracks(
    limit: int = Query(default=10, ge=1, le=100),
    as_of_date: date | None = Query(default=None, description='YYYY-MM-DD; default latest as_of_date'),
    db: Session = Depends(get_db),
) -> TopCompetitiveTracksResponse:
    return get_top_competitive_tracks(db, limit=limit, as_of_date=as_of_date, window=DEFAULT_WINDOW)


@router.get('/top-growth-companies', response_model=TopGrowthCompaniesResponse)
def top_growth_companies(
    limit: int = Query(default=10, ge=1, le=100),
    as_of_date: date | None = Query(default=None, description='YYYY-MM-DD; default latest as_of_date'),
    db: Session = Depends(get_db),
) -> TopGrowthCompaniesResponse:
    return get_top_growth_companies(db, limit=limit, as_of_date=as_of_date, window=DEFAULT_WINDOW)


@router.get('/batch', response_model=BatchSignalsResponse)
def batch_signals(
    registration_nos: str = Query(default='', description='Comma-separated registration_nos, max 200'),
    as_of_date: date | None = Query(default=None, description='YYYY-MM-DD'),
    db: Session = Depends(get_db),
) -> BatchSignalsResponse:
    raw_items = [x.strip() for x in str(registration_nos or '').split(',') if x.strip()]
    if len(raw_items) > 200:
        raise HTTPException(status_code=400, detail='registration_nos exceeds max 200')
    return get_batch_registration_signals(
        db,
        registration_nos=raw_items,
        as_of_date=as_of_date,
        window=DEFAULT_WINDOW,
    )
