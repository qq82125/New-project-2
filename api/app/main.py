from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Company, Registration
from app.repositories.products import get_company, get_product, search_products
from app.repositories.source_runs import latest_runs
from app.schemas.api import (
    CompanyOut,
    ProductOut,
    RegistrationOut,
    SearchItem,
    SearchResponse,
    StatusItem,
    StatusResponse,
)

app = FastAPI(title='NMPA IVD 查询工具 API', version='0.1.0')


def serialize_product(product) -> ProductOut:
    company = None
    if product.company:
        company = CompanyOut(id=product.company.id, name=product.company.name, country=product.company.country)

    registration = None
    if product.registration:
        registration = RegistrationOut(
            id=product.registration.id,
            registration_no=product.registration.registration_no,
            filing_no=product.registration.filing_no,
            status=product.registration.status,
        )

    return ProductOut(
        id=product.id,
        udi_di=product.udi_di,
        name=product.name,
        model=product.model,
        specification=product.specification,
        category=product.category,
        company=company,
        registration=registration,
    )


@app.get('/search', response_model=SearchResponse)
def search(
    q: str | None = Query(default=None),
    company: str | None = Query(default=None),
    registration_no: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> SearchResponse:
    products, total = search_products(db, q, company, registration_no, page, page_size)
    items = [
        SearchItem(
            product=serialize_product(item),
            highlight=(item.name.replace(q, f'<mark>{q}</mark>') if q and q in item.name else None),
        )
        for item in products
    ]
    return SearchResponse(total=total, page=page, page_size=page_size, items=items)


@app.get('/product/{product_id}', response_model=ProductOut)
def product_detail(product_id: str, db: Session = Depends(get_db)) -> ProductOut:
    product = get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail='Product not found')
    return serialize_product(product)


@app.get('/company/{company_id}', response_model=CompanyOut)
def company_detail(company_id: str, db: Session = Depends(get_db)) -> CompanyOut:
    company = get_company(db, company_id)
    if not company:
        raise HTTPException(status_code=404, detail='Company not found')
    return CompanyOut(id=company.id, name=company.name, country=company.country)


@app.get('/status', response_model=StatusResponse)
def status(db: Session = Depends(get_db)) -> StatusResponse:
    runs = latest_runs(db)
    return StatusResponse(
        latest_runs=[
            StatusItem(
                id=run.id,
                source=run.source,
                package_name=run.package_name,
                status=run.status,
                started_at=run.started_at,
                finished_at=run.finished_at,
                message=run.message,
            )
            for run in runs
        ]
    )
