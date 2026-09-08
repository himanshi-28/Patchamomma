from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Experience = Literal[
    "",
    "New to this",
    "Restarting after many years",
    "Some recent practice",
    "पहली बार सीख रही हूँ",
    "कई वर्षों बाद फिर शुरू कर रही हूँ",
    "हाल में थोड़ा अभ्यास किया है",
]
Availability = Literal[
    "15 minutes · 3 days a week",
    "30 minutes · 4 days a week",
    "45 minutes · 5 days a week",
    "15 मिनट · सप्ताह में 3 दिन",
    "30 मिनट · सप्ताह में 4 दिन",
    "45 मिनट · सप्ताह में 5 दिन",
]
PlanLanguage = Literal["English", "Hindi", "English and Hindi", "अंग्रेज़ी", "हिंदी", "अंग्रेज़ी और हिंदी"]
Accessibility = Literal[
    "No support needed right now",
    "Larger text",
    "Larger text · seated alternatives",
    "अभी किसी सुविधा की ज़रूरत नहीं",
    "बड़ा टेक्स्ट",
    "बड़ा टेक्स्ट · बैठकर करने के विकल्प",
]
LearningFormat = Literal[
    "At home · individual",
    "At home · small online group",
    "In person · small group",
    "घर पर · अकेले",
    "घर पर · छोटा ऑनलाइन समूह",
    "सामने · छोटा समूह",
]


class LearningWishProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

    hobby: str = Field(min_length=1, max_length=120)
    experience: Experience
    goal: str = Field(default="", max_length=240)
    availability: Availability
    plan_weeks: Literal[2, 4, 6, 8] = Field(
        default=4,
        alias="planWeeks",
        exclude_if=lambda value: value == 4,
    )
    language: PlanLanguage
    accessibility: Accessibility
    format: LearningFormat
    plan_consent: bool = Field(alias="planConsent")
    matching_consent: bool = Field(alias="matchingConsent")
    city: str = Field(default="", max_length=80)

    @model_validator(mode="after")
    def require_plan_consent(self) -> "LearningWishProfile":
        if not self.plan_consent:
            raise ValueError("Plan consent is required before saving")
        return self


class SavedProfileResponse(BaseModel):
    status: Literal["saved"] = "saved"
    profile: LearningWishProfile
