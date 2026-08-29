import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Annotated, cast
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import AuthenticatedUser, require_user
from .config import Settings
from .journey import (
    JourneyCreateRequest,
    JourneyDocument,
    build_deterministic_journey,
    validate_journey_for_profile,
)
from .journey_workflow import (
    GoogleAdkJourneyWorkflow,
    JourneyUnavailable,
    JourneyWorkflow,
    generate_with_workflow,
)
from .matching import (
    RecommendationResponse,
    RecommendationType,
    canonicalize_profile,
    empty_recommendation,
    generate_recommendations,
)
from .profile import LearningWishProfile, SavedProfileResponse
from .synthetic_data import generate_synthetic_dataset

trace_id_context: ContextVar[str] = ContextVar("trace_id", default="")
logger = logging.getLogger("sakhicircle.api")


def create_app(
    settings: Settings | None = None,
    *,
    journey_workflow: JourneyWorkflow | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    api = FastAPI(
        title="SakhiCircle API",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.app_env != "production" else None,
        redoc_url=None,
    )
    api.state.settings = resolved_settings
    api.state.profile_store: dict[str, LearningWishProfile] = {}
    api.state.profile_model = LearningWishProfile
    api.state.journey_store: dict[str, JourneyDocument] = {}
    api.state.journey_metadata: dict[str, dict[str, str]] = {}
    api.state.matching_dataset = (
        None
        if resolved_settings.adapter_mode == "production"
        else generate_synthetic_dataset()
    )
    api.state.integration_call_counts = {"ai": 0, "paid": 0}
    configured_journey_workflow = journey_workflow
    if (
        configured_journey_workflow is None
        and resolved_settings.journey_adapter_mode == "gemini_adk"
        and resolved_settings.paid_api_calls_enabled
        and resolved_settings.gemini_api_key is not None
    ):
        configured_journey_workflow = GoogleAdkJourneyWorkflow(
            api_key=resolved_settings.gemini_api_key.get_secret_value(),
            model=resolved_settings.gemini_model,
        )
    api.state.journey_workflow = configured_journey_workflow

    api.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
    )

    @api.middleware("http")
    async def trace_requests(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
        token = trace_id_context.set(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            trace_id_context.reset(token)

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "sakhicircle-api",
            "environment": resolved_settings.app_env,
        }

    @api.get("/ready")
    async def readiness() -> dict[str, str | bool]:
        return {
            "status": "ready",
            "service": "sakhicircle-api",
            "environment": resolved_settings.app_env,
            "adapterMode": resolved_settings.adapter_mode,
            "paidApiCallsEnabled": resolved_settings.paid_api_calls_enabled,
        }

    @api.get("/api/v1/auth/session", response_model=AuthenticatedUser)
    async def auth_session(
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> AuthenticatedUser:
        return user

    @api.put("/api/v1/profile", response_model=SavedProfileResponse)
    async def save_profile(
        profile: LearningWishProfile,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> SavedProfileResponse:
        api.state.profile_store[user.uid] = profile
        return SavedProfileResponse(profile=profile)

    @api.post("/api/v1/journeys", response_model=JourneyDocument)
    async def create_journey(
        request: JourneyCreateRequest,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> JourneyDocument:
        profile = api.state.profile_store.get(user.uid)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "confirmed_profile_required",
                    "message": "Confirm your learning details before creating a journey.",
                },
            )
        if resolved_settings.journey_adapter_mode == "deterministic":
            return build_deterministic_journey(
                profile=profile,
                starts_on=request.starts_on,
                uid=user.uid,
            )
        if api.state.journey_workflow is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "journey_configuration_required",
                    "message": "The personalised journey service is not configured.",
                },
            )

        def count_attempt() -> None:
            api.state.integration_call_counts["ai"] += 1
            if resolved_settings.paid_api_calls_enabled:
                api.state.integration_call_counts["paid"] += 1

        try:
            return await generate_with_workflow(
                profile=profile,
                starts_on=request.starts_on,
                uid=user.uid,
                workflow=api.state.journey_workflow,
                attempt_timeout_seconds=resolved_settings.journey_attempt_timeout_seconds,
                on_attempt=count_attempt,
            )
        except JourneyUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "journey_unavailable",
                    "message": "A reviewed journey is unavailable. Please try again.",
                },
            ) from error

    @api.put("/api/v1/journeys/{journey_id}", response_model=JourneyDocument)
    async def confirm_journey(
        journey_id: str,
        draft: JourneyDocument,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> JourneyDocument:
        profile = api.state.profile_store.get(user.uid)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "confirmed_profile_required"},
            )
        if draft.journey_id != journey_id or draft.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_journey_confirmation"},
            )
        try:
            validate_journey_for_profile(draft, profile)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_journey_schedule", "message": str(error)},
            ) from error
        confirmed = draft.model_copy(update={"status": "confirmed"})
        api.state.journey_store[user.uid] = confirmed
        api.state.journey_metadata[user.uid] = {
            "uid": user.uid,
            "confirmedAt": datetime.now(UTC).isoformat(),
            "schemaVersion": confirmed.schema_version,
        }
        return confirmed

    @api.get(
        "/api/v1/recommendations",
        response_model=RecommendationResponse,
        response_model_exclude_none=True,
    )
    async def recommendations(
        request: Request,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
        recommendation_type: Annotated[str, Query(alias="type")],
    ) -> RecommendationResponse:
        profile = api.state.profile_store.get(user.uid)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "profile_confirmation_required",
                    "message": "Confirm your learning details before finding a match.",
                },
            )
        if not profile.matching_consent:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "matching_consent_required",
                    "message": "Review matching permission before finding a match.",
                },
            )
        if recommendation_type not in {"partner", "mentor"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "unsupported_recommendation_type"},
            )
        if set(request.query_params) != {"type"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "unsupported_recommendation_query"},
            )

        typed_recommendation = cast(RecommendationType, recommendation_type)
        dataset = api.state.matching_dataset
        if dataset is None:
            code = (
                "recommendations_configuration_required"
                if resolved_settings.adapter_mode == "production"
                else "recommendations_unavailable"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": code},
            )
        learner = canonicalize_profile(profile, dataset.hobbies)
        if learner is None:
            return empty_recommendation(typed_recommendation, "hobby_not_in_catalog")
        return generate_recommendations(
            learner=learner,
            recommendation_type=typed_recommendation,
            dataset=dataset,
            requester_candidate_id=(
                "syn_requester_0001" if user.synthetic else f"external_requester_{user.uid}"
            ),
        )

    return api


app = create_app()
