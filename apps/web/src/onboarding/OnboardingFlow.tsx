import { Check, ChevronDown, Mic, Pencil, RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  extractLearningWish,
  type LearningWish,
  type Locale,
  type ProfileGateway,
  TranscriptCaptureError,
  type TranscriptCaptureFailure,
  type TranscriptAdapter,
} from "./runtime";

interface OnboardingFlowProps {
  locale: Locale;
  transcriptAdapter: TranscriptAdapter;
  profileGateway: ProfileGateway;
  onConfirmed?: (profile: LearningWish) => void;
}

type Stage = "capture" | "review" | "success";
type FieldKey = keyof Pick<LearningWish, "hobby" | "experience" | "goal" | "availability" | "language" | "accessibility" | "format" | "city">;
type GroupKey = "learning" | "comfort" | "permission";

const requiredFields: FieldKey[] = ["hobby", "experience", "goal", "availability", "language", "accessibility", "format"];

const fieldGroups: Record<GroupKey, FieldKey[]> = {
  learning: ["hobby", "experience", "goal"],
  comfort: ["availability", "accessibility"],
  permission: ["language", "format", "city"],
};

const options: Partial<Record<FieldKey, Record<Locale, string[]>>> = {
  experience: {
    en: ["New to this", "Restarting after many years", "Some recent practice"],
    hi: ["पहली बार सीख रही हूँ", "कई वर्षों बाद फिर शुरू कर रही हूँ", "हाल में थोड़ा अभ्यास किया है"],
  },
  availability: {
    en: ["15 minutes · 3 days a week", "30 minutes · 4 days a week", "45 minutes · 5 days a week"],
    hi: ["15 मिनट · सप्ताह में 3 दिन", "30 मिनट · सप्ताह में 4 दिन", "45 मिनट · सप्ताह में 5 दिन"],
  },
  language: { en: ["English", "Hindi", "English and Hindi"], hi: ["अंग्रेज़ी", "हिंदी", "अंग्रेज़ी और हिंदी"] },
  accessibility: {
    en: ["No support needed right now", "Larger text", "Larger text · seated alternatives"],
    hi: ["अभी किसी सुविधा की ज़रूरत नहीं", "बड़ा टेक्स्ट", "बड़ा टेक्स्ट · बैठकर करने के विकल्प"],
  },
  format: {
    en: ["At home · individual", "At home · small online group", "In person · small group"],
    hi: ["घर पर · अकेले", "घर पर · छोटा ऑनलाइन समूह", "सामने · छोटा समूह"],
  },
};

