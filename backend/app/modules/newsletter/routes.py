from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.rate_limiter import RateLimiter, get_rate_limiter
from app.db.session import get_db
from app.modules.auth.dependencies import _enforce_rate_limit
from app.modules.newsletter import service
from app.modules.newsletter.schemas import NewsletterSubscribeRequest, NewsletterSubscribeResponse

router = APIRouter(prefix="/newsletter", tags=["newsletter"])

# Public, unauthenticated endpoint (any site visitor can submit an email) -- so it
# needs its own abuse guard, same shape as /auth/forgot-password: without this it's
# a free email-bombing vector against arbitrary third-party addresses.
NEWSLETTER_IP_RATE_LIMIT = 5
NEWSLETTER_IP_RATE_WINDOW_SECONDS = 3600  # 1 hour


async def _enforce_newsletter_rate_limit(
    request: Request,
    response: Response,
    rate_limiter: RateLimiter = Depends(get_rate_limiter),
) -> None:
    await _enforce_rate_limit(
        request, response, rate_limiter,
        key_prefix="newsletter", header_label="Newsletter",
        limit=NEWSLETTER_IP_RATE_LIMIT, window_seconds=NEWSLETTER_IP_RATE_WINDOW_SECONDS,
        error_detail="Too many newsletter signup attempts from this network, please try again later",
    )


@router.post("/subscribe", response_model=NewsletterSubscribeResponse)
async def subscribe(
    payload: NewsletterSubscribeRequest,
    db: AsyncSession = Depends(get_db),
    _rate_limit_check: None = Depends(_enforce_newsletter_rate_limit),
):
    status_value, message = await service.subscribe(db, email=payload.email)
    return NewsletterSubscribeResponse(status=status_value, message=message)
