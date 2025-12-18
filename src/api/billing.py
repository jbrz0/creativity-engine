import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from src.config import get_settings
from src.database.session import get_db
from src.models.user import User, Transaction, TransactionType, PlanType
from src.api.deps import get_current_user

logger = structlog.get_logger(__name__)
settings = get_settings()
router = APIRouter()

stripe.api_key = settings.stripe_secret_key


@router.post("/billing/subscription")
async def create_subscription_checkout(
    user: User = Depends(get_current_user),
):
    """Create Stripe Checkout Session for Monthly Subscription."""
    if not settings.stripe_monthly_price_id:
        raise HTTPException(status_code=500, detail="Stripe configuration missing")

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {"price": settings.stripe_monthly_price_id, "quantity": 1},
            ],
            mode="subscription",
            success_url=f"{settings.api_host}/dashboard?payment=success", # Placeholder URL
            cancel_url=f"{settings.api_host}/dashboard?payment=cancelled",
            metadata={"user_id": str(user.id), "type": "subscription"},
            client_reference_id=str(user.id),
        )
        return {"url": checkout_session.url}
    except Exception as e:
        logger.error("Stripe error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.post("/billing/addon")
async def create_addon_checkout(
    user: User = Depends(get_current_user),
):
    """Create Stripe Checkout Session for Add-on Credits."""
    if not settings.stripe_addon_price_id:
        raise HTTPException(status_code=500, detail="Stripe configuration missing")

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[
                {"price": settings.stripe_addon_price_id, "quantity": 1},
            ],
            mode="payment", # One-time payment
            success_url=f"{settings.api_host}/dashboard?payment=success",
            cancel_url=f"{settings.api_host}/dashboard?payment=cancelled",
            metadata={"user_id": str(user.id), "type": "addon"},
            client_reference_id=str(user.id),
        )
        return {"url": checkout_session.url}
    except Exception as e:
        logger.error("Stripe error", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.get("/billing/usage")
async def get_usage(
    user: User = Depends(get_current_user),
):
    """Get current credit usage and plan info."""
    return {
        "monthly_credits": user.monthly_credits,
        "addon_credits": user.addon_credits,
        "total_usable": user.total_credits,
        "plan_type": user.plan_type,
    }


@router.post("/billing/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe Webhooks."""
    payload = await request.body()
    
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        
        # Reload user
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user:
            # Check what type of purchase
            # If subscription
            if session.get("mode") == "subscription":
                user.plan_type = PlanType.PREMIUM
                user.monthly_credits = 500 # Set to Premium amount immediately? Or wait for reset logic?
                # Usually we set it now or upgrade handle. 
                # Let's just set it to 500 max logic for now or give +450 diff? 
                # Simplest: Upgrade plan, set monthly caps.
                # Actually, prompt says "if they are paying monthly they get 500". 
                # So we update plan. The credits amount might depend on if they just paid.
                # Let's give them the 500 reset now.
                user.monthly_credits = 500
                user.stripe_subscription_id = session.get("subscription")
                user.stripe_customer_id = session.get("customer")
                
                # Log transaction
                txn = Transaction(
                    user_id=user.id,
                    amount=500, # or 0 if we just consider it a reset
                    type=TransactionType.SUBSCRIPTION,
                    description="Premium Plan Subscription"
                )
                db.add(txn)

            # If add-on
            elif session.get("mode") == "payment":
                # Assuming the product was the addon one
                user.addon_credits += 250
                
                txn = Transaction(
                    user_id=user.id,
                    amount=250,
                    type=TransactionType.PURCHASE,
                    description="Add-on Credits Purchase"
                )
                db.add(txn)
            
            await db.commit()
    
    return {"status": "success"}
