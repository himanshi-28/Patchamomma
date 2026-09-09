import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from urllib.parse import parse_qs, urlparse
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .profile import LearningWishProfile

SCHEMA_VERSION = "1.0.0"
FLEXIBLE_SCHEMA_VERSION = "1.1.0"
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
    activity_id: str = Field(alias="activityId", pattern=r"^day-(0[1-9]|[1-4][0-9]|5[0-6])$")
    day_number: int = Field(alias="dayNumber", ge=1, le=56)
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


class RecommendedVideo(StrictModel):
    video_id: str = Field(alias="videoId", pattern=r"^[A-Za-z0-9_-]{11}$")
    title: str = Field(min_length=1, max_length=220)
    url: str = Field(min_length=1, max_length=500)
    position: int = Field(ge=0)
    duration_seconds: int = Field(alias="durationSeconds", ge=1, le=10800)
    default_language: str | None = Field(default=None, alias="defaultLanguage", max_length=35)
    captions_available: bool = Field(alias="captionsAvailable")

    @field_validator("url")
    @classmethod
    def youtube_watch_url(cls, value: str) -> str:
        parsed = urlparse(value)
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.youtube.com"
            or parsed.path != "/watch"
            or video_id is None
            or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id)
        ):
            raise ValueError("Recommended videos must use a YouTube watch URL")
        return value

    @model_validator(mode="after")
    def url_matches_video(self) -> "RecommendedVideo":
        video_id = parse_qs(urlparse(self.url).query).get("v", [None])[0]
        if video_id != self.video_id:
            raise ValueError("YouTube video URL must match its video identifier")
        return self


class WeeklyVideoGuide(StrictModel):
    videos: list[RecommendedVideo] = Field(min_length=1, max_length=8)
    prerequisites: LocalizedInstructions
    summary: LocalizedText
    key_points: LocalizedInstructions = Field(alias="keyPoints")
    what_to_expect: LocalizedText = Field(alias="whatToExpect")
    expected_result: LocalizedText = Field(alias="expectedResult")


class RecommendedPlaylist(StrictModel):
    provider: Literal["youtube"]
    playlist_id: str = Field(alias="playlistId", pattern=r"^[A-Za-z0-9_-]{12,80}$")
    title: str = Field(min_length=1, max_length=220)
    channel_title: str = Field(alias="channelTitle", min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=500)
    selection_method: Literal["automatic"] = Field(alias="selectionMethod")
    language_match: Literal["preferred", "fallback", "unknown"] = Field(alias="languageMatch")
    default_language: str | None = Field(default=None, alias="defaultLanguage", max_length=35)
    captions_available: bool | None = Field(default=None, alias="captionsAvailable")
    selected_video_count: int = Field(alias="selectedVideoCount", ge=1, le=100)
    total_video_count: int = Field(alias="totalVideoCount", ge=1, le=500)
    selection_note: LocalizedText = Field(alias="selectionNote")
    source_note: LocalizedText = Field(alias="sourceNote")
    fetched_at: datetime = Field(alias="fetchedAt")
    expires_at: datetime = Field(alias="expiresAt")

    @field_validator("url")
    @classmethod
    def youtube_playlist_url(cls, value: str) -> str:
        parsed = urlparse(value)
        playlist_id = parse_qs(parsed.query).get("list", [None])[0]
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.youtube.com"
            or parsed.path != "/playlist"
            or playlist_id is None
        ):
            raise ValueError("Recommended playlists must use a YouTube playlist URL")
        return value

    @model_validator(mode="after")
    def valid_selection_size(self) -> "RecommendedPlaylist":
        if self.selected_video_count > self.total_video_count:
            raise ValueError("Selected video count cannot exceed the playlist size")
        playlist_id = parse_qs(urlparse(self.url).query).get("list", [None])[0]
        if playlist_id != self.playlist_id:
            raise ValueError("YouTube playlist URL must match its playlist identifier")
        if self.fetched_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("YouTube metadata timestamps must include a timezone")
        lifetime = self.expires_at.astimezone(UTC) - self.fetched_at.astimezone(UTC)
        if lifetime <= timedelta(0) or lifetime > timedelta(days=29):
            raise ValueError("YouTube metadata may be retained for at most 29 days")
        return self


