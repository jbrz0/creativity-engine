import asyncio
import structlog
from sqlalchemy import select, update
from src.database.session import AsyncSessionLocal
from src.models.user import User, PlanType, Transaction, TransactionType

logger = structlog.get_logger(__name__)

async def reset_credits():
    """Reset monthly credits for all users."""
    logger.info("Starting monthly credit reset")
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Reset FREE users to 50
            stmt_free = (
                update(User)
                .where(User.plan_type == PlanType.FREE)
                .values(monthly_credits=50)
            )
            await session.execute(stmt_free)
            
            # 2. Reset PREMIUM users to 500
            stmt_premium = (
                update(User)
                .where(User.plan_type == PlanType.PREMIUM)
                .values(monthly_credits=500)
            )
            await session.execute(stmt_premium)
            
            # Log the reset event (optional: log individual transactions if strict auditing required, 
            # here we just log the batch action for simplicity or we could iterate users to create txn records.
            # For scale, batch update is better. We can create a single 'system' log or rely on logs.)
            
            await session.commit()
            logger.info("Successfully reset monthly credits")
            
        except Exception as e:
            logger.error("Failed to reset credits", error=str(e))
            await session.rollback()

if __name__ == "__main__":
    asyncio.run(reset_credits())
