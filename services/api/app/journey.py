import re
from datetime import date, timedelta
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .profile import LearningWishProfile

SCHEMA_VERSION = "1.0.0"
REVIEW_CONTRACT_VERSION = "safety-accessibility-v1"
PASSED_CHECKS = ["schema", "schedule", "accessibility", "safety", "localization"]
FallbackReason = Literal[
    "workflow_unavailable",
    "workflow_timeout",
    "validation_failed_twice",
    "review_failed_twice",
    "localization_failed_twice",
]
Generator = Literal["deterministic_fixture", "gemini_adk", "curated_fallback"]
ActivityKind = Literal["learn", "practice", "create", "reflect", "rest"]


def _plain_text(value: str) -> str:
    if re.search(r"https?://|www\.|<[^>]+>|```|\[[^\]]+\]\([^\)]+\)", value, re.IGNORECASE):
        raise ValueError("Journey text must be plain text without HTML, Markdown, or URLs")
    if re.search(r"ignore (the )?(previous|system)|system prompt|tool call", value, re.IGNORECASE):
        raise ValueError("Journey text cannot contain model or tool instructions")
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)


class LocalizedText(StrictModel):
    en: str = Field(min_length=1, max_length=500)
    hi: str = Field(min_length=1, max_length=500)

    @field_validator("en", "hi")
    @classmethod
    def plain_text(cls, value: str) -> str:
        return _plain_text(value)


class LocalizedTitle(LocalizedText):
    en: str = Field(min_length=1, max_length=120)
    hi: str = Field(min_length=1, max_length=120)


class LocalizedInstructions(StrictModel):
    en: list[str] = Field(min_length=1, max_length=4)
    hi: list[str] = Field(min_length=1, max_length=4)

    @field_validator("en", "hi")
    @classmethod
    def valid_steps(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 280 for value in values):
            raise ValueError("Instruction steps must contain 1 to 280 characters")
        return [_plain_text(value) for value in values]


class JourneyProvenance(StrictModel):
    generator: Generator
    attempts: int = Field(ge=0, le=2)
    fallback_used: bool = Field(alias="fallbackUsed")
    fallback_reason: FallbackReason | None = Field(alias="fallbackReason")

    @model_validator(mode="after")
    def fallback_fields_agree(self) -> "JourneyProvenance":
        fallback = self.generator == "curated_fallback"
        if self.fallback_used != fallback:
            raise ValueError("Fallback provenance must agree with the generator")
        if fallback != (self.fallback_reason is not None):
            raise ValueError("Fallback reason is required only for curated fallback")
        return self


class JourneyReview(StrictModel):
    status: Literal["passed"]
    contract_version: Literal[REVIEW_CONTRACT_VERSION] = Field(alias="contractVersion")
    passed_checks: list[
        Literal["schema", "schedule", "accessibility", "safety", "localization"]
    ] = Field(alias="passedChecks", min_length=5, max_length=5)

    @model_validator(mode="after")
    def all_checks_passed(self) -> "JourneyReview":
        if self.passed_checks != PASSED_CHECKS:
            raise ValueError("All fixed journey checks must pass in contract order")
        return self


class JourneyActivity(StrictModel):
    activity_id: str = Field(alias="activityId", pattern=r"^day-(0[1-9]|1[0-9]|2[0-8])$")
    day_number: int = Field(alias="dayNumber", ge=1, le=28)
    date: date
    kind: ActivityKind
    required: bool
    duration_minutes: int = Field(alias="durationMinutes", ge=0, le=45)
    title: LocalizedTitle
    instructions: LocalizedInstructions
    accessible_alternative: LocalizedText = Field(alias="accessibleAlternative")
    reflection_prompt: LocalizedText = Field(alias="reflectionPrompt")
    safety_note: LocalizedText = Field(alias="safetyNote")

    @model_validator(mode="after")
    def valid_rest(self) -> "JourneyActivity":
        if self.kind == "rest" and (self.required or self.duration_minutes != 0):
            raise ValueError("Rest activities must be optional and zero minutes")
        if self.kind != "rest" and not 5 <= self.duration_minutes <= 45:
            raise ValueError("Non-rest activities must last 5 to 45 minutes")
        return self


class JourneyWeek(StrictModel):
    week_number: int = Field(alias="weekNumber", ge=1, le=4)
    theme: LocalizedTitle
    outcome: LocalizedText
    activities: list[JourneyActivity] = Field(min_length=7, max_length=7)