class VideoRecommendation(StrictModel):
    status: Literal["recommended", "no_match", "unavailable", "not_applicable"]
    provider: Literal["youtube"] = "youtube"
    message: LocalizedText


class JourneyWeek(StrictModel):
    week_number: int = Field(alias="weekNumber", ge=1, le=8)
    theme: LocalizedTitle
    outcome: LocalizedText
    activities: list[JourneyActivity] = Field(min_length=7, max_length=7)
    video_guide: WeeklyVideoGuide | None = Field(
        default=None,
        alias="videoGuide",
        exclude_if=lambda value: value is None,
    )


class JourneyDocument(StrictModel):
    schema_version: Literal["1.0.0", "1.1.0", "1.2.0"] = Field(alias="schemaVersion")
    journey_id: str = Field(alias="journeyId", min_length=12, max_length=120)
    status: Literal["draft", "confirmed"]
    starts_on: date = Field(alias="startsOn")
    timezone: Literal["Asia/Kolkata"]
    languages: list[Literal["en", "hi"]] = Field(min_length=2, max_length=2)
    title: LocalizedTitle
    summary: LocalizedText
    provenance: JourneyProvenance
    review: JourneyReview
    video_recommendation: VideoRecommendation | None = Field(
        default=None,
        alias="videoRecommendation",
        exclude_if=lambda value: value is None,
    )
    recommended_playlist: RecommendedPlaylist | None = Field(
        default=None,
        alias="recommendedPlaylist",
        exclude_if=lambda value: value is None,
    )
    weeks: list[JourneyWeek] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def exact_calendar_structure(self) -> "JourneyDocument":
        has_video_recommendation = self.video_recommendation is not None
        recommended = (
            self.video_recommendation is not None
            and self.video_recommendation.status == "recommended"
        )
        expected_schema = schema_version_for_weeks(len(self.weeks), has_video_recommendation)
        if self.schema_version != expected_schema:
            raise ValueError("Journey schema version must agree with its timeline length")
        if self.languages != ["en", "hi"]:
            raise ValueError("Journey languages must be exactly English then Hindi")
        expected_weeks = list(range(1, len(self.weeks) + 1))
        if [week.week_number for week in self.weeks] != expected_weeks:
            raise ValueError("Journey weeks must be consecutively numbered")
        weekly_guides = [week.video_guide for week in self.weeks]
        if recommended != (self.recommended_playlist is not None):
            raise ValueError("Recommended video status must agree with playlist availability")
        if recommended != all(guide is not None for guide in weekly_guides):
            raise ValueError("A recommended playlist requires video guidance for every week")
        if recommended:
            videos = [video for guide in weekly_guides if guide for video in guide.videos]
            video_ids = [video.video_id for video in videos]
            if len(video_ids) != len(set(video_ids)):
                raise ValueError("Recommended videos must not repeat across weeks")
            if (
                self.recommended_playlist
                and len(video_ids) != self.recommended_playlist.selected_video_count
            ):
                raise ValueError("Selected video count must match the weekly lesson assignments")
        activities = [activity for week in self.weeks for activity in week.activities]
        expected_days = list(range(1, len(self.weeks) * 7 + 1))
        if [activity.day_number for activity in activities] != expected_days:
            raise ValueError("Journey days must be consecutive across the selected timeline")
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


def schema_version_for_weeks(
    plan_weeks: int,
    has_video_guide: bool = False,
) -> Literal["1.0.0", "1.1.0", "1.2.0"]:
    if has_video_guide:
        return "1.2.0"
    return SCHEMA_VERSION if plan_weeks == 4 else FLEXIBLE_SCHEMA_VERSION


