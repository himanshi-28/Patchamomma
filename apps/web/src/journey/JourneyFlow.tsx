import { CalendarDays, Check, ChevronDown, ExternalLink, ListVideo, Pencil, PlayCircle, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "../onboarding/runtime";
import { RecommendationFlow } from "../recommendation/RecommendationFlow";
import type { RecommendationGateway } from "../recommendation/runtime";
import { cacheConfirmedJourney } from "./cache";
import {
  localized,
  nextJourneyStartDate,
  shiftJourneyStartDate,
  type JourneyActivity,
  type JourneyDraft,
  type JourneyGateway,
  type RecommendedPlaylist,
  type WeeklyVideoGuide,
} from "./runtime";

interface JourneyFlowProps {
  locale: Locale;
  gateway: JourneyGateway;
  planWeeks?: number;
  recommendationGateway?: RecommendationGateway;
  matchingConsent?: boolean;
  initialJourney?: JourneyDraft | null;
  onConfirmed?: (journey: JourneyDraft) => void;
}

const englishWeekWord = (weeks: number) => ({ 2: "two", 4: "four", 6: "six", 8: "eight" })[weeks] ?? String(weeks);
const hindiWeekWord = (weeks: number) => ({ 2: "दो", 4: "चार", 6: "छह", 8: "आठ" })[weeks] ?? String(weeks);

const copy = {
  en: {
    loading: (weeks: number) => `Creating your reviewed ${englishWeekWord(weeks)}-week plan and finding a suitable video course…`,
    readyTitle: "Your plan is ready",
    readyBody: (weeks: number) => `Your reviewed details were accepted and your ${englishWeekWord(weeks)}-week plan has been created.`,
    reviewPlan: (weeks: number) => `Review my ${englishWeekWord(weeks)}-week plan`,
    generationError: "We couldn't create your plan. Your confirmed learning details are safe; try again.",
    retry: "Try creating the plan again",
    notSaved: "Not saved yet",
    intro: (weeks: number) => `Review all ${englishWeekWord(weeks)} weeks. You can change the date, plan title, time, steps, accessible alternative, and reflection before saving.`,
    startDate: "Plan start date",
    editTitle: "Edit plan title",
    titleLabel: "Plan title",
    saveTitle: "Save plan title",
    week: "Week",
    required: "Required",
    optional: "Optional",
    minutes: "minutes",
    rest: "Rest day",
    editDay: "Edit day",
    duration: "duration in minutes",
    instruction: "instruction 1",
    activityTitle: "activity title",
    alternative: "accessible alternative",
    reflection: "reflection prompt",
    saveDay: "Save day",
    safety: "Safety note",
    fallback: (weeks: number) => `We couldn't create a personalised plan just now. Here is a reviewed ${englishWeekWord(weeks)}-week plan you can use or edit.`,
    retryPersonalised: "Try personalised plan again",
    reject: "Reject this draft",
    confirm: "Confirm and save my plan",
    confirming: "Saving your confirmed plan…",
    saveError: "Your plan was not saved. Your edited draft is still here; check the connection and retry.",
    savedTitle: (weeks: number) => `Your ${englishWeekWord(weeks)}-week plan is saved`,
    savedBody: "Your reviewed plan is ready. You can now begin with day 1.",
    offlineAvailable: "Available offline on this device",
    offlineUnavailable: "Your plan is saved, but this device could not make it available offline.",
    viewSavedPlan: "View saved plan",
    hideSavedPlan: "Hide saved plan",
    rejectedTitle: "This draft was discarded",
    rejectedBody: "Nothing from the draft was saved.",
    createAnother: "Create another plan",
  },
  hi: {
    loading: (weeks: number) => `आपकी जाँची हुई ${hindiWeekWord(weeks)}-सप्ताह की योजना बन रही है और उपयुक्त वीडियो पाठ्यक्रम खोजा जा रहा है…`,
    readyTitle: "आपकी योजना तैयार है",
    readyBody: (weeks: number) => `आपकी जाँची हुई जानकारी स्वीकार हो गई और आपकी ${hindiWeekWord(weeks)}-सप्ताह की योजना बन गई है।`,
    reviewPlan: (weeks: number) => `मेरी ${hindiWeekWord(weeks)}-सप्ताह की योजना देखें`,
    generationError: "आपकी योजना नहीं बन सकी। आपकी पुष्टि की हुई जानकारी सुरक्षित है; फिर कोशिश करें।",
    retry: "योजना फिर बनाएँ",
    notSaved: "अभी सेव नहीं हुई",
    intro: (weeks: number) => `${hindiWeekWord(weeks)} सप्ताह जाँचें। सेव करने से पहले तारीख, शीर्षक, समय, चरण, सुविधाजनक विकल्प और विचार बदल सकती हैं।`,
    startDate: "योजना शुरू होने की तारीख",
    editTitle: "योजना का शीर्षक बदलें",
    titleLabel: "योजना का शीर्षक",
    saveTitle: "योजना का शीर्षक सेव करें",
    week: "सप्ताह",
    required: "ज़रूरी",
    optional: "वैकल्पिक",
    minutes: "मिनट",
    rest: "आराम का दिन",
    editDay: "दिन बदलें",
    duration: "अवधि मिनटों में",
    instruction: "निर्देश 1",
    activityTitle: "गतिविधि का शीर्षक",
    alternative: "सुविधाजनक विकल्प",
    reflection: "विचार का सवाल",
    saveDay: "दिन सेव करें",
    safety: "सुरक्षा नोट",
    fallback: (weeks: number) => `अभी आपकी व्यक्तिगत योजना नहीं बन सकी। यहाँ ${hindiWeekWord(weeks)} सप्ताह की जाँची हुई योजना है, जिसे आप इस्तेमाल या संपादित कर सकती हैं।`,
    retryPersonalised: "व्यक्तिगत योजना फिर बनाएँ",
    reject: "यह ड्राफ़्ट अस्वीकार करें",
    confirm: "पुष्टि करके योजना सेव करें",
    confirming: "आपकी पुष्टि की हुई योजना सेव हो रही है…",
    saveError: "आपकी योजना सेव नहीं हुई। आपका बदला हुआ ड्राफ़्ट यहीं है; कनेक्शन जाँचकर फिर कोशिश करें।",
    savedTitle: (weeks: number) => `आपकी ${hindiWeekWord(weeks)}-सप्ताह की योजना सेव हो गई`,
    savedBody: "आपकी जाँची हुई योजना तैयार है। अब आप पहले दिन से शुरू कर सकती हैं।",
    offlineAvailable: "इस डिवाइस पर ऑफ़लाइन उपलब्ध है",
    offlineUnavailable: "आपकी योजना सेव है, लेकिन यह डिवाइस इसे ऑफ़लाइन उपलब्ध नहीं करा सका।",
    viewSavedPlan: "सेव की हुई योजना देखें",
    hideSavedPlan: "सेव की हुई योजना छिपाएँ",
    rejectedTitle: "यह ड्राफ़्ट हटा दिया गया",
    rejectedBody: "ड्राफ़्ट से कुछ भी सेव नहीं हुआ।",
    createAnother: "दूसरी योजना बनाएँ",
  },
} as const;

const videoCopy = {
  en: {
    playlistTitle: "Recommended YouTube playlist",
    openPlaylist: "Open complete playlist on YouTube",
    fetched: "YouTube details checked",
    preferred: "Preferred language confirmed",
    fallback: "Different language—labelled fallback",
    unknown: "Video language could not be confirmed",
    captions: "Captions confirmed",
    captionsUnknown: "Captions not confirmed",
    weekTitle: "Video lessons for this week",
    aboutMinutes: (minutes: number) => `About ${minutes} minutes`,
    opensYouTube: "opens YouTube in a new tab",
    prerequisites: "Before you watch",
    summary: "Learning overview—not a transcript summary",
    keyPoints: "Key points",
    whatToExpect: "What to expect",
    expectedResult: "Expected result",
    terms: "YouTube Terms",
    privacy: "Google Privacy Policy",
    refresh: "Find videos again",
    refreshing: "Looking for videos…",
    refreshError: "Videos could not be refreshed. Your written plan is still available.",
  },
  hi: {
    playlistTitle: "सुझाई गई YouTube प्लेलिस्ट",
    openPlaylist: "YouTube पर पूरी प्लेलिस्ट खोलें",
    fetched: "YouTube विवरण की जाँच",
    preferred: "पसंदीदा भाषा की पुष्टि हुई",
    fallback: "दूसरी भाषा—वैकल्पिक रूप में चिन्हित",
    unknown: "वीडियो की भाषा की पुष्टि नहीं हुई",
    captions: "कैप्शन की पुष्टि हुई",
    captionsUnknown: "कैप्शन की पुष्टि नहीं हुई",
    weekTitle: "इस सप्ताह के वीडियो पाठ",
    aboutMinutes: (minutes: number) => `लगभग ${minutes} मिनट`,
    opensYouTube: "नए टैब में YouTube खुलता है",
    prerequisites: "देखने से पहले",
    summary: "सीखने का अवलोकन—ट्रांसक्रिप्ट सारांश नहीं",
    keyPoints: "मुख्य बातें",
    whatToExpect: "क्या उम्मीद रखें",
    expectedResult: "अपेक्षित परिणाम",
    terms: "YouTube की शर्तें",
    privacy: "Google गोपनीयता नीति",
    refresh: "वीडियो फिर खोजें",
    refreshing: "वीडियो खोजे जा रहे हैं…",
    refreshError: "वीडियो फिर नहीं खोजे जा सके। आपकी लिखित योजना उपलब्ध है।",
  },
} as const;

interface VideoPlaylistOverviewProps {
  locale: Locale;
  playlist: RecommendedPlaylist;
}

function VideoPlaylistOverview({ locale, playlist }: VideoPlaylistOverviewProps) {
  const text = videoCopy[locale];
  const languageLabel = text[playlist.languageMatch];
  return (
    <section className="video-playlist-overview" aria-labelledby="recommended-playlist-title">
      <div className="video-playlist-heading">
        <ListVideo aria-hidden="true" />
        <div>
          <h2 id="recommended-playlist-title">{text.playlistTitle}</h2>
          <p><strong>{playlist.title}</strong><span>{playlist.channelTitle}</span></p>
        </div>
      </div>
      <p>{localized(playlist.selectionNote, locale)}</p>
      <p className="video-metadata-status">
        <span>{languageLabel}</span>
        <span>{playlist.captionsAvailable ? text.captions : text.captionsUnknown}</span>
      </p>
      <a className="video-playlist-link" href={playlist.url} target="_blank" rel="noreferrer">
        <ExternalLink aria-hidden="true" />
        {text.openPlaylist}
      </a>
      <p className="video-source-note">
        <ShieldCheck aria-hidden="true" />
        <span>
          {localized(playlist.sourceNote, locale)} {text.fetched}: {new Date(playlist.fetchedAt).toLocaleDateString(locale === "hi" ? "hi-IN" : "en-IN")}.
          {" "}<a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">{text.terms}</a>
          {" · "}<a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">{text.privacy}</a>
        </span>
      </p>
    </section>
  );
}

interface WeeklyVideoGuideViewProps {
  guide: WeeklyVideoGuide;
  locale: Locale;
  saved?: boolean;
  weekNumber: number;
}

function WeeklyVideoGuideView({ guide, locale, saved = false, weekNumber }: WeeklyVideoGuideViewProps) {
  const text = videoCopy[locale];
  const Heading = saved ? "h4" : "h3";
  return (
    <section className="video-week-guide" aria-labelledby={`week-${weekNumber}-video-title`}>
      <div className="video-week-heading">
        <PlayCircle aria-hidden="true" />
        <Heading id={`week-${weekNumber}-video-title`}>{text.weekTitle}</Heading>
      </div>
      <ul className="video-lesson-list">
        {guide.videos.map((video) => (
          <li key={video.videoId}>
            <a href={video.url} target="_blank" rel="noreferrer">
              <PlayCircle aria-hidden="true" />
              <span><strong>{video.title}</strong><small>{text.aboutMinutes(Math.ceil(video.durationSeconds / 60))} · YouTube</small></span>
              <span className="visually-hidden"> · {text.opensYouTube}</span>
              <ExternalLink aria-hidden="true" />
            </a>
          </li>
        ))}
      </ul>
      <div className="video-guide-details">
        <section>
          <h4>{text.prerequisites}</h4>
          <ul>{guide.prerequisites[locale].map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
        <section>
          <h4>{text.summary}</h4>
          <p>{localized(guide.summary, locale)}</p>
        </section>
        <section>
          <h4>{text.keyPoints}</h4>
          <ul>{guide.keyPoints[locale].map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
        <section>
          <h4>{text.whatToExpect}</h4>
          <p>{localized(guide.whatToExpect, locale)}</p>
        </section>
        <section className="video-expected-result">
          <h4>{text.expectedResult}</h4>
          <p>{localized(guide.expectedResult, locale)}</p>
        </section>
      </div>
    </section>
  );
}

type FlowState = "loading" | "ready" | "review" | "confirming" | "confirmed" | "rejected" | "error";

export function JourneyFlow({
  locale,
  gateway,
  planWeeks = 4,
  recommendationGateway,
  matchingConsent = false,
  initialJourney = null,
  onConfirmed,
}: JourneyFlowProps) {
  const restoredJourney = initialJourney?.status === "confirmed" ? initialJourney : null;
  const gatewayRef = useRef(gateway);
  const generationStarted = useRef(false);
  const [state, setState] = useState<FlowState>(restoredJourney ? "confirmed" : "loading");
  const [draft, setDraft] = useState<JourneyDraft | null>(restoredJourney);
  const [openWeek, setOpenWeek] = useState(1);
  const [editingTitle, setEditingTitle] = useState(false);
  const [pendingTitle, setPendingTitle] = useState("");
  const [editingDay, setEditingDay] = useState<number | null>(null);
  const [pendingActivity, setPendingActivity] = useState<JourneyActivity | null>(null);
  const [saveError, setSaveError] = useState(false);
  const [savedPlanOpen, setSavedPlanOpen] = useState(false);
  const [refreshingVideos, setRefreshingVideos] = useState(false);
  const [videoRefreshError, setVideoRefreshError] = useState(false);
  const [offlineCacheState, setOfflineCacheState] = useState<"available" | "unavailable" | null>(
    restoredJourney ? "available" : null,
  );
  const headingRef = useRef<HTMLHeadingElement>(null);
  const text = copy[locale];
  const displayedWeeks = draft?.weeks.length ?? planWeeks;

  const generate = async () => {
    setState("loading");
    setDraft(null);
    try {
      const created = await gatewayRef.current.create(nextJourneyStartDate());
      setDraft(created);
      setOpenWeek(1);
      setState("ready");
    } catch {
      setState("error");
    }
  };

  useEffect(() => {
    if (generationStarted.current || restoredJourney) return;
    generationStarted.current = true;
    void generate();
  }, [restoredJourney]);

  useEffect(() => {
    if (state === "ready" || state === "review" || state === "confirmed") headingRef.current?.focus();
  }, [state]);

  const beginTitleEdit = () => {
    if (!draft) return;
    setPendingTitle(draft.title[locale]);
    setEditingTitle(true);
  };

  const saveTitle = () => {
    if (!draft || !pendingTitle.trim()) return;
    setDraft({ ...draft, title: { ...draft.title, [locale]: pendingTitle.trim() } });
    setEditingTitle(false);
  };

  const beginDayEdit = (activity: JourneyActivity) => {
    setEditingDay(activity.dayNumber);
    setPendingActivity(structuredClone(activity));
  };

  const updatePendingText = (
    field: "title" | "accessibleAlternative" | "reflectionPrompt",
    value: string,
  ) => {
    setPendingActivity((current) => current ? {
      ...current,
      [field]: { ...current[field], [locale]: value },
    } : current);
  };

  const updatePendingInstruction = (value: string) => {
    setPendingActivity((current) => current ? {
      ...current,
      instructions: {
        ...current.instructions,
        [locale]: [value, ...current.instructions[locale].slice(1)],
      },
    } : current);
  };

  const saveDay = () => {
    if (!draft || !pendingActivity || !pendingActivity.title[locale].trim()
      || !pendingActivity.instructions[locale][0]?.trim()) return;
    setDraft({
      ...draft,
      weeks: draft.weeks.map((week) => ({
        ...week,
        activities: week.activities.map((activity) => (
          activity.dayNumber === pendingActivity.dayNumber ? pendingActivity : activity
        )),
      })),
    });
    setEditingDay(null);
    setPendingActivity(null);
  };

  const confirm = async () => {
    if (!draft) return;
    setState("confirming");
    setSaveError(false);
    try {
      const saved = await gatewayRef.current.confirm(draft);
      setDraft(saved);
      setOfflineCacheState(cacheConfirmedJourney(saved) ? "available" : "unavailable");
      setState("confirmed");
      onConfirmed?.(saved);
    } catch {
      setSaveError(true);
      setState("review");
    }
  };

  const refreshVideos = async () => {
    if (!draft || !gatewayRef.current.refreshVideos) return;
    setRefreshingVideos(true);
    setVideoRefreshError(false);
    try {
      const refreshed = await gatewayRef.current.refreshVideos(draft.journeyId);
      setDraft(refreshed);
      cacheConfirmedJourney(refreshed);
      onConfirmed?.(refreshed);
    } catch {
      setVideoRefreshError(true);
    } finally {
      setRefreshingVideos(false);
    }
  };

  const videoFallback = draft?.videoRecommendation
    && draft.videoRecommendation.status !== "recommended"
    ? (
      <section className="video-fallback" aria-label={locale === "en" ? "Video recommendation" : "वीडियो सुझाव"}>
        <p role="status">{localized(draft.videoRecommendation.message, locale)}</p>
        {draft.status === "confirmed"
          && ["no_match", "unavailable"].includes(draft.videoRecommendation.status)
          && gatewayRef.current.refreshVideos && (
          <button className="secondary-button" type="button" onClick={refreshVideos} disabled={refreshingVideos}>
            {refreshingVideos ? videoCopy[locale].refreshing : videoCopy[locale].refresh}
          </button>
        )}
        {videoRefreshError && <p className="save-error" role="alert">{videoCopy[locale].refreshError}</p>}
      </section>
    )
    : null;

  if (state === "loading") {
    return <section className="journey-state" aria-busy="true"><p role="status">{text.loading(displayedWeeks)}</p></section>;
  }

  if (state === "ready" && draft) {
    return (
      <section className="journey-state journey-ready" aria-labelledby="journey-ready-title">
        <span className="success-mark" aria-hidden="true"><Check /></span>
        <div>
          <h1 id="journey-ready-title" ref={headingRef} data-screen-heading tabIndex={-1}>{text.readyTitle}</h1>
          <p>{text.readyBody(displayedWeeks)}</p>
          <button className="primary-button onboarding-plan-action" type="button" onClick={() => setState("review")}>
            {text.reviewPlan(displayedWeeks)}
          </button>
        </div>
      </section>
    );
  }

  if (state === "error") {
    return (
      <section className="journey-state" aria-labelledby="journey-error-title">
        <h1 id="journey-error-title" data-screen-heading tabIndex={-1}>{text.generationError}</h1>
        <button className="primary-button" type="button" onClick={generate}>{text.retry}</button>
      </section>
    );
  }

  if (state === "rejected") {
    return (
      <section className="journey-state" aria-labelledby="journey-rejected-title">
        <h1 id="journey-rejected-title" data-screen-heading tabIndex={-1}>{text.rejectedTitle}</h1>
        <p>{text.rejectedBody}</p>
        <button className="primary-button" type="button" onClick={generate}>{text.createAnother}</button>
      </section>
    );
  }

  if (state === "confirmed" && draft) {
    return (
      <div className="journey-confirmed-stage">
        <section className="journey-state journey-confirmed" aria-labelledby="journey-confirmed-title">
          <span className="success-mark" aria-hidden="true"><Check /></span>
          <h1 id="journey-confirmed-title" ref={headingRef} data-screen-heading tabIndex={-1}>{text.savedTitle(displayedWeeks)}</h1>
          <p>{text.savedBody}</p>
          {offlineCacheState === "available" && <p className="offline-status"><ShieldCheck aria-hidden="true" />{text.offlineAvailable}</p>}
          {offlineCacheState === "unavailable" && <p className="offline-warning" role="status">{text.offlineUnavailable}</p>}
        </section>
        <section className="saved-journey" aria-labelledby="saved-journey-title">
          <div className="saved-journey-heading">
            <div>
              <h2 id="saved-journey-title">{localized(draft.title, locale)}</h2>
              <p>{localized(draft.summary, locale)}</p>
            </div>
            <button
              className="secondary-button"
              type="button"
              aria-expanded={savedPlanOpen}
              aria-controls="saved-journey-weeks"
              onClick={() => setSavedPlanOpen((open) => !open)}
            >
              {savedPlanOpen ? text.hideSavedPlan : text.viewSavedPlan}
            </button>
          </div>
          {draft.recommendedPlaylist && (
            <VideoPlaylistOverview locale={locale} playlist={draft.recommendedPlaylist} />
          )}
          {videoFallback}
          {savedPlanOpen && (
            <div id="saved-journey-weeks" className="saved-journey-weeks">
              {draft.weeks.map((week) => (
                <section className="saved-journey-week" key={week.weekNumber}>
                  <h3>{text.week} {week.weekNumber}: {localized(week.theme, locale)}</h3>
                  <p>{localized(week.outcome, locale)}</p>
                  {week.videoGuide && (
                    <WeeklyVideoGuideView guide={week.videoGuide} locale={locale} saved weekNumber={week.weekNumber} />
                  )}
                  <div className="journey-days">
                    {week.activities.map((activity) => (
                      <article className="journey-day" key={activity.activityId}>
                        <div className="journey-day-heading">
                          <div>
                            <span>{activity.date} · {activity.required ? text.required : text.optional}</span>
                            <h4>{localized(activity.title, locale)}</h4>
                          </div>
                        </div>
                        <p className="journey-duration">{activity.kind === "rest" ? text.rest : `${activity.durationMinutes} ${text.minutes}`}</p>
                        <ol>{activity.instructions[locale].map((step, index) => <li key={`${activity.activityId}-saved-${index}`}>{step}</li>)}</ol>
                        <p><strong>{locale === "en" ? "Comfort option:" : "सुविधाजनक विकल्प:"}</strong> {localized(activity.accessibleAlternative, locale)}</p>
                        <p><strong>{locale === "en" ? "Reflect:" : "विचार:"}</strong> {localized(activity.reflectionPrompt, locale)}</p>
                        <p className="journey-safety"><ShieldCheck aria-hidden="true" /><span><strong>{text.safety}:</strong> {localized(activity.safetyNote, locale)}</span></p>
                      </article>
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </section>
        {recommendationGateway && (
          <RecommendationFlow
            locale={locale}
            matchingConsent={matchingConsent}
            gateway={recommendationGateway}
          />
        )}
      </div>
    );
  }

  if (!draft) return null;

  return (
    <section className="journey-flow" aria-labelledby="journey-title">
      <header className="journey-heading">
        <p className="not-saved"><Check aria-hidden="true" />{text.notSaved}</p>
        {draft.provenance.fallbackUsed && (
          <div className="fallback-panel">
            <p className="fallback-notice" role="status">{text.fallback(displayedWeeks)}</p>
            <button className="secondary-button" type="button" onClick={generate}>
              {text.retryPersonalised}
            </button>
          </div>
        )}
        <div className="journey-title-row">
          {editingTitle ? (
            <div className="journey-title-editor">
              <label htmlFor="journey-plan-title">{text.titleLabel}</label>
              <input id="journey-plan-title" value={pendingTitle} maxLength={120} onChange={(event) => setPendingTitle(event.target.value)} />
              <button className="secondary-button" type="button" onClick={saveTitle}>{text.saveTitle}</button>
            </div>
          ) : (
            <>
              <div>
                <h1 id="journey-title" ref={headingRef} data-screen-heading tabIndex={-1}>{localized(draft.title, locale)}</h1>
                <p>{localized(draft.summary, locale)}</p>
              </div>
              <button className="edit-button" type="button" onClick={beginTitleEdit} aria-label={text.editTitle}>
                <Pencil aria-hidden="true" />{locale === "en" ? "Edit" : "बदलें"}
              </button>
            </>
          )}
        </div>
        <p>{text.intro(displayedWeeks)}</p>
        <label className="journey-date" htmlFor="journey-start-date">
          <CalendarDays aria-hidden="true" />
          <span>{text.startDate}</span>
          <input
            id="journey-start-date"
            type="date"
            value={draft.startsOn}
            onChange={(event) => setDraft(shiftJourneyStartDate(draft, event.target.value))}
          />
        </label>
        {draft.recommendedPlaylist && (
          <VideoPlaylistOverview locale={locale} playlist={draft.recommendedPlaylist} />
        )}
        {videoFallback}
      </header>

      <div className="journey-weeks">
        {draft.weeks.map((week) => {
          const expanded = openWeek === week.weekNumber;
          return (
            <section className="journey-week" key={week.weekNumber}>
              <button
                className="journey-week-toggle"
                type="button"
                aria-expanded={expanded}
                aria-controls={`journey-week-${week.weekNumber}`}
                onClick={() => setOpenWeek(expanded ? 0 : week.weekNumber)}
              >
                <span><strong>{text.week} {week.weekNumber}</strong>{localized(week.theme, locale)}</span>
                <ChevronDown aria-hidden="true" />
              </button>
              {expanded && (
                <div id={`journey-week-${week.weekNumber}`} className="journey-week-body">
                  <p>{localized(week.outcome, locale)}</p>
                  {week.videoGuide && (
                    <WeeklyVideoGuideView guide={week.videoGuide} locale={locale} weekNumber={week.weekNumber} />
                  )}
                  <div className="journey-days">
                    {week.activities.map((activity) => (
                      <article className="journey-day" key={activity.activityId}>
                        {editingDay === activity.dayNumber && pendingActivity ? (
                          <div className="journey-day-editor">
                            <label htmlFor={`day-${activity.dayNumber}-title`}>Day {activity.dayNumber} {text.activityTitle}</label>
                            <input
                              id={`day-${activity.dayNumber}-title`}
                              value={pendingActivity.title[locale]}
                              maxLength={120}
                              onChange={(event) => updatePendingText("title", event.target.value)}
                            />
                            <label htmlFor={`day-${activity.dayNumber}-duration`}>Day {activity.dayNumber} {text.duration}</label>
                            <input
                              id={`day-${activity.dayNumber}-duration`}
                              type="number"
                              min={activity.kind === "rest" ? 0 : 5}
                              max={45}
                              value={pendingActivity.durationMinutes}
                              disabled={activity.kind === "rest"}
                              onChange={(event) => setPendingActivity({ ...pendingActivity, durationMinutes: Number(event.target.value) })}
                            />
                            <label htmlFor={`day-${activity.dayNumber}-instruction`}>Day {activity.dayNumber} {text.instruction}</label>
                            <textarea
                              id={`day-${activity.dayNumber}-instruction`}
                              rows={3}
                              value={pendingActivity.instructions[locale][0]}
                              maxLength={280}
                              onChange={(event) => updatePendingInstruction(event.target.value)}
                            />
                            <label htmlFor={`day-${activity.dayNumber}-alternative`}>Day {activity.dayNumber} {text.alternative}</label>
                            <textarea id={`day-${activity.dayNumber}-alternative`} rows={3} value={pendingActivity.accessibleAlternative[locale]} maxLength={500} onChange={(event) => updatePendingText("accessibleAlternative", event.target.value)} />
                            <label htmlFor={`day-${activity.dayNumber}-reflection`}>Day {activity.dayNumber} {text.reflection}</label>
                            <textarea id={`day-${activity.dayNumber}-reflection`} rows={3} value={pendingActivity.reflectionPrompt[locale]} maxLength={500} onChange={(event) => updatePendingText("reflectionPrompt", event.target.value)} />
                            <button className="secondary-button" type="button" onClick={saveDay} aria-label={`${text.saveDay} ${activity.dayNumber}`}>{text.saveDay} {activity.dayNumber}</button>
                          </div>
                        ) : (
                          <>
                            <div className="journey-day-heading">
                              <div>
                                <span>{activity.date} · {activity.required ? text.required : text.optional}</span>
                                <h3>{localized(activity.title, locale)}</h3>
                              </div>
                              <button className="edit-button" type="button" onClick={() => beginDayEdit(activity)} aria-label={`${text.editDay} ${activity.dayNumber}`}>
                                <Pencil aria-hidden="true" />{locale === "en" ? "Edit" : "बदलें"}
                              </button>
                            </div>
                            <p className="journey-duration">{activity.kind === "rest" ? text.rest : `${activity.durationMinutes} ${text.minutes}`}</p>
                            <ol>{activity.instructions[locale].map((step, index) => <li key={`${activity.activityId}-${index}`}>{step}</li>)}</ol>
                            <p><strong>{locale === "en" ? "Comfort option:" : "सुविधाजनक विकल्प:"}</strong> {localized(activity.accessibleAlternative, locale)}</p>
                            <p><strong>{locale === "en" ? "Reflect:" : "विचार:"}</strong> {localized(activity.reflectionPrompt, locale)}</p>
                            <p className="journey-safety"><ShieldCheck aria-hidden="true" /><span><strong>{text.safety}:</strong> {localized(activity.safetyNote, locale)}</span></p>
                          </>
                        )}
                      </article>
                    ))}
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </div>

      {saveError && <p className="save-error" role="alert">{text.saveError}</p>}
      <div className="journey-actions">
        <button className="secondary-button" type="button" onClick={() => { setDraft(null); setState("rejected"); }}>{text.reject}</button>
        <button className="primary-button" type="button" onClick={confirm} disabled={state === "confirming"}>
          {state === "confirming" ? text.confirming : text.confirm}
        </button>
      </div>
    </section>
  );
}