const copy = {
  en: {
    captureTitle: "Share your learning wish",
    captureIntro: "Speak or type in your own words. Include what you want to learn, your first goal, and time that feels realistic.",
    wishLabel: "Your learning wish",
    typeStatus: "Typing works just as well.",
    startSpeaking: "Start speaking",
    listening: "Listening…",
    reviewAction: "Review my details",
    privacy: "SakhiCircle never records or stores raw audio. Nothing is saved until you confirm.",
    voiceErrors: {
      permission_denied: "Microphone access was not allowed. Continue by typing above.",
      unsupported: "Voice input is not supported in this browser. Continue by typing above.",
      no_speech: "We did not hear any words. Try speaking again or continue by typing above.",
      unavailable: "Voice input is unavailable right now. Continue by typing above or try again.",
    },
    reviewTitle: "Review before saving",
    nothingSaved: "Nothing has been saved",
    reviewIntro: "Check your words, then review each detail. You can change anything before confirming.",
    transcriptSummary: "1. Check your words",
    transcriptLabel: "Editable transcript",
    transcriptRight: "My words look right",
    update: "Update details from my words",
    groups: { learning: "Learning", comfort: "Time & comfort", permission: "Preferences & permission" },
    labels: {
      hobby: "What would you like to learn?",
      experience: "Your experience",
      goal: "Your first goal",
      availability: "Time you can give",
      language: "Plan language",
      accessibility: "What would make learning easier?",
      format: "How you prefer to learn",
      city: "City (optional)",
    },
    edit: "Edit",
    saveDetail: "Save detail",
    missing: "Please add this",
    changed: "Updated from your words",
    planConsent: "I agree SakhiCircle may use these reviewed details to create my private 4-week plan.",
    matchingConsent: "Also use hobby, language, schedule, format and city to suggest compatible people. You can change this later.",
    matchingHelp: "Optional. This is not needed to create your plan.",
    back: "Back to my words",
    confirm: "Confirm and create my 4-week plan",
    saving: "Saving reviewed details…",
    storage: "After confirmation, only reviewed structured details are saved. The transcript is discarded; raw audio is never stored.",
    saveError: "Your details were not saved. Check your connection and retry; your reviewed draft is still here.",
    retry: "Retry saving",
    successTitle: "Your plan is ready to build",
    successBody: "The reviewed details were accepted. The transcript was discarded.",
    reviewPlan: "Review my four-week plan",
  },
  hi: {
    captureTitle: "अपनी सीखने की इच्छा बताएँ",
    captureIntro: "अपने शब्दों में बोलें या लिखें। क्या सीखना है, पहला लक्ष्य और जितना समय देना आसान लगे—यह सब बताएँ।",
    wishLabel: "आपकी सीखने की इच्छा",
    typeStatus: "लिखकर बताना भी उतना ही आसान है।",
    startSpeaking: "बोलना शुरू करें",
    listening: "सुन रही हूँ…",
    reviewAction: "मेरे विवरण जाँचें",
    privacy: "SakhiCircle कच्ची ऑडियो रिकॉर्ड या सेव नहीं करता। आपकी पुष्टि तक कुछ भी सेव नहीं होता।",
    voiceErrors: {
      permission_denied: "माइक्रोफ़ोन की अनुमति नहीं मिली। ऊपर लिखकर जारी रखें।",
      unsupported: "यह ब्राउज़र वॉइस इनपुट का समर्थन नहीं करता। ऊपर लिखकर जारी रखें।",
      no_speech: "कोई शब्द सुनाई नहीं दिए। फिर बोलें या ऊपर लिखकर जारी रखें।",
      unavailable: "वॉइस इनपुट अभी उपलब्ध नहीं है। ऊपर लिखकर जारी रखें या फिर कोशिश करें।",
    },
    reviewTitle: "सेव करने से पहले जाँचें",
    nothingSaved: "अभी कुछ भी सेव नहीं हुआ है",
    reviewIntro: "अपने शब्द और हर विवरण जाँचें। पुष्टि से पहले आप कुछ भी बदल सकती हैं।",
    transcriptSummary: "1. अपने शब्द जाँचें",
    transcriptLabel: "बदली जा सकने वाली ट्रांसक्रिप्ट",
    transcriptRight: "मेरे शब्द सही हैं",
    update: "मेरे शब्दों से विवरण अपडेट करें",
    groups: { learning: "सीखना", comfort: "समय और सुविधा", permission: "पसंद और अनुमति" },
    labels: {
      hobby: "आप क्या सीखना चाहती हैं?",
      experience: "आपका अनुभव",
      goal: "आपका पहला लक्ष्य",
      availability: "आप कितना समय दे सकती हैं?",
      language: "योजना की भाषा",
      accessibility: "सीखना आसान बनाने के लिए क्या चाहिए?",
      format: "आप कैसे सीखना पसंद करेंगी?",
      city: "शहर (वैकल्पिक)",
    },
    edit: "बदलें",
    saveDetail: "विवरण सेव करें",
    missing: "यह विवरण जोड़ें",
    changed: "आपके शब्दों से बदला गया",
    planConsent: "मैं सहमत हूँ कि SakhiCircle इन जाँचे हुए विवरणों से मेरी निजी 4-सप्ताह की योजना बनाए।",
    matchingConsent: "शौक, भाषा, समय, सीखने का तरीका और शहर इस्तेमाल करके उपयुक्त लोगों के सुझाव भी दें। इसे बाद में बदल सकती हैं।",
    matchingHelp: "वैकल्पिक। आपकी योजना बनाने के लिए यह ज़रूरी नहीं है।",
    back: "अपने शब्दों पर वापस जाएँ",
    confirm: "पुष्टि करें और मेरी 4-सप्ताह की योजना बनाएँ",
    saving: "जाँचे हुए विवरण सेव हो रहे हैं…",
    storage: "पुष्टि के बाद केवल जाँचे हुए विवरण सेव होंगे। ट्रांसक्रिप्ट हटा दी जाएगी और कच्ची ऑडियो कभी सेव नहीं होगी।",
    saveError: "आपके विवरण सेव नहीं हुए। कनेक्शन जाँचकर फिर कोशिश करें; आपका जाँचा हुआ ड्राफ़्ट यहीं है।",
    retry: "फिर सेव करें",
    successTitle: "आपकी योजना बनने के लिए तैयार है",
    successBody: "जाँचे हुए विवरण स्वीकार हुए। ट्रांसक्रिप्ट हटा दी गई।",
    reviewPlan: "मेरी चार-सप्ताह की योजना देखें",
  },
} as const;