def attach_video_recommendation(
    journey: JourneyDocument,
    *,
    status: Literal["recommended", "no_match", "unavailable", "not_applicable"],
    message: dict[str, str],
    playlist: dict[str, object] | None = None,
    weekly_guides: list[dict[str, object]] | None = None,
) -> JourneyDocument:
    document = journey.model_dump(by_alias=True)
    document["schemaVersion"] = schema_version_for_weeks(len(journey.weeks), True)
    document["videoRecommendation"] = {
        "status": status,
        "provider": "youtube",
        "message": message,
    }
    if status == "recommended":
        if playlist is None or weekly_guides is None:
            raise ValueError("A recommended video result requires playlist and weekly guides")
        document["recommendedPlaylist"] = playlist
        for week, weekly_guide in zip(document["weeks"], weekly_guides, strict=True):
            week["videoGuide"] = weekly_guide
    return JourneyDocument.model_validate(document)


def strip_video_recommendation(journey: JourneyDocument) -> JourneyDocument:
    document = journey.model_dump(by_alias=True)
    document.pop("videoRecommendation", None)
    document.pop("recommendedPlaylist", None)
    for week in document["weeks"]:
        week.pop("videoGuide", None)
    document["schemaVersion"] = schema_version_for_weeks(len(journey.weeks))
    return JourneyDocument.model_validate(document)


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
    if len(journey.weeks) != profile.plan_weeks:
        raise ValueError("Journey length must match the confirmed learning timeline")
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


HARP_WEEK_FOCUSES = [
    (
        ("Meet the harp", "हार्प को समझें"),
        ("Find a supported sitting position and learn how the instrument rests safely.", "सहारे के साथ बैठने की स्थिति और वाद्य को सुरक्षित रखने का तरीका समझें।"),
        ("comfortable posture and harp position", "बैठने और हार्प रखने की सहज स्थिति"),
        ("Sit with both feet supported, bring the harp gently toward you, and relax your shoulders before touching the strings.", "दोनों पैर टिकाकर बैठें, हार्प को धीरे से अपनी ओर लाएँ और तार छूने से पहले कंधे ढीले रखें।"),
    ),
    (
        ("Find notes by colour", "रंग से सुर पहचानें"),
        ("Use the coloured strings as landmarks for finding notes.", "रंगीन तारों की मदद से सुरों की जगह पहचानें।"),
        ("string colours and note names", "तारों के रंग और सुरों के नाम"),
        ("Find one red C string and the nearest blue or black F string, then say the note names as you point to them.", "एक लाल C तार और उसके पास नीला या काला F तार खोजें, फिर उनकी ओर इशारा करते हुए सुरों के नाम बोलें।"),
    ),
    (
        ("Shape a clear pluck", "साफ़ प्लक बनाना सीखें"),
        ("Produce one clear note with a relaxed hand.", "ढीले हाथ से एक साफ़ सुर निकालें।"),
        ("a relaxed one-finger pluck", "एक उँगली से सहज प्लक"),
        ("Place one fingertip on a middle string, close it gently into your palm, and listen for an even tone.", "एक उँगली का सिरा बीच के तार पर रखें, उसे धीरे से हथेली की ओर बंद करें और समान सुर सुनें।"),
    ),
    (
        ("Alternate two fingers", "दो उँगलियाँ बारी-बारी चलाएँ"),
        ("Move between two nearby notes without tightening the hand.", "हाथ में खिंचाव लाए बिना पास के दो सुरों के बीच चलें।"),
        ("alternating fingers for even notes", "समान सुरों के लिए उँगलियाँ बारी-बारी चलाना"),
        ("Alternate fingers two and one on two nearby strings, relaxing the hand briefly between each pair of notes.", "पास के दो तारों पर दूसरी और पहली उँगली बारी-बारी चलाएँ और हर दो सुरों के बीच हाथ को थोड़ा ढीला करें।"),
    ),
    (
        ("Build a four-note pattern", "चार सुरों का क्रम बनाएँ"),
        ("Connect neighbouring notes in both directions.", "पास के सुरों को दोनों दिशाओं में जोड़ें।"),
        ("a four-note rising and falling pattern", "चार सुरों का चढ़ता और उतरता क्रम"),
        ("Play four neighbouring notes upward, pause, then return downward at the same slow pace.", "पास के चार सुर ऊपर की ओर बजाएँ, रुकें, फिर उसी धीमी गति से नीचे की ओर लौटें।"),
    ),
    (
        ("Keep a steady pulse", "स्थिर ताल बनाए रखें"),
        ("Place clear notes on an even four-beat count.", "चार समान गिनतियों पर साफ़ सुर बजाएँ।"),
        ("placing notes on four steady beats", "चार स्थिर तालों पर सुर रखना"),
        ("Count four steady beats aloud and play one chosen note on each beat without rushing.", "चार स्थिर ताल ज़ोर से गिनें और बिना जल्दी किए हर ताल पर एक चुना हुआ सुर बजाएँ।"),
    ),
    (
        ("Connect a short phrase", "छोटा संगीत वाक्य जोड़ें"),
        ("Turn familiar notes into a short musical idea.", "पहचाने हुए सुरों से एक छोटा संगीत विचार बनाएँ।"),
        ("connecting notes into a short melody", "सुरों को छोटी धुन में जोड़ना"),
        ("Choose three or four familiar notes and connect them into a short phrase with one clear pause.", "तीन या चार पहचाने हुए सुर चुनें और एक साफ़ विराम के साथ उन्हें छोटे संगीत वाक्य में जोड़ें।"),
    ),
    (
        ("Play and reflect", "बजाएँ और विचार करें"),
        ("Play a complete beginner melody and notice one improvement.", "पूरी शुरुआती धुन बजाएँ और एक सुधार पहचानें।"),
        ("a complete short beginner melody", "पूरी छोटी शुरुआती धुन"),
        ("Play your short melody from start to finish, pause, then repeat only the section you most want to improve.", "अपनी छोटी धुन शुरू से अंत तक बजाएँ, रुकें, फिर केवल वह हिस्सा दोहराएँ जिसे सबसे अधिक सुधारना चाहती हैं।"),
    ),
]