class JourneyDocument(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = Field(alias="schemaVersion")
    journey_id: str = Field(alias="journeyId", min_length=12, max_length=120)
    status: Literal["draft", "confirmed"]
    starts_on: date = Field(alias="startsOn")
    timezone: Literal["Asia/Kolkata"]
    languages: list[Literal["en", "hi"]] = Field(min_length=2, max_length=2)
    title: LocalizedTitle
    summary: LocalizedText
    provenance: JourneyProvenance
    review: JourneyReview
    weeks: list[JourneyWeek] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def exact_calendar_structure(self) -> "JourneyDocument":
        if self.languages != ["en", "hi"]:
            raise ValueError("Journey languages must be exactly English then Hindi")
        if [week.week_number for week in self.weeks] != [1, 2, 3, 4]:
            raise ValueError("Journey weeks must be numbered 1 through 4")
        activities = [activity for week in self.weeks for activity in week.activities]
        if [activity.day_number for activity in activities] != list(range(1, 29)):
            raise ValueError("Journey days must be consecutive 1 through 28")
        for day_number, activity in enumerate(activities, start=1):
            expected_id = f"day-{day_number:02d}"
            expected_date = self.starts_on + timedelta(days=day_number - 1)
            expected_week = (day_number - 1) // 7 + 1
            actual_week = next(
                week.week_number for week in self.weeks if activity in week.activities
            )
            if activity.activity_id != expected_id or activity.date != expected_date:
                raise ValueError("Activity identity and date must agree with its day number")
            if actual_week != expected_week:
                raise ValueError("Activity week must agree with its day number")
        return self


class JourneyCreateRequest(StrictModel):
    starts_on: date = Field(alias="startsOn")


def availability_limits(profile: LearningWishProfile) -> tuple[int, int]:
    if profile.availability.startswith(("15 minutes", "15 मिनट")):
        return 15, 3
    if profile.availability.startswith(("30 minutes", "30 मिनट")):
        return 30, 4
    return 45, 5


def validate_journey_for_profile(
    journey: JourneyDocument,
    profile: LearningWishProfile,
) -> JourneyDocument:
    max_minutes, max_days = availability_limits(profile)
    for week in journey.weeks:
        required_non_rest = sum(
            activity.required and activity.kind != "rest" for activity in week.activities
        )
        if required_non_rest > max_days:
            raise ValueError("Journey exceeds confirmed days-per-week availability")
        for activity in week.activities:
            if activity.kind != "rest" and activity.duration_minutes > max_minutes:
                raise ValueError("Journey exceeds confirmed per-day availability")
    return journey


PHASES = [
    (
        ("Begin gently", "सहज शुरुआत"),
        ("Set up comfortably and learn the basic materials.", "सुविधा से तैयारी करें और बुनियादी सामग्री समझें।"),
    ),
    (
        ("Build the foundation", "बुनियाद मजबूत करें"),
        ("Practise one small technique at a steady pace.", "सहज गति से एक छोटी तकनीक का अभ्यास करें।"),
    ),
    (
        ("Create your small project", "अपना छोटा प्रोजेक्ट बनाएँ"),
        ("Bring the practised steps together toward your goal.", "अभ्यास के चरणों को अपने लक्ष्य के लिए साथ लाएँ।"),
    ),
    (
        ("Finish and reflect", "पूरा करें और विचार करें"),
        ("Finish the project and notice what you can do now.", "प्रोजेक्ट पूरा करें और अपनी नई क्षमता पहचानें।"),
    ),
]


def _activity_copy(kind: ActivityKind, day_number: int) -> dict[str, object]:
    if kind == "rest":
        return {
            "title": {"en": "Rest and notice", "hi": "आराम करें और ध्यान दें"},
            "instructions": {
                "en": ["Keep today free, or look back at one piece of work if you wish."],
                "hi": ["आज आराम करें, या चाहें तो अपने किसी एक काम को फिर देखें।"],
            },
            "accessibleAlternative": {
                "en": "Listen to your notes or describe your progress aloud instead of handling materials.",
                "hi": "सामग्री उपयोग करने के बजाय अपने नोट सुनें या अपनी प्रगति बोलकर बताएँ।",
            },
            "reflectionPrompt": {
                "en": "What would make the next practice feel comfortable?",
                "hi": "अगला अभ्यास सहज बनाने के लिए क्या मदद करेगा?",
            },
            "safetyNote": {
                "en": "Rest fully today and return only when you feel comfortable.",
                "hi": "आज पूरा आराम करें और सहज महसूस होने पर ही दोबारा शुरू करें।",
            },
        }
    if kind == "reflect":
        return {
            "title": {"en": "Review this week's practice", "hi": "इस सप्ताह के अभ्यास को देखें"},
            "instructions": {
                "en": ["Choose one practice piece and note one part you want to repeat."],
                "hi": ["अभ्यास का एक काम चुनें और वह हिस्सा लिखें जिसे फिर करना चाहती हैं।"],
            },
            "accessibleAlternative": {
                "en": "Record a short spoken reflection or ask someone to write your words.",
                "hi": "अपना छोटा विचार बोलकर रिकॉर्ड करें या किसी से अपने शब्द लिखवाएँ।",
            },
            "reflectionPrompt": {
                "en": "Which step feels clearer now?",
                "hi": "अब कौन-सा चरण अधिक स्पष्ट लगता है?",
            },
            "safetyNote": {
                "en": "Review in good light and pause if your eyes or hands feel tired.",
                "hi": "अच्छी रोशनी में देखें और आँखें या हाथ थकें तो रुकें।",
            },
        }
    action = "Learn" if kind == "learn" else "Create" if kind == "create" else "Practise"
    action_hi = "सीखें" if kind == "learn" else "बनाएँ" if kind == "create" else "अभ्यास करें"
    return {
        "title": {
            "en": f"{action} one steady step · Day {day_number}",
            "hi": f"एक सहज चरण {action_hi} · दिन {day_number}",
        },
        "instructions": {
            "en": [
                "Set out only the materials you need within easy reach.",
                "Complete one small practice step, then stop at the planned time.",
            ],
            "hi": [
                "केवल ज़रूरी सामग्री आसान पहुँच में रखें।",
                "एक छोटा अभ्यास चरण पूरा करें और तय समय पर रुकें।",
            ],
        },
        "accessibleAlternative": {
            "en": "Work seated at a table, use a raised board, and divide the step into shorter turns.",
            "hi": "मेज़ पर बैठकर, ऊँचा बोर्ड इस्तेमाल करके और चरण को छोटे हिस्सों में बाँटकर काम करें।",
        },
        "reflectionPrompt": {
            "en": "What felt easier after today's practice?",
            "hi": "आज के अभ्यास के बाद क्या आसान लगा?",
        },
        "safetyNote": {
            "en": "Use non-toxic materials, keep water away from electrical items, and pause if uncomfortable.",
            "hi": "गैर-विषैले सामान इस्तेमाल करें, पानी को बिजली के सामान से दूर रखें और असहजता होने पर रुकें।",
        },
    }


def _build_journey(
    *,
    profile: LearningWishProfile,
    starts_on: date,
    journey_id: str,
    generator: Generator,
    fallback_reason: FallbackReason | None,
    attempts: int = 0,
) -> JourneyDocument:
    max_minutes, max_days = availability_limits(profile)
    weeks: list[dict[str, object]] = []
    for week_index, (theme, outcome) in enumerate(PHASES):
        activities: list[dict[str, object]] = []
        for day_index in range(7):
            day_number = week_index * 7 + day_index + 1
            if day_index < max_days:
                kind: ActivityKind = ("learn", "practice", "practice", "create", "practice")[day_index]
                required = True
                duration = max_minutes
            elif day_index == max_days:
                kind = "reflect"
                required = False
                duration = min(10, max_minutes)
            else:
                kind = "rest"
                required = False
                duration = 0
            activities.append(
                {
                    "activityId": f"day-{day_number:02d}",
                    "dayNumber": day_number,
                    "date": starts_on + timedelta(days=day_number - 1),
                    "kind": kind,
                    "required": required,
                    "durationMinutes": duration,
                    **_activity_copy(kind, day_number),
                }
            )
        weeks.append(
            {
                "weekNumber": week_index + 1,
                "theme": {"en": theme[0], "hi": theme[1]},
                "outcome": {"en": outcome[0], "hi": outcome[1]},
                "activities": activities,
            }
        )

    fallback = generator == "curated_fallback"
    journey = JourneyDocument.model_validate(
        {
            "schemaVersion": SCHEMA_VERSION,
            "journeyId": journey_id,
            "status": "draft",
            "startsOn": starts_on,
            "timezone": "Asia/Kolkata",
            "languages": ["en", "hi"],
            "title": {
                "en": "Four steady weeks for your learning goal",
                "hi": "आपके सीखने के लक्ष्य के लिए चार सहज सप्ताह",
            },
            "summary": {
                "en": f"A reviewed plan for {profile.hobby}. Your goal: {profile.goal}.",
                "hi": f"{profile.hobby} के लिए जाँची हुई योजना। आपका लक्ष्य: {profile.goal}।",
            },
            "provenance": {
                "generator": generator,
                "attempts": attempts,
                "fallbackUsed": fallback,
                "fallbackReason": fallback_reason,
            },
            "review": {
                "status": "passed",
                "contractVersion": REVIEW_CONTRACT_VERSION,
                "passedChecks": PASSED_CHECKS,
            },
            "weeks": weeks,
        }
    )
    return validate_journey_for_profile(journey, profile)


def build_deterministic_journey(
    *, profile: LearningWishProfile, starts_on: date, uid: str
) -> JourneyDocument:
    opaque = uuid5(NAMESPACE_URL, f"sakhicircle:{uid}:{starts_on.isoformat()}:{profile.hobby}")
    return _build_journey(
        profile=profile,
        starts_on=starts_on,
        journey_id=f"journey_{opaque.hex}",
        generator="deterministic_fixture",
        fallback_reason=None,
    )


def build_curated_fallback(
    *,
    profile: LearningWishProfile,
    starts_on: date,
    journey_id: str,
    reason: FallbackReason,
    attempts: int = 0,
) -> JourneyDocument:
    return _build_journey(
        profile=profile,
        starts_on=starts_on,
        journey_id=journey_id,
        generator="curated_fallback",
        fallback_reason=reason,
        attempts=attempts,
    )
