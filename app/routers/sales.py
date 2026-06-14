import csv
from io import StringIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_business
from app.database import get_db
from app.models.business import Business
from app.schemas.sale import (
    SaleCreate,
    SaleListResponse,
    SaleRead,
    SaleSummary,
    SaleUpdate,
)
from app.services.sale_service import SaleService
from app.utils.enums import Channel, SaleStatus

router = APIRouter(prefix="/api/sales", tags=["Sales"])
sale_service = SaleService()


@router.get("/", response_model=SaleListResponse)
async def list_sales(
    status_filter: Optional[SaleStatus] = Query(default=None, alias="status"),
    channel: Optional[Channel] = None,
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    sales, total = await sale_service.list_sales(
        db,
        business_id=current_business.id,
        status=status_filter,
        channel=channel,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {"items": sales, "total": total}


@router.get("/summary", response_model=SaleSummary)
async def get_sales_summary(
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    return await sale_service.get_summary(db, business_id=current_business.id)


@router.get("/export")
async def export_sales_csv(
    status_filter: Optional[SaleStatus] = Query(default=None, alias="status"),
    channel: Optional[Channel] = None,
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    sales = await sale_service.list_sales_for_export(
        db,
        business_id=current_business.id,
        status=status_filter,
        channel=channel,
        search=search,
    )

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "customer", "product", "channel", "date", "amount", "status"])
    for sale in sales:
        writer.writerow(
            [
                sale.id,
                sale.customer,
                sale.product,
                sale.channel.value,
                sale.created_at.isoformat(),
                sale.amount,
                sale.status.value,
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="sales-report.csv"'},
    )


@router.post("/", response_model=SaleRead, status_code=status.HTTP_201_CREATED)
async def create_sale(
    payload: SaleCreate,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await sale_service.create_sale(
            db,
            business_id=current_business.id,
            values=payload.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{sale_id}", response_model=SaleRead)
async def get_sale(
    sale_id: UUID,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    sale = await sale_service.get_sale(
        db,
        business_id=current_business.id,
        sale_id=sale_id,
    )
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
    return sale


@router.patch("/{sale_id}", response_model=SaleRead)
async def update_sale(
    sale_id: UUID,
    payload: SaleUpdate,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    sale = await sale_service.get_sale(
        db,
        business_id=current_business.id,
        sale_id=sale_id,
    )
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")

    try:
        return await sale_service.update_sale(
            db,
            business_id=current_business.id,
            sale=sale,
            values=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{sale_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sale(
    sale_id: UUID,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    deleted = await sale_service.delete_sale(
        db,
        business_id=current_business.id,
        sale_id=sale_id,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found")