def _generic_week_focuses(profile: LearningWishProfile) -> list[tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]]:
    hobby = profile.hobby
    goal = profile.goal or f"complete one small {hobby} piece"
    return [
        ((f"Get ready for {hobby}", f"{hobby} के लिए तैयारी"), ("Set up only what you need and choose a comfortable starting point.", "केवल ज़रूरी चीज़ें तैयार करें और सहज शुरुआत चुनें।"), (f"the basic parts and setup for {hobby}", f"{hobby} की बुनियादी चीज़ें और तैयारी"), (f"Name the basic parts or tools used for {hobby}, then arrange only what you need for one short practice.", f"{hobby} की बुनियादी चीज़ों या साधनों के नाम बोलें, फिर एक छोटे अभ्यास के लिए केवल ज़रूरी सामान रखें।")),
        (("Understand one example", "एक उदाहरण समझें"), (f"Notice what makes a beginner {hobby} example work.", f"समझें कि {hobby} का शुरुआती उदाहरण कैसे काम करता है।"), (f"one clear beginner example of {hobby}", f"{hobby} का एक साफ़ शुरुआती उदाहरण"), (f"Choose one beginner {hobby} example and name one detail you want to learn from it.", f"{hobby} का एक शुरुआती उदाहरण चुनें और उससे सीखने वाली एक बात का नाम बोलें।")),
        (("Learn the first technique", "पहली तकनीक सीखें"), ("Break one foundation technique into small, repeatable movements.", "एक बुनियादी तकनीक को छोटे दोहराने योग्य चरणों में बाँटें।"), (f"one foundation {hobby} technique", f"{hobby} की एक बुनियादी तकनीक"), (f"Break one foundation {hobby} technique into two small movements and practise the first movement slowly.", f"{hobby} की एक बुनियादी तकनीक को दो छोटे चरणों में बाँटें और पहला चरण धीरे-धीरे करें।")),
        (("Build steady control", "स्थिर नियंत्रण बनाएँ"), ("Repeat the foundation technique with an even pace.", "बुनियादी तकनीक को समान गति से दोहराएँ।"), (f"steady control of the foundation {hobby} technique", f"{hobby} की बुनियादी तकनीक पर स्थिर नियंत्रण"), ("Repeat the learned technique three times at the same easy pace, pausing between attempts.", "सीखी हुई तकनीक को सहज समान गति से तीन बार दोहराएँ और हर कोशिश के बीच रुकें।")),
        (("Connect two skills", "दो कौशल जोड़ें"), ("Bring two familiar steps together in one short sequence.", "दो पहचाने हुए चरणों को एक छोटे क्रम में जोड़ें।"), (f"connecting two familiar {hobby} steps", f"{hobby} के दो पहचाने हुए चरण जोड़ना"), (f"Choose two {hobby} steps you have practised and connect them once without adding a new step.", f"{hobby} के दो अभ्यास किए हुए चरण चुनें और नया चरण जोड़े बिना उन्हें एक बार जोड़ें।")),
        (("Make a first version", "पहला रूप बनाएँ"), (f"Use your practised steps toward this goal: {goal}.", f"अपने लक्ष्य की ओर अभ्यास किए हुए चरण इस्तेमाल करें: {goal}।"), (f"a first small version of {goal}", f"{goal} का पहला छोटा रूप"), (f"Use two practised {hobby} skills to make one small first version; stop before trying to perfect it.", f"{hobby} के दो अभ्यास किए कौशलों से पहला छोटा रूप बनाएँ; उसे बिल्कुल सही बनाने से पहले रुकें।")),
        (("Refine one section", "एक हिस्सा सुधारें"), ("Compare two attempts and improve one chosen detail.", "दो कोशिशों की तुलना करके एक चुनी हुई बात सुधारें।"), (f"one chosen detail in {goal}", f"{goal} की एक चुनी हुई बात"), ("Compare your first version with your goal, choose one small section, and repeat only that section.", "अपने पहले रूप की लक्ष्य से तुलना करें, एक छोटा हिस्सा चुनें और केवल वही हिस्सा दोहराएँ।")),
        (("Complete and reflect", "पूरा करें और विचार करें"), ("Complete one version and name what you can now do.", "एक रूप पूरा करें और अपनी नई क्षमता पहचानें।"), (f"a complete version of {goal}", f"{goal} का पूरा रूप"), (f"Complete one version using the {hobby} skills you practised, then name one skill that now feels clearer.", f"अभ्यास किए हुए {hobby} कौशलों से एक रूप पूरा करें, फिर उस कौशल का नाम बोलें जो अब अधिक स्पष्ट लगता है।")),
    ]


