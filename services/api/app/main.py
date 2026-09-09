import asyncio
import logging
from collections.abc import Callable
from contextvars import ContextVar
from typing import Annotated, Any, cast
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .analytics import (
    AnalyticsConflict,
    AnalyticsDeliveryRetry,
    AnalyticsError,
    AnalyticsKeyring,
    AnalyticsReceiptError,
    AnalyticsReceiptRequest,
    AnalyticsService,
    AnalyticsUnavailable,
    DeliveryRequest,
    InMemoryAnalyticsBackend,
    IssuedAnalyticsEvent,
    StaticTaskTokenVerifier,
    TaskAuthorizationError,
    TaskTokenVerifier,
)
from .auth import AuthenticatedUser, require_user
from .config import Settings
from .cost_controls import (
    GEMINI_DEPLOYMENT_DAILY_MAXIMUM,
    CachedCostControlReader,
    CostControlStateUnavailable,
    FirestoreCostControlSource,
)
from .journey import (
    JourneyCreateRequest,
    JourneyDocument,
    attach_video_recommendation,
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
from .persistence import (
    InMemoryJourneyRepository,
    InMemoryProfileRepository,
    InMemoryRecommendationRepository,
    JourneyRepository,
    OperationalDataUnavailable,
    ProfileRepository,
    RecommendationRepository,
    build_firestore_repositories,
)
from .profile import LearningWishProfile, SavedProfileResponse
from .profile_extraction import (
    GoogleProfileExtractor,
    ProfileExtractionRequest,
    ProfileExtractionResult,
    ProfileExtractionUnavailable,
    ProfileExtractor,
    deterministic_profile_extraction,
)
from .quotas import (
    FirestoreQuotaCounterStore,
    InMemoryQuotaCounterStore,
    QuotaExceeded,
    QuotaService,
    QuotaStoreUnavailable,
)
from .video_recommendations import (
    STATUS_MESSAGES,
    GoogleVideoGuideGenerator,
    GoogleYouTubeDiscovery,
    VideoRecommendationService,
)

trace_id_context: ContextVar[str] = ContextVar("trace_id", default="")
logger = logging.getLogger("sakhicircle.api")


def create_app(
    settings: Settings | None = None,
    *,
    journey_workflow: JourneyWorkflow | None = None,
    cost_control_reader: CachedCostControlReader | None = None,
    quota_service: QuotaService | None = None,
    analytics_service: AnalyticsService | None = None,
    task_token_verifier: TaskTokenVerifier | None = None,
    profile_repository: ProfileRepository | None = None,
    journey_repository: JourneyRepository | None = None,
    recommendation_repository: RecommendationRepository | None = None,
    profile_extractor: ProfileExtractor | None = None,
    video_recommendation_service: VideoRecommendationService | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings()
    api = FastAPI(
        title="SakhiCircle API",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.app_env != "production" else None,
        redoc_url=None,
    )
    api.state.settings = resolved_settings
    supplied_repositories = (
        profile_repository,
        journey_repository,
        recommendation_repository,
    )
    if any(repository is not None for repository in supplied_repositories) and not all(
        repository is not None for repository in supplied_repositories
    ):
        raise ValueError(
            "Profile, journey, and recommendation repositories must be supplied together"
        )
    if all(repository is None for repository in supplied_repositories):
        if resolved_settings.adapter_mode == "deterministic":
            profile_repository = InMemoryProfileRepository()
            journey_repository = InMemoryJourneyRepository()
            recommendation_repository = InMemoryRecommendationRepository()
        else:
            repositories = build_firestore_repositories(resolved_settings)
            profile_repository = repositories.profile
            journey_repository = repositories.journey
            recommendation_repository = repositories.recommendation
    assert profile_repository is not None
    assert journey_repository is not None
    assert recommendation_repository is not None
    api.state.profile_repository = profile_repository
    api.state.journey_repository = journey_repository
    api.state.recommendation_repository = recommendation_repository
    api.state.integration_call_counts = {"ai": 0, "paid": 0}
    gemini_configured = (
        resolved_settings.journey_adapter_mode == "gemini_adk"
        and resolved_settings.paid_api_calls_enabled
        and (
            resolved_settings.gemini_backend == "vertex_ai"
            or resolved_settings.gemini_api_key is not None
        )
    )
    gemini_client_options = (
        {
            "vertex_project": resolved_settings.firebase_project_id,
            "vertex_location": resolved_settings.gemini_location,
        }
        if resolved_settings.gemini_backend == "vertex_ai"
        else {
            "api_key": (
                resolved_settings.gemini_api_key.get_secret_value()
                if resolved_settings.gemini_api_key is not None
                else None
            )
        }
    )
    configured_profile_extractor = profile_extractor
    if configured_profile_extractor is None and gemini_configured:
        configured_profile_extractor = GoogleProfileExtractor(
            model=resolved_settings.gemini_model,
            timeout_seconds=resolved_settings.profile_extraction_timeout_seconds,
            **gemini_client_options,
        )
    api.state.profile_extractor = configured_profile_extractor
    configured_analytics = analytics_service
    configured_task_verifier = task_token_verifier
    if configured_analytics is None and resolved_settings.app_env != "production":
        local_project = resolved_settings.firebase_project_id or "sakhicircle-local"
        configured_analytics = AnalyticsService(
            project_id=local_project,
            environment=resolved_settings.app_env,
            keyring=AnalyticsKeyring(
                project_id=local_project,
                keys={"local-v1": b"deterministic-local-analytics-key"},
                current_version="local-v1",
            ),
            backend=InMemoryAnalyticsBackend(),
        )
    elif configured_analytics is None:
        try:
            from .analytics_google import build_production_analytics

            analytics_bindings = build_production_analytics(resolved_settings)
            configured_analytics = analytics_bindings.analytics_service
            if configured_task_verifier is None:
                configured_task_verifier = analytics_bindings.task_token_verifier
        except (AttributeError, RuntimeError, ValueError):
            configured_analytics = None
    api.state.analytics_service = configured_analytics
    api.state.task_token_verifier = configured_task_verifier or StaticTaskTokenVerifier({})
    configured_cost_controls = cost_control_reader
    configured_quota_service = quota_service
    if resolved_settings.app_env == "production":
        assert resolved_settings.firebase_project_id is not None
        if configured_cost_controls is None:
            configured_cost_controls = CachedCostControlReader(
                FirestoreCostControlSource(
                    project_id=resolved_settings.firebase_project_id,
                )
            )
        if configured_quota_service is None:
            configured_quota_service = QuotaService(
                FirestoreQuotaCounterStore(
                    project_id=resolved_settings.firebase_project_id,
                )
            )
    elif configured_quota_service is None:
        configured_quota_service = QuotaService(InMemoryQuotaCounterStore())
    api.state.cost_control_reader = configured_cost_controls
    api.state.quota_service = configured_quota_service
    configured_journey_workflow = journey_workflow
    if configured_journey_workflow is None and gemini_configured:
        configured_journey_workflow = GoogleAdkJourneyWorkflow(
            model=resolved_settings.journey_gemini_model,
            **gemini_client_options,
        )
    api.state.journey_workflow = configured_journey_workflow
    configured_video_recommendations = video_recommendation_service
    if configured_video_recommendations is None and resolved_settings.youtube_discovery_enabled:
        assert resolved_settings.youtube_api_key is not None
        configured_video_recommendations = VideoRecommendationService(
            discovery=GoogleYouTubeDiscovery(
                api_key=resolved_settings.youtube_api_key.get_secret_value(),
                timeout_seconds=resolved_settings.youtube_timeout_seconds,
            ),
            generator=GoogleVideoGuideGenerator(
                model=resolved_settings.video_guide_gemini_model,
                timeout_seconds=min(
                    15,
                    resolved_settings.video_enrichment_timeout_seconds,
                ),
                **gemini_client_options,
            ),
        )
    api.state.video_recommendation_service = configured_video_recommendations

    @api.middleware("http")
    async def trace_requests(request: Request, call_next):
        trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
        token = trace_id_context.set(trace_id)
        try:
            if (
                resolved_settings.app_env == "production"
                and request.method != "OPTIONS"
                and request.url.path.startswith("/api/v1/")
                and api.state.cost_control_reader is not None
            ):
                try:
                    controls = api.state.cost_control_reader.read()
                except CostControlStateUnavailable:
                    controls = None
                if controls is not None and controls.maintenance_mode:
                    response = JSONResponse(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={
                            "detail": {
                                "code": "maintenance_mode",
                                "message": "SakhiCircle is temporarily paused for maintenance.",
                            }
                        },
                        headers={"Retry-After": "60"},
                    )
                    response.headers["X-Trace-Id"] = trace_id
                    return response
            response = await call_next(request)
            response.headers["X-Trace-Id"] = trace_id
            return response
        finally:
            trace_id_context.reset(token)

    api.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"],
        expose_headers=[
            "X-Sakhi-Analytics-Event-Id",
            "X-Sakhi-Analytics-Receipt",
        ],
    )

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "sakhicircle-api",
            "environment": resolved_settings.app_env,
        }

    @api.get("/ready")
    async def readiness() -> Any:
        if resolved_settings.app_env == "production" and api.state.cost_control_reader is not None:
            try:
                controls = api.state.cost_control_reader.read()
            except CostControlStateUnavailable:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "status": "not_ready",
                        "service": "sakhicircle-api",
                        "environment": resolved_settings.app_env,
                        "code": "cost_controls_unavailable",
                    },
                )
            if controls.maintenance_mode:
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "status": "maintenance",
                        "service": "sakhicircle-api",
                        "environment": resolved_settings.app_env,
                        "code": "maintenance_mode",
                    },
                    headers={"Retry-After": "60"},
                )
        return {
            "status": "ready",
            "service": "sakhicircle-api",
            "environment": resolved_settings.app_env,
            "adapterMode": resolved_settings.adapter_mode,
            "paidApiCallsEnabled": resolved_settings.paid_api_calls_enabled,
        }

    def reserve_general_request(user: AuthenticatedUser) -> None:
        try:
            api.state.quota_service.reserve_general_request(user.uid)
        except QuotaExceeded as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": error.code, "message": "Please wait before trying again."},
                headers={"Retry-After": str(error.retry_after)},
            ) from error
        except QuotaStoreUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "rate_counter_unavailable"},
            ) from error

    def reserve_product_quota(
        reserve: Callable[[str], None],
        user: AuthenticatedUser,
    ) -> None:
        try:
            reserve(user.uid)
        except QuotaExceeded as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": error.code, "message": "Daily capacity has been reached."},
                headers={"Retry-After": str(error.retry_after)},
            ) from error
        except QuotaStoreUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "rate_counter_unavailable"},
            ) from error

    def expose_analytics_receipt(
        response: Response,
        user: AuthenticatedUser,
        issue: Callable[[], IssuedAnalyticsEvent],
    ) -> None:
        analytics = api.state.analytics_service
        if analytics is None:
            return
        if user.synthetic and analytics.environment == "production":
            return
        try:
            issued = issue()
        except AnalyticsError:
            return
        response.headers["X-Sakhi-Analytics-Event-Id"] = issued.event_id
        response.headers["X-Sakhi-Analytics-Receipt"] = issued.action_receipt

    def require_operational_identity(user: AuthenticatedUser) -> None:
        if resolved_settings.app_env == "production" and user.synthetic:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "production_identity_required"},
            )

    def read_profile(user: AuthenticatedUser) -> LearningWishProfile | None:
        require_operational_identity(user)
        try:
            return api.state.profile_repository.get_profile(user.uid)
        except OperationalDataUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "operational_data_unavailable"},
            ) from error

    async def enrich_journey_videos(
        journey: JourneyDocument,
        profile: LearningWishProfile,
        user: AuthenticatedUser,
        *,
        idempotency_key: str,
    ) -> JourneyDocument:
        recommendation_service = api.state.video_recommendation_service
        if recommendation_service is None:
            return journey
        try:
            api.state.quota_service.reserve_youtube_search(
                user.uid,
                idempotency_key=idempotency_key,
            )
        except (QuotaExceeded, QuotaStoreUnavailable):
            return attach_video_recommendation(
                journey,
                status="unavailable",
                message=STATUS_MESSAGES["unavailable"],
            )
        try:
            return await asyncio.wait_for(
                recommendation_service.enrich(journey, profile),
                timeout=resolved_settings.video_enrichment_timeout_seconds,
            )
        except TimeoutError:
            return attach_video_recommendation(
                journey,
                status="unavailable",
                message=STATUS_MESSAGES["unavailable"],
            )

    def read_confirmed_journey(user: AuthenticatedUser) -> JourneyDocument | None:
        require_operational_identity(user)
        try:
            return api.state.journey_repository.get_confirmed_journey(user.uid)
        except OperationalDataUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "operational_data_unavailable"},
            ) from error

    @api.get("/api/v1/auth/session", response_model=AuthenticatedUser)
    async def auth_session(
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> AuthenticatedUser:
        return user

    @api.put("/api/v1/profile", response_model=SavedProfileResponse)
    async def save_profile(
        profile: LearningWishProfile,
        response: Response,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> SavedProfileResponse:
        require_operational_identity(user)
        reserve_general_request(user)
        try:
            api.state.profile_repository.save_profile(user.uid, profile)
        except OperationalDataUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "operational_data_unavailable"},
            ) from error
        expose_analytics_receipt(
            response,
            user,
            lambda: api.state.analytics_service.issue_profile_confirmed(subject_uid=user.uid),
        )
        return SavedProfileResponse(profile=profile)

    @api.post("/api/v1/profile/extractions", response_model=ProfileExtractionResult)
    async def extract_profile(
        extraction_request: ProfileExtractionRequest,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> ProfileExtractionResult:
        require_operational_identity(user)
        reserve_general_request(user)
        extractor = api.state.profile_extractor
        if extractor is None:
            return deterministic_profile_extraction(extraction_request, source="deterministic")

        if resolved_settings.app_env == "production":
            try:
                controls = api.state.cost_control_reader.read()
            except CostControlStateUnavailable:
                return deterministic_profile_extraction(extraction_request)
            if controls.gemini_project_daily_allowance == 0:
                return deterministic_profile_extraction(extraction_request)
            try:
                api.state.quota_service.reserve_gemini_workflow(
                    user.uid,
                    project_daily_allowance=controls.gemini_project_daily_allowance,
                    subject_rolling_allowance=controls.gemini_project_daily_allowance,
                )
            except (QuotaExceeded, QuotaStoreUnavailable):
                return deterministic_profile_extraction(extraction_request)

        api.state.integration_call_counts["ai"] += 1
        if resolved_settings.paid_api_calls_enabled:
            api.state.integration_call_counts["paid"] += 1
        try:
            return await extractor.extract(extraction_request)
        except ProfileExtractionUnavailable:
            return deterministic_profile_extraction(extraction_request)

    @api.post("/api/v1/journeys", response_model=JourneyDocument)
    async def create_journey(
        request: JourneyCreateRequest,
        response: Response,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> JourneyDocument:
        reserve_general_request(user)
        profile = read_profile(user)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "confirmed_profile_required",
                    "message": "Confirm your learning details before creating a journey.",
                },
            )
        if resolved_settings.journey_adapter_mode == "deterministic":
            journey = build_deterministic_journey(
                profile=profile,
                starts_on=request.starts_on,
                uid=user.uid,
            )
        else:
            if api.state.journey_workflow is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "journey_configuration_required",
                        "message": "The personalised journey service is not configured.",
                    },
                )

            project_daily_allowance = GEMINI_DEPLOYMENT_DAILY_MAXIMUM
            if resolved_settings.app_env == "production":
                try:
                    controls = api.state.cost_control_reader.read()
                except CostControlStateUnavailable as error:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail={"code": "cost_controls_unavailable"},
                    ) from error
                project_daily_allowance = controls.gemini_project_daily_allowance
            try:
                api.state.quota_service.reserve_gemini_workflow(
                    user.uid,
                    project_daily_allowance=project_daily_allowance,
                    subject_rolling_allowance=project_daily_allowance,
                )
            except QuotaExceeded as error:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "code": error.code,
                        "message": "Daily journey capacity has been reached.",
                    },
                    headers={"Retry-After": str(error.retry_after)},
                ) from error
            except QuotaStoreUnavailable as error:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={"code": "rate_counter_unavailable"},
                ) from error

            def count_attempt() -> None:
                api.state.integration_call_counts["ai"] += 1
                if resolved_settings.paid_api_calls_enabled:
                    api.state.integration_call_counts["paid"] += 1

            try:
                journey = await generate_with_workflow(
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

        journey = await enrich_journey_videos(
            journey,
            profile,
            user,
            idempotency_key=f"{journey.journey_id}:create",
        )

        expose_analytics_receipt(
            response,
            user,
            lambda: api.state.analytics_service.issue_journey_draft_created(
                subject_uid=user.uid,
                journey_schema_version=journey.schema_version,
                generator=journey.provenance.generator,
                fallback_used=journey.provenance.fallback_used,
            ),
        )
        return journey

    @api.get("/api/v1/journeys/current", response_model=JourneyDocument)
    async def current_journey(
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> JourneyDocument:
        reserve_general_request(user)
        journey = read_confirmed_journey(user)
        if journey is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "journey_not_found"},
            )
        if (
            api.state.video_recommendation_service is not None
            and journey.video_recommendation is None
        ):
            return attach_video_recommendation(
                journey,
                status="unavailable",
                message=STATUS_MESSAGES["unavailable"],
            )
        return journey

    @api.post(
        "/api/v1/journeys/{journey_id}/video-recommendation",
        response_model=JourneyDocument,
    )
    async def refresh_video_recommendation(
        journey_id: str,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> JourneyDocument:
        reserve_general_request(user)
        profile = read_profile(user)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "confirmed_profile_required"},
            )
        try:
            current = api.state.journey_repository.get_confirmed_journey(user.uid)
        except OperationalDataUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "operational_data_unavailable"},
            ) from error
        if current is None or current.journey_id != journey_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "journey_not_found"},
            )
        refreshed = await enrich_journey_videos(
            current,
            profile,
            user,
            idempotency_key=f"{journey_id}:refresh:{uuid4().hex}",
        )
        try:
            api.state.journey_repository.save_confirmed_journey(user.uid, refreshed)
        except OperationalDataUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "operational_data_unavailable"},
            ) from error
        return refreshed

    @api.put("/api/v1/journeys/{journey_id}", response_model=JourneyDocument)
    async def confirm_journey(
        journey_id: str,
        draft: JourneyDocument,
        response: Response,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> JourneyDocument:
        reserve_general_request(user)
        profile = read_profile(user)
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
        try:
            api.state.journey_repository.save_confirmed_journey(user.uid, confirmed)
        except OperationalDataUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "operational_data_unavailable"},
            ) from error
        expose_analytics_receipt(
            response,
            user,
            lambda: api.state.analytics_service.issue_journey_confirmed(
                subject_uid=user.uid,
                journey_schema_version=confirmed.schema_version,
                generator=confirmed.provenance.generator,
                fallback_used=confirmed.provenance.fallback_used,
            ),
        )
        return confirmed

    @api.get(
        "/api/v1/recommendations",
        response_model=RecommendationResponse,
        response_model_exclude_none=True,
    )
    async def recommendations(
        request: Request,
        response: Response,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
        recommendation_type: Annotated[str, Query(alias="type")],
    ) -> RecommendationResponse:
        profile = read_profile(user)
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
        try:
            dataset = api.state.recommendation_repository.get_dataset()
        except OperationalDataUnavailable as error:
            code = (
                "recommendations_configuration_required"
                if resolved_settings.adapter_mode == "production"
                else "recommendations_unavailable"
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": code},
            ) from error
        reserve_general_request(user)
        reserve_product_quota(api.state.quota_service.reserve_recommendation, user)
        learner = canonicalize_profile(profile, dataset.hobbies)
        if learner is None:
            result = empty_recommendation(
                typed_recommendation,
                "hobby_not_in_catalog",
            )
        else:
            result = generate_recommendations(
                learner=learner,
                recommendation_type=typed_recommendation,
                dataset=dataset,
                requester_candidate_id=(
                    "syn_requester_0001" if user.synthetic else f"external_requester_{user.uid}"
                ),
            )
        expose_analytics_receipt(
            response,
            user,
            lambda: api.state.analytics_service.issue_recommendation_presented(
                subject_uid=user.uid,
                matching_contract_version=result.contract_version,
                recommendation_type=result.recommendation_type,
                outcome=result.status,
                result_count=len(result.results),
            ),
        )
        return result

    @api.post(
        "/api/v1/analytics/events",
        response_model_exclude_none=True,
    )
    async def resume_analytics_event(
        receipt_request: AnalyticsReceiptRequest,
        response: Response,
        user: Annotated[AuthenticatedUser, Depends(require_user)],
    ) -> Any:
        analytics = api.state.analytics_service
        if analytics is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "analytics_configuration_required"},
            )
        if user.synthetic and analytics.environment == "production":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "analytics_production_only"},
            )
        try:
            analytics.verify_receipt(
                subject_uid=user.uid,
                event_id=receipt_request.event_id,
                action_receipt=receipt_request.action_receipt,
            )
            api.state.quota_service.reserve_analytics_event(
                user.uid,
                receipt_request.event_id,
            )
            result = analytics.resume(
                subject_uid=user.uid,
                request=receipt_request,
            )
        except AnalyticsConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "event_id_conflict"},
            ) from error
        except AnalyticsReceiptError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_analytics_receipt"},
            ) from error
        except QuotaExceeded as error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": error.code},
                headers={"Retry-After": str(error.retry_after)},
            ) from error
        except QuotaStoreUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "rate_counter_unavailable"},
            ) from error
        except AnalyticsUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "analytics_configuration_required"},
            ) from error
        response.status_code = (
            status.HTTP_202_ACCEPTED if result.status == "queued" else status.HTTP_200_OK
        )
        return result

    @api.post("/internal/v1/analytics/deliver")
    async def deliver_analytics_event(
        delivery_request: DeliveryRequest,
        request: Request,
    ) -> Any:
        analytics = api.state.analytics_service
        if analytics is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "analytics_configuration_required"},
            )
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "task_authentication_required"},
            )
        try:
            claims = api.state.task_token_verifier.verify(authorization.removeprefix("Bearer "))
            result = analytics.deliver(
                delivery_request.delivery_handle,
                claims=claims,
            )
        except TaskAuthorizationError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "task_authentication_required"},
            ) from error
        except AnalyticsDeliveryRetry as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "analytics_delivery_retry"},
                headers={"Retry-After": "10"},
            ) from error
        except AnalyticsUnavailable as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "analytics_configuration_required"},
            ) from error
        return result

    return api


app = create_app()
