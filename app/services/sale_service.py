from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.sale import Sale
from app.utils.enums import Channel, SaleStatus


class SaleService:
    async def list_sales(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        status: Optional[SaleStatus] = None,
        channel: Optional[Channel] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Sale], int]:
        filters = self._build_filters(
            business_id=business_id,
            status=status,
            channel=channel,
            search=search,
        )

        count_stmt = select(func.count()).select_from(Sale).where(*filters)
        total = await db.scalar(count_stmt)

        stmt = (
            select(Sale)
            .where(*filters)
            .order_by(Sale.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), int(total or 0)

    async def get_sale(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        sale_id: UUID,
    ) -> Sale | None:
        stmt = select(Sale).where(Sale.id == sale_id, Sale.business_id == business_id)
        return await db.scalar(stmt)

    async def create_sale(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        values: dict,
    ) -> Sale:
        if values.get("lead_id") is not None:
            await self._ensure_lead_belongs_to_business(
                db,
                business_id=business_id,
                lead_id=values["lead_id"],
            )

        sale = Sale(business_id=business_id, **values)
        db.add(sale)
        await db.flush()
        return sale

    async def update_sale(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        sale: Sale,
        values: dict,
    ) -> Sale:
        if values.get("lead_id") is not None:
            await self._ensure_lead_belongs_to_business(
                db,
                business_id=business_id,
                lead_id=values["lead_id"],
            )

        for field, value in values.items():
            setattr(sale, field, value)
        await db.flush()
        return sale

    async def delete_sale(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        sale_id: UUID,
    ) -> bool:
        stmt = delete(Sale).where(Sale.id == sale_id, Sale.business_id == business_id)
        result = await db.execute(stmt)
        return bool(result.rowcount)

    async def get_summary(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
    ) -> dict:
        completed_revenue = func.coalesce(
            func.sum(Sale.amount).filter(Sale.status == SaleStatus.COMPLETED),
            0,
        )
        pending_revenue = func.coalesce(
            func.sum(Sale.amount).filter(Sale.status == SaleStatus.PENDING),
            0,
        )
        refunded_revenue = func.coalesce(
            func.sum(Sale.amount).filter(Sale.status == SaleStatus.REFUNDED),
            0,
        )

        stmt = select(
            func.count(Sale.id),
            func.count(Sale.id).filter(Sale.status == SaleStatus.COMPLETED),
            func.count(Sale.id).filter(Sale.status == SaleStatus.PENDING),
            func.count(Sale.id).filter(Sale.status == SaleStatus.REFUNDED),
            completed_revenue,
            pending_revenue,
            refunded_revenue,
        ).where(Sale.business_id == business_id)

        row = (await db.execute(stmt)).one()
        total_orders = int(row[0] or 0)
        completed_orders = int(row[1] or 0)
        refunded_orders = int(row[3] or 0)
        total_revenue = Decimal(row[4] or 0)
        average_order_value = (
            total_revenue / completed_orders if completed_orders else Decimal("0")
        )
        refund_rate = (
            (Decimal(refunded_orders) / Decimal(total_orders)) * Decimal("100")
            if total_orders
            else Decimal("0")
        )

        return {
            "total_orders": total_orders,
            "completed_orders": completed_orders,
            "pending_orders": int(row[2] or 0),
            "refunded_orders": refunded_orders,
            "total_revenue": total_revenue,
            "gross_revenue": total_revenue,
            "pending_revenue": Decimal(row[5] or 0),
            "refunded_revenue": Decimal(row[6] or 0),
            "average_order_value": average_order_value.quantize(Decimal("0.01")),
            "refund_rate": refund_rate.quantize(Decimal("0.01")),
        }

    async def list_sales_for_export(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        status: Optional[SaleStatus] = None,
        channel: Optional[Channel] = None,
        search: Optional[str] = None,
    ) -> list[Sale]:
        filters = self._build_filters(
            business_id=business_id,
            status=status,
            channel=channel,
            search=search,
        )
        stmt = select(Sale).where(*filters).order_by(Sale.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    def _build_filters(
        self,
        *,
        business_id: UUID,
        status: Optional[SaleStatus] = None,
        channel: Optional[Channel] = None,
        search: Optional[str] = None,
    ) -> list:
        filters = [Sale.business_id == business_id]
        if status is not None:
            filters.append(Sale.status == status)
        if channel is not None:
            filters.append(Sale.channel == channel)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Sale.customer.ilike(pattern), Sale.product.ilike(pattern)))
        return filters

    async def _ensure_lead_belongs_to_business(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        lead_id: UUID,
    ) -> None:
        stmt = select(Lead.id).where(Lead.id == lead_id, Lead.business_id == business_id)
        if await db.scalar(stmt) is None:
            raise ValueError("Lead not found")