export function OnboardingFlow({ locale, transcriptAdapter, profileGateway, onConfirmed }: OnboardingFlowProps) {
  const [stage, setStage] = useState<Stage>("capture");
  const [transcript, setTranscript] = useState("");
  const [wish, setWish] = useState<LearningWish>(() => extractLearningWish("", locale));
  const [transcriptReviewed, setTranscriptReviewed] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [voiceError, setVoiceError] = useState<TranscriptCaptureFailure | null>(null);
  const [editing, setEditing] = useState<FieldKey | null>(null);
  const [pendingEdit, setPendingEdit] = useState("");
  const [activeGroup, setActiveGroup] = useState<GroupKey>("learning");
  const [changedFields, setChangedFields] = useState<Set<FieldKey>>(new Set());
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(false);
  const reviewHeading = useRef<HTMLHeadingElement>(null);
  const successHeading = useRef<HTMLHeadingElement>(null);
  const voiceErrorRef = useRef<HTMLParagraphElement>(null);
  const text = copy[locale];

  useEffect(() => {
    if (stage === "review") reviewHeading.current?.focus();
    if (stage === "success") successHeading.current?.focus();
  }, [stage]);

  useEffect(() => {
    if (voiceError) voiceErrorRef.current?.focus();
  }, [voiceError]);

  const review = () => {
    const extracted = extractLearningWish(transcript, locale);
    setWish((current) => ({ ...extracted, planConsent: current.planConsent, matchingConsent: current.matchingConsent }));
    setTranscriptReviewed(false);
    setStage("review");
  };

  const captureVoice = async () => {
    setCapturing(true);
    setVoiceError(null);
    try {
      const result = await transcriptAdapter.capture(locale);
      setTranscript(result.transcript);
      setTranscriptReviewed(false);
    } catch (error) {
      setVoiceError(error instanceof TranscriptCaptureError ? error.reason : "unavailable");
    } finally {
      setCapturing(false);
    }
  };

  const updateDetails = () => {
    const extracted = extractLearningWish(transcript, locale);
    const changed = new Set<FieldKey>();
    for (const key of [...requiredFields, "city" as const]) {
      if (extracted[key] !== wish[key]) changed.add(key);
    }
    setWish({ ...extracted, planConsent: wish.planConsent, matchingConsent: wish.matchingConsent });
    setChangedFields(changed);
    setTranscriptReviewed(false);
  };

  const beginEdit = (key: FieldKey) => {
    setEditing(key);
    setPendingEdit(wish[key]);
  };

  const saveEdit = (key: FieldKey) => {
    setWish((current) => ({ ...current, [key]: pendingEdit.trim() }));
    setChangedFields((current) => new Set(current).add(key));
    setEditing(null);
  };

  const saveProfile = async () => {
    setSaving(true);
    setSaveError(false);
    try {
      await profileGateway.save(wish);
      setTranscript("");
      setStage("success");
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  };

  const complete = requiredFields.every((key) => wish[key].trim()) && wish.planConsent && transcriptReviewed;

  if (stage === "success") {
    return (
      <section className="onboarding-success" aria-labelledby="onboarding-success-title">
        <span className="success-mark" aria-hidden="true"><Check /></span>
        <div>
          <h1 id="onboarding-success-title" ref={successHeading} data-screen-heading tabIndex={-1}>{text.successTitle}</h1>
          <p>{text.successBody}</p>
          {onConfirmed && (
            <button className="primary-button onboarding-plan-action" type="button" onClick={() => onConfirmed(wish)}>
              {text.reviewPlan}
            </button>
          )}
        </div>
      </section>
    );
  }

  if (stage === "capture") {
    return (
      <section className="onboarding-flow capture-stage" aria-labelledby="onboarding-capture-title">
        <div className="onboarding-heading">
          <p className="section-label">{locale === "en" ? "Your next step" : "आपका अगला कदम"}</p>
          <h1 id="onboarding-capture-title" data-screen-heading tabIndex={-1}>{text.captureTitle}</h1>
          <p>{text.captureIntro}</p>
        </div>
        <div className="capture-panel">
          <label htmlFor="learning-wish">{text.wishLabel}</label>
          <textarea
            id="learning-wish"
            value={transcript}
            onChange={(event) => {
              setTranscript(event.target.value);
              setTranscriptReviewed(false);
              setVoiceError(null);
            }}
            rows={6}
          />
          <div className="voice-row">
            <button className="secondary-button" type="button" onClick={captureVoice} disabled={capturing}>
              <Mic aria-hidden="true" />
              {capturing ? text.listening : text.startSpeaking}
            </button>
            <p role="status">{capturing ? text.listening : text.typeStatus}</p>
          </div>
          {voiceError && (
            <p className="voice-error" role="alert" ref={voiceErrorRef} tabIndex={-1}>
              {text.voiceErrors[voiceError]}
            </p>
          )}
          <div className="provider-disclosure">
            <strong>{transcriptAdapter.providerName}</strong>
            <span>{transcriptAdapter.providerPolicy}</span>
          </div>
        </div>
        <p className="privacy-note"><Check aria-hidden="true" />{text.privacy}</p>
        <button className="primary-button onboarding-primary" type="button" onClick={review} disabled={!transcript.trim()}>
          {text.reviewAction}
        </button>
      </section>
    );
  }

  return (
    <section className="onboarding-flow review-stage" aria-labelledby="onboarding-review-title">
      <div className="onboarding-heading">
        <p className="not-saved"><Check aria-hidden="true" />{text.nothingSaved}</p>
        <h1 id="onboarding-review-title" ref={reviewHeading} data-screen-heading tabIndex={-1}>{text.reviewTitle}</h1>
        <p>{text.reviewIntro}</p>
      </div>

      <div className="review-layout">
        <section className={`transcript-review ${transcriptReviewed ? "reviewed" : ""}`} aria-labelledby="transcript-heading">
          <h2 id="transcript-heading">{text.transcriptSummary}</h2>
          <div className="transcript-body">
            <label htmlFor="review-transcript">{text.transcriptLabel}</label>
            <textarea
              id="review-transcript"
              value={transcript}
              onChange={(event) => {
                setTranscript(event.target.value);
                setTranscriptReviewed(false);
              }}
              rows={7}
            />
            <div className="transcript-actions">
              <button className="secondary-button" type="button" onClick={() => setTranscriptReviewed(true)}>
                <Check aria-hidden="true" />{text.transcriptRight}
              </button>
              <button className="text-button" type="button" onClick={updateDetails}>
                <RotateCcw aria-hidden="true" />{text.update}
              </button>
            </div>
          </div>
        </section>

        <div className="review-groups">
          {(Object.keys(fieldGroups) as GroupKey[]).map((group) => (
            <section key={group} className={`review-group ${activeGroup === group ? "active" : ""}`}>
              <button
                className="group-toggle"
                type="button"
                aria-expanded={activeGroup === group}
                onClick={() => setActiveGroup(group)}
              >
                <span>{text.groups[group]}</span><ChevronDown aria-hidden="true" />
              </button>
              <h2>{text.groups[group]}</h2>
              <div className="group-body">
                {fieldGroups[group].map((key) => {
                  const currentOptions = options[key]?.[locale] ?? [];
                  const selectOptions = wish[key] && !currentOptions.includes(wish[key])
                    ? [wish[key], ...currentOptions]
                    : currentOptions;
                  return (
                    <div className="field-row" key={key} data-changed={changedFields.has(key) || undefined}>
                      <div className="field-copy">
                        <span className="field-label">{text.labels[key]}{requiredFields.includes(key) && <span aria-hidden="true"> *</span>}</span>
                        {wish[key]
                          ? <strong>{wish[key]}</strong>
                          : <span className="missing-detail" role="status">{text.missing}</span>}
                        {changedFields.has(key) && <small>{text.changed}</small>}
                      </div>
                      {editing === key ? (
                        <div className="field-editor">
                          <label htmlFor={`edit-${key}`}>{text.labels[key]}</label>
                          {options[key] ? (
                            <select id={`edit-${key}`} value={pendingEdit} onChange={(event) => setPendingEdit(event.target.value)}>
                              <option value="">{text.missing}</option>
                              {selectOptions.map((value) => <option key={value} value={value}>{value}</option>)}
                            </select>
                          ) : (
                            <input id={`edit-${key}`} value={pendingEdit} onChange={(event) => setPendingEdit(event.target.value)} />
                          )}
                          <button className="secondary-button" type="button" onClick={() => saveEdit(key)}>{text.saveDetail}</button>
                        </div>
                      ) : (
                        <button className="edit-button" type="button" aria-label={`${text.edit}: ${text.labels[key]}`} onClick={() => beginEdit(key)}>
                          <Pencil aria-hidden="true" />{text.edit}
                        </button>
                      )}
                    </div>
                  );
                })}
                {group === "permission" && (
                  <div className="consent-fields">
                    <label className="consent-row">
                      <input
                        type="checkbox"
                        checked={wish.planConsent}
                        onChange={(event) => setWish((current) => ({ ...current, planConsent: event.target.checked }))}
                      />
                      <span>{text.planConsent} <strong aria-hidden="true">*</strong></span>
                    </label>
                    <label className="consent-row">
                      <input
                        type="checkbox"
                        checked={wish.matchingConsent}
                        onChange={(event) => setWish((current) => ({ ...current, matchingConsent: event.target.checked }))}
                      />
                      <span>{text.matchingConsent}<small>{text.matchingHelp}</small></span>
                    </label>
                  </div>
                )}
              </div>
            </section>
          ))}
        </div>
      </div>

      {saveError && <p className="save-error" role="alert">{text.saveError}</p>}
      <div className="review-actions">
        <button className="text-button" type="button" onClick={() => setStage("capture")}>{text.back}</button>
        {saveError ? (
          <button className="primary-button" type="button" onClick={saveProfile} disabled={saving}>{text.retry}</button>
        ) : (
          <button className="primary-button" type="button" onClick={saveProfile} disabled={!complete || saving}>
            {saving ? text.saving : text.confirm}
          </button>
        )}
      </div>
      <p className="storage-footnote">{text.storage}</p>
    </section>
  );
}