def _week_focuses(profile: LearningWishProfile) -> list[tuple[tuple[str, str], tuple[str, str], tuple[str, str], tuple[str, str]]]:
    focuses = HARP_WEEK_FOCUSES if re.search(r"\bharp\b|हार्प", profile.hobby, re.IGNORECASE) else _generic_week_focuses(profile)
    selections = {
        2: (0, 7),
        4: (0, 2, 5, 7),
        6: (0, 1, 3, 4, 6, 7),
        8: tuple(range(8)),
    }[profile.plan_weeks]
    return [focuses[index] for index in selections]


def _activity_copy(
    kind: ActivityKind,
    day_number: int,
    hobby: str,
    focus: tuple[str, str],
    instruction: tuple[str, str],
) -> dict[str, object]:
    focus_en, focus_hi = focus
    is_harp = bool(re.search(r"\bharp\b|हार्प", hobby, re.IGNORECASE))
    if kind == "rest":
        return {
            "title": {"en": f"Rest after {focus_en}", "hi": f"{focus_hi} के बाद आराम"},
            "instructions": {
                "en": [f"Keep today free, or quietly recall one thing you learned about {focus_en}."],
                "hi": [f"आज आराम करें, या {focus_hi} के बारे में सीखी हुई एक बात शांति से याद करें।"],
            },
            "accessibleAlternative": {
                "en": "Listen to your notes or describe your progress aloud instead of completing the activity.",
                "hi": "गतिविधि करने के बजाय अपने नोट सुनें या अपनी प्रगति बोलकर बताएँ।",
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
            "title": {"en": f"Review {focus_en}", "hi": f"{focus_hi} की समीक्षा"},
            "instructions": {
                "en": [f"Choose your clearest attempt at {focus_en} and note one part you want to repeat."],
                "hi": [f"{focus_hi} की अपनी सबसे साफ़ कोशिश चुनें और दोहराने वाला एक हिस्सा लिखें।"],
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
                "en": "Review at a comfortable pace and pause if you feel tired.",
                "hi": "सहज गति से जाँचें और थकान होने पर रुकें।",
            },
        }
    day_slot = (day_number - 1) % 7
    actions = ("Learn", "Try", "Repeat with control", "Connect", "Revisit")
    actions_hi = ("समझें", "कोशिश करें", "नियंत्रण से दोहराएँ", "जोड़ें", "फिर देखें")
    follow_up_en = (
        "Say the focus in your own words before beginning.",
        "Repeat it three times, with a short pause between attempts.",
        "Compare the last attempt with the first and keep the movement easy.",
        "Use it once in a short sequence without adding a new skill.",
        "Repeat your clearest attempt once, then stop at the planned time.",
    )[day_slot]
    follow_up_hi = (
        "शुरू करने से पहले इस अभ्यास को अपने शब्दों में बोलें।",
        "हर कोशिश के बीच थोड़ा रुककर इसे तीन बार दोहराएँ।",
        "आखिरी कोशिश की पहली से तुलना करें और गति सहज रखें।",
        "नया कौशल जोड़े बिना इसे एक छोटे क्रम में एक बार इस्तेमाल करें।",
        "अपनी सबसे साफ़ कोशिश एक बार दोहराएँ, फिर तय समय पर रुकें।",
    )[day_slot]
    if is_harp:
        alternatives_en = (
            "Work seated with both feet supported and the harp resting securely against you.",
            "Practise the hand movement away from the strings if holding the harp is tiring.",
            "Divide the practice into two shorter turns and relax your hand between them.",
            "Use fewer strings and a slower pace while keeping the same musical idea.",
            "Describe or hum the pattern before playing it once at a comfortable pace.",
        )
        alternatives_hi = (
            "दोनों पैर टिकाकर बैठें और हार्प को अपने पास सुरक्षित सहारा दें।",
            "हार्प पकड़ना थकाने वाला हो तो तारों से दूर केवल हाथ की गति करें।",
            "अभ्यास को दो छोटे हिस्सों में बाँटें और उनके बीच हाथ को ढीला करें।",
            "उसी संगीत विचार को रखते हुए कम तार और धीमी गति चुनें।",
            "सहज गति से एक बार बजाने से पहले क्रम को बोलकर या गुनगुनाकर बताएँ।",
        )
        safety_en = (
            "Keep the harp stable and the floor around your feet clear before you begin.",
            "Keep your shoulders low and your wrist neutral; pause if either starts to tighten.",
            "Use a gentle pluck and stop if a fingertip, hand, or shoulder feels uncomfortable.",
            "Do not adjust, tune, or replace tight strings without experienced guidance.",
            "Finish at the planned time and move the harp only after placing both feet firmly on the floor.",
        )
        safety_hi = (
            "शुरू करने से पहले हार्प को स्थिर रखें और पैरों के आसपास की जगह साफ़ रखें।",
            "कंधे नीचे और कलाई सीधी रखें; खिंचाव शुरू हो तो रुकें।",
            "हल्का प्लक करें और उँगली, हाथ या कंधे में असहजता हो तो रुकें।",
            "अनुभवी मार्गदर्शन के बिना कसे तारों को न कसें, ट्यून न करें और न बदलें।",
            "तय समय पर समाप्त करें और दोनों पैर ज़मीन पर टिकाने के बाद ही हार्प हटाएँ।",
        )
    else:
        alternatives_en = (
            f"Work seated and arrange {focus_en} within easy reach.",
            f"Practise only the smallest movement involved in {focus_en}.",
            f"Divide {focus_en} into two shorter turns with a rest between them.",
            f"Use a lighter or slower version of {focus_en} while keeping the same goal.",
            f"Describe the steps for {focus_en} aloud before trying them once.",
        )
        alternatives_hi = (
            f"बैठकर अभ्यास करें और {focus_hi} की चीज़ें आसान पहुँच में रखें।",
            f"{focus_hi} में शामिल केवल सबसे छोटी गति का अभ्यास करें।",
            f"{focus_hi} को दो छोटे हिस्सों में बाँटें और उनके बीच आराम करें।",
            f"उसी लक्ष्य के साथ {focus_hi} का हल्का या धीमा रूप चुनें।",
            f"एक बार कोशिश करने से पहले {focus_hi} के चरण ज़ोर से बोलें।",
        )
        safety_en = (
            "Keep the practice area clear and use only equipment you already understand.",
            "Keep the movement easy and pause as soon as anything feels uncomfortable.",
            "Check your posture before each repeat and avoid forcing the movement.",
            "Add no new tool or difficult step while combining the skills.",
            "Stop at the planned time even if you would like to repeat the activity again.",
        )
        safety_hi = (
            "अभ्यास की जगह साफ़ रखें और केवल वही साधन इस्तेमाल करें जिन्हें आप समझती हैं।",
            "गति सहज रखें और असहजता शुरू होते ही रुकें।",
            "हर बार दोहराने से पहले बैठने या खड़े होने की स्थिति जाँचें और गति पर ज़ोर न डालें।",
            "कौशल जोड़ते समय कोई नया साधन या कठिन चरण न जोड़ें।",
            "दोबारा करने की इच्छा हो तब भी तय समय पर रुकें।",
        )
    reflections_en = (
        f"Which part of {focus_en} is clear enough to explain in your own words?",
        f"What felt different on the third try at {focus_en}?",
        f"Which movement in {focus_en} became more even today?",
        f"What stayed clear when you connected {focus_en} into a short sequence?",
        f"What is one improvement you noticed in {focus_en} this week?",
    )
    reflections_hi = (
        f"{focus_hi} का कौन-सा हिस्सा आप अपने शब्दों में समझा सकती हैं?",
        f"{focus_hi} की तीसरी कोशिश में क्या अलग लगा?",
        f"{focus_hi} की कौन-सी गति आज अधिक समान हुई?",
        f"{focus_hi} को छोटे क्रम में जोड़ते समय क्या स्पष्ट रहा?",
        f"इस सप्ताह {focus_hi} में आपने कौन-सा एक सुधार देखा?",
    )
    return {
        "title": {
            "en": f"{actions[day_slot]}: {focus_en}",
            "hi": f"{focus_hi}: {actions_hi[day_slot]}",
        },
        "instructions": {
            "en": [instruction[0], follow_up_en],
            "hi": [instruction[1], follow_up_hi],
        },
        "accessibleAlternative": {
            "en": alternatives_en[day_slot],
            "hi": alternatives_hi[day_slot],
        },
        "reflectionPrompt": {
            "en": reflections_en[day_slot],
            "hi": reflections_hi[day_slot],
        },
        "safetyNote": {
            "en": safety_en[day_slot],
            "hi": safety_hi[day_slot],
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
    english_weeks = {2: "Two", 4: "Four", 6: "Six", 8: "Eight"}[profile.plan_weeks]
    hindi_weeks = {2: "दो", 4: "चार", 6: "छह", 8: "आठ"}[profile.plan_weeks]
    weeks: list[dict[str, object]] = []
    for week_index, (theme, outcome, focus, instruction) in enumerate(_week_focuses(profile)):
        activities: list[dict[str, object]] = []
        for day_index in range(7):
            day_number = week_index * 7 + day_index + 1
            if day_index < max_days:
                kind: ActivityKind = ("learn", "practice", "practice", "create", "practice")[
                    day_index
                ]
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
                    **_activity_copy(kind, day_number, profile.hobby, focus, instruction),
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
            "schemaVersion": schema_version_for_weeks(profile.plan_weeks),
            "journeyId": journey_id,
            "status": "draft",
            "startsOn": starts_on,
            "timezone": "Asia/Kolkata",
            "languages": ["en", "hi"],
            "title": {
                "en": f"{english_weeks} steady weeks for {profile.hobby}",
                "hi": f"{profile.hobby} के लिए {hindi_weeks} सहज सप्ताह",
            },
            "summary": {
                "en": (
                    f"A reviewed plan for {profile.hobby}. Your goal: {profile.goal}."
                    if profile.goal
                    else f"A reviewed plan for {profile.hobby}."
                ),
                "hi": (
                    f"{profile.hobby} के लिए जाँची हुई योजना। आपका लक्ष्य: {profile.goal}।"
                    if profile.goal
                    else f"{profile.hobby} के लिए जाँची हुई योजना।"
                ),
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
