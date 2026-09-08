import {
  BookOpenText,
  ChevronDown,
  CircleHelp,
  GraduationCap,
  Languages,
  LogOut,
  Mail,
  MessageCircle,
  Sparkles,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import {
  createDeterministicAuthGateway,
  SessionCleanupError,
  type AuthGateway,
  type AuthSession,
} from "./auth/runtime";
import sakhiGuide from "./assets/sakhi-guide-maroon.webp";
import { JourneyFlow } from "./journey/JourneyFlow";
import { readConfirmedJourneyCache } from "./journey/cache";
import type { JourneyDraft, JourneyGateway } from "./journey/runtime";
import { OnboardingFlow } from "./onboarding/OnboardingFlow";
import {
  createDeterministicTranscriptAdapter,
  type ProfileGateway,
  type ProfileExtractionGateway,
  type TranscriptAdapter,
} from "./onboarding/runtime";
import type { RecommendationGateway } from "./recommendation/runtime";
import { DemoActivityCenter } from "./activities/DemoActivityCenter";

type Locale = "en" | "hi";
type Destination = "today" | "circle" | "mentors";
type TodayView = "today" | "plan";

interface AppProps {
  demoMode?: boolean;
  authGateway?: AuthGateway;
  transcriptAdapter?: TranscriptAdapter;
  profileGateway?: ProfileGateway;
  profileExtractionGateway?: ProfileExtractionGateway;
  journeyGateway?: JourneyGateway;
  recommendationGateway?: RecommendationGateway;
}

interface Copy {
  skipLink: string;
  brandLabel: string;
  navigationLabel: string;
  today: string;
  circle: string;
  mentors: string;
  todayViewsLabel: string;
  myPlan: string;
  savedPlanTodayHeading: string;
  savedPlanTodayBody: string;
  openMyPlan: string;
  emptyPlanHeading: string;
  emptyPlanBody: string;
  createMyPlan: string;
  help: string;
  languageAction: string;
  languageChanged: string;
  greeting: string;
  profileLabel: string;
  signOut: string;
  startHeading: string;
  startBody: string;
  startAction: string;
  circleHeading: string;
  circleBody: string;
  mentorsHeading: string;
  mentorsBody: string;
  login: {
    meetGuide: string;
    guideTrigger: string;
    guideImageAlt: string;
    guideRegion: string;
    guideClose: string;
    guidePrompt: string;
    guideTopics: Record<GuideTopic, string>;
    guideReplies: Record<GuideTopic, string>;
    title: string;
    tagline: string;
    security: string;
    emailLabel: string;
    sendLink: string;
    sending: string;
    divider: string;
    googleAction: string;
    googleHelp: string;
    demoTitle: string;
    demoDescription: string;
    demoAction: string;
    statuses: Record<AuthStatus, string>;
  };
}

type GuideTopic = "signIn" | "hobby" | "review";
type AuthStatus =
  | "emailSent"
  | "emailUnavailable"
  | "googleUnavailable"
  | "configurationUnavailable"
  | "cleanupFailed";

const copy: Record<Locale, Copy> = {
  en: {
    skipLink: "Skip to main content",
    brandLabel: "SakhiCircle home",
    navigationLabel: "Primary navigation",
    today: "Today",
    circle: "My Circle",
    mentors: "Mentors",
    todayViewsLabel: "Today views",
    myPlan: "My Plan",
    savedPlanTodayHeading: "Your plan is ready for today",
    savedPlanTodayBody: "Your confirmed learning plan is saved and ready whenever you want to continue.",
    openMyPlan: "Open My Plan",
    emptyPlanHeading: "Your plan will live here",
    emptyPlanBody: "Create and confirm a learning plan first. Only a plan you explicitly save will appear here.",
    createMyPlan: "Create my plan",
    help: "Need help?",
    languageAction: "हिंदी में देखें",
    languageChanged: "Language changed to English. Your draft is unchanged.",
    greeting: "Hi",
    profileLabel: "profile",
    signOut: "Sign out",
    startHeading: "Your next chapter starts here",
    startBody: "Tell us what you have always wanted to learn. We will shape it around your time, pace, and comfort.",
    startAction: "Choose my first hobby",
    circleHeading: "Your circle is ready when you are",
    circleBody: "After onboarding, we will introduce a small group learning the same skill at a compatible pace.",
    mentorsHeading: "Learn from lived experience",
    mentorsBody: "Verified mentors and their available sessions will appear here after we understand your goal.",
    login: {
      meetGuide: "Meet Sakhi, your guide",
      guideTrigger: "Hi, how may I help you?",
      guideImageAlt: "Sakhi, your SakhiCircle guide",
      guideRegion: "Sakhi help",
      guideClose: "Close Sakhi help",
      guidePrompt: "What would you like help with?",
      guideTopics: {
        signIn: "Signing in",
        hobby: "Finding a hobby",
        review: "Reviewing my details",
      },
      guideReplies: {
        signIn: "Use your email or Google. You will not need to create a password.",
        hobby: "After sign-in, tell me what interests you. I can help you choose a comfortable first step.",
        review: "You can edit every suggested detail. Nothing is saved until you confirm it.",
      },
      title: "Welcome to SakhiCircle",
      tagline: "A friendly place to learn, teach, and belong.",
      security: "Sign in securely. No password needed.",
      emailLabel: "Email address",
      sendLink: "Send sign-in link",
      sending: "Please wait…",
      divider: "or",
      googleAction: "Continue with Google",
      googleHelp: "Google sign-in continues on a full Google page in this tab. No popup permission is required.",
      demoTitle: "Try the demo",
      demoDescription: "Synthetic data · no cloud account",
      demoAction: "Continue as Meera",
      statuses: {
        emailSent: "Firebase accepted the request for {email}. Check Spam or Promotions and allow up to 5 minutes. If it still does not arrive, verify the address or use Google sign-in.",
        emailUnavailable: "Email sign-in needs Firebase project settings. Demo access still works locally.",
        googleUnavailable: "Google sign-in needs Firebase project settings. Demo access still works locally.",
        configurationUnavailable: "Firebase sign-in is unavailable because required project settings are missing.",
        cleanupFailed: "You are signed out. Some local data could not be cleared; please retry before using this device again.",
      },
    },
  },
  hi: {
    skipLink: "मुख्य सामग्री पर जाएँ",
    brandLabel: "SakhiCircle होम",
    navigationLabel: "मुख्य नेविगेशन",
    today: "आज",
    circle: "मेरा सर्कल",
    mentors: "मेंटर्स",
    todayViewsLabel: "आज के दृश्य",
    myPlan: "मेरी योजना",
    savedPlanTodayHeading: "आज के लिए आपकी योजना तैयार है",
    savedPlanTodayBody: "आपकी पुष्टि की हुई सीखने की योजना सेव है और जब चाहें आगे बढ़ने के लिए तैयार है।",
    openMyPlan: "मेरी योजना खोलें",
    emptyPlanHeading: "आपकी योजना यहाँ दिखाई देगी",
    emptyPlanBody: "पहले सीखने की योजना बनाएँ और पुष्टि करें। केवल आपकी स्पष्ट अनुमति से सेव की हुई योजना यहाँ दिखाई देगी।",
    createMyPlan: "मेरी योजना बनाएँ",
    help: "मदद चाहिए?",
    languageAction: "View in English",
    languageChanged: "भाषा हिंदी हुई। आपका ड्राफ़्ट नहीं बदला।",
    greeting: "नमस्ते",
    profileLabel: "प्रोफ़ाइल",
    signOut: "साइन आउट करें",
    startHeading: "आपकी नई शुरुआत यहीं से है",
    startBody: "हमें बताइए कि आप हमेशा से क्या सीखना चाहती थीं। हम आपकी सुविधा, समय और गति के अनुसार योजना बनाएँगे।",
    startAction: "अपना पहला शौक चुनें",
    circleHeading: "आपका सर्कल आपका इंतज़ार कर रहा है",
    circleBody: "ऑनबोर्डिंग के बाद हम आपको समान रुचि और गति वाली महिलाओं के छोटे समूह से मिलाएँगे।",
    mentorsHeading: "अनुभव से सीखें",
    mentorsBody: "आपका लक्ष्य समझने के बाद सत्यापित मेंटर्स और उपलब्ध सत्र यहाँ दिखाई देंगे।",
    login: {
      meetGuide: "सखी से मिलें, आपकी मार्गदर्शक",
      guideTrigger: "नमस्ते, मैं आपकी मदद करूँगी",
      guideImageAlt: "सखी, आपकी SakhiCircle मार्गदर्शक",
      guideRegion: "सखी सहायता",
      guideClose: "सखी सहायता बंद करें",
      guidePrompt: "आप किस चीज़ में मदद चाहती हैं?",
      guideTopics: {
        signIn: "साइन इन करना",
        hobby: "शौक चुनना",
        review: "अपने विवरण जाँचना",
      },
      guideReplies: {
        signIn: "अपने ईमेल या Google का उपयोग करें। आपको पासवर्ड बनाने की ज़रूरत नहीं है।",
        hobby: "साइन इन करने के बाद, हमें अपनी रुचि बताएँ। हम पहला सहज कदम चुनने में आपकी मदद करेंगे।",
        review: "आप हर सुझाए गए विवरण को बदल सकती हैं। आपकी पुष्टि से पहले कुछ सेव नहीं होता।",
      },
      title: "SakhiCircle में आपका स्वागत है",
      tagline: "सीखने, सिखाने और अपनापन पाने की एक दोस्ताना जगह।",
      security: "सुरक्षित रूप से साइन इन करें। पासवर्ड की ज़रूरत नहीं।",
      emailLabel: "ईमेल पता",
      sendLink: "साइन-इन लिंक भेजें",
      sending: "कृपया प्रतीक्षा करें…",
      divider: "या",
      googleAction: "Google से जारी रखें",
      googleHelp: "Google साइन-इन इसी टैब में पूरे पेज पर जारी रहेगा। पॉप-अप की अनुमति देने की ज़रूरत नहीं है।",
      demoTitle: "डेमो आज़माएँ",
      demoDescription: "काल्पनिक डेटा · क्लाउड खाते की ज़रूरत नहीं",
      demoAction: "मीरा के रूप में जारी रखें",
      statuses: {
        emailSent: "Firebase ने {email} के लिए अनुरोध स्वीकार किया। Spam या Promotions देखें और 5 मिनट तक प्रतीक्षा करें। फिर भी न आए तो पता जाँचें या Google साइन-इन इस्तेमाल करें।",
        emailUnavailable: "ईमेल साइन-इन के लिए Firebase प्रोजेक्ट सेटिंग्स चाहिए। स्थानीय डेमो अभी भी काम करता है।",
        googleUnavailable: "Google साइन-इन के लिए Firebase प्रोजेक्ट सेटिंग्स चाहिए। स्थानीय डेमो अभी भी काम करता है।",
        configurationUnavailable: "ज़रूरी प्रोजेक्ट सेटिंग्स न होने के कारण Firebase साइन-इन उपलब्ध नहीं है।",
        cleanupFailed: "आप साइन आउट हो चुकी हैं। कुछ स्थानीय डेटा साफ़ नहीं हुआ; इस डिवाइस को फिर उपयोग करने से पहले दोबारा कोशिश करें।",
      },
    },
  },
};

const navItems = [
  { id: "today" as const, icon: BookOpenText },
  { id: "circle" as const, icon: UsersRound },
  { id: "mentors" as const, icon: GraduationCap },
];

export function App({
  demoMode = false,
  authGateway,
  transcriptAdapter,
  profileGateway,
  profileExtractionGateway,
  journeyGateway,
  recommendationGateway,
}: AppProps) {
  const [gateway] = useState<AuthGateway>(() => (
    authGateway ?? createDeterministicAuthGateway({ demoMode })
  ));
  const [session, setSession] = useState<AuthSession | null>(null);
  const [locale, setLocale] = useState<Locale>("en");
  const [languageAnnouncement, setLanguageAnnouncement] = useState("");
  const [destination, setDestination] = useState<Destination>("today");
  const [todayView, setTodayView] = useState<TodayView>("today");
  const [helpOpen, setHelpOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [guideReply, setGuideReply] = useState<GuideTopic | null>(null);
  const [stepsOpen, setStepsOpen] = useState(false);
  const [isNarrowViewport, setIsNarrowViewport] = useState(false);
  const [onboardingStarted, setOnboardingStarted] = useState(false);
  const [journeyStarted, setJourneyStarted] = useState(false);
  const [restoredJourney, setRestoredJourney] = useState<JourneyDraft | null>(null);
  const [matchingConsent, setMatchingConsent] = useState(false);
  const [planWeeks, setPlanWeeks] = useState(4);
  const [voiceAdapter] = useState(() => transcriptAdapter ?? createDeterministicTranscriptAdapter());
  const [profileBoundary] = useState<ProfileGateway>(() => profileGateway ?? ({
    save: async () => { throw new Error("Profile saving is not configured."); },
  }));
  const helpId = useId();
  const guideId = useId();
  const stepsId = useId();
  const localeFocusPending = useRef(false);
  const text = copy[locale];
  const authenticated = session !== null;
  const displayName = session?.displayName.trim() || (locale === "hi" ? "सखी" : "SakhiCircle member");
  const firstName = displayName.split(/\s+/)[0];
  const statusMessage = status === "emailSent"
    ? text.login.statuses.emailSent.replace("{email}", email)
    : status ? text.login.statuses[status] : "";

  useEffect(() => gateway.observeSession(
    setSession,
    () => setStatus("configurationUnavailable"),
  ), [gateway]);

  useEffect(() => {
    if (!authenticated) {
      setOnboardingStarted(false);
      setJourneyStarted(false);
      setMatchingConsent(false);
      setPlanWeeks(4);
      setRestoredJourney(null);
      setTodayView("today");
      return;
    }
    const cachedJourney = readConfirmedJourneyCache();
    if (!cachedJourney) return;
    setRestoredJourney(cachedJourney);
    setPlanWeeks(cachedJourney.weeks.length);
    setOnboardingStarted(true);
    setJourneyStarted(true);
  }, [authenticated]);

  useLayoutEffect(() => {
    if (!authenticated) return;

    const root = document.documentElement;
    const previousScrollBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    const resetScroll = () => {
      root.scrollTop = 0;
      document.body.scrollTop = 0;
      window.scrollTo(0, 0);
    };

    document.getElementById("main-content")?.focus({ preventScroll: true });
    resetScroll();
    const frame = window.requestAnimationFrame(() => {
      resetScroll();
      root.style.scrollBehavior = previousScrollBehavior;
    });

    return () => {
      window.cancelAnimationFrame(frame);
      root.style.scrollBehavior = previousScrollBehavior;
    };
  }, [authenticated]);

  useLayoutEffect(() => {
    if (typeof window.matchMedia !== "function") return;

    const narrowViewport = window.matchMedia("(max-width: 780px)");
    const syncViewport = (event: MediaQueryList | MediaQueryListEvent) => {
      setIsNarrowViewport(event.matches);
      if (event.matches) setStepsOpen(false);
    };

    syncViewport(narrowViewport);
    narrowViewport.addEventListener("change", syncViewport);

    return () => narrowViewport.removeEventListener("change", syncViewport);
  }, []);

  useLayoutEffect(() => {
    if (!localeFocusPending.current) return;
    localeFocusPending.current = false;
    const activeHeading = destination === "today"
      ? document.querySelector<HTMLElement>(`#today-panel-${todayView} [data-screen-heading]`)
      : document.querySelector<HTMLElement>("#main-content [data-screen-heading]");
    activeHeading?.focus();
  }, [destination, locale, todayView]);

  const toggleLocale = () => {
    const nextLocale = locale === "en" ? "hi" : "en";
    localeFocusPending.current = true;
    setLanguageAnnouncement(copy[nextLocale].languageChanged);
    setLocale(nextLocale);
  };

  const sendEmailLink = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      await gateway.sendEmailLink(email);
      setStatus("emailSent");
    } catch {
      setStatus("emailUnavailable");
    } finally {
      setBusy(false);
    }
  };

  const signInWithGoogle = async () => {
    setBusy(true);
    setStatus(null);
    try {
      await gateway.signInWithGoogle();
    } catch {
      setStatus("googleUnavailable");
    } finally {
      setBusy(false);
    }
  };

  const signInDemo = async () => {
    setBusy(true);
    setStatus(null);
    try {
      await gateway.signInDemo();
    } catch {
      setStatus("configurationUnavailable");
    } finally {
      setBusy(false);
    }
  };

  const signOut = async () => {
    setBusy(true);
    setProfileOpen(false);
    try {
      await gateway.signOut();
    } catch (error) {
      if (error instanceof SessionCleanupError) {
        setSession(null);
        setStatus("cleanupFailed");
      }
    } finally {
      setBusy(false);
    }
  };

  if (!authenticated) {
    return (
      <div className="login-page" lang={locale === "hi" ? "hi" : "en-IN"}>
        <a className="skip-link" href="#main-content">{text.skipLink}</a>
        <p className="visually-hidden" aria-live="polite" aria-atomic="true">{languageAnnouncement}</p>
        <header className="public-header">
          <Brand ariaLabel={text.brandLabel} />
          <button className="language-button" type="button" onClick={toggleLocale}>
            <Languages aria-hidden="true" />
            {text.languageAction}
          </button>
        </header>

        <main id="main-content" className="login-layout">
          <section className="welcome-guide" aria-label={text.login.meetGuide}>
            <button
              className="guide-trigger"
              type="button"
              aria-label={text.login.guideTrigger}
              aria-expanded={guideOpen}
              aria-controls={guideId}
              onClick={() => setGuideOpen((open) => !open)}
            >
              <span className="guide-portrait">
                <img
                  src={sakhiGuide}
                  alt={text.login.guideImageAlt}
                  width={1033}
                  height={1522}
                />
                <span className="guide-bubble">
                  <MessageCircle aria-hidden="true" />
                  {text.login.guideTrigger}
                </span>
              </span>
            </button>

            {guideOpen && (
              <div id={guideId} className="guide-conversation" role="region" aria-label={text.login.guideRegion}>
                <button className="guide-close" type="button" aria-label={text.login.guideClose} onClick={() => setGuideOpen(false)}>
                  <X aria-hidden="true" />
                </button>
                <strong>{text.login.guidePrompt}</strong>
                <div className="guide-topics">
                  <button type="button" onClick={() => setGuideReply("signIn")}>{text.login.guideTopics.signIn}</button>
                  <button type="button" onClick={() => setGuideReply("hobby")}>{text.login.guideTopics.hobby}</button>
                  <button type="button" onClick={() => setGuideReply("review")}>{text.login.guideTopics.review}</button>
                </div>
                {guideReply && <p className="guide-reply" role="status">{text.login.guideReplies[guideReply]}</p>}
              </div>
            )}
          </section>

          <section className="sign-in-panel" aria-labelledby="sign-in-title">
            <div className="sign-in-heading">
              <h1 id="sign-in-title" data-screen-heading tabIndex={-1}>{text.login.title}</h1>
              <p>{text.login.tagline}</p>
              <span>{text.login.security}</span>
            </div>

            <form className="email-form" onSubmit={sendEmailLink} aria-busy={busy}>
              <label htmlFor="email">{text.login.emailLabel}</label>
              <div className="input-with-icon">
                <Mail aria-hidden="true" />
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
              <button className="primary-button" type="submit" disabled={busy}>
                {busy ? text.login.sending : text.login.sendLink}
              </button>
            </form>

            <div className="choice-divider"><span>{text.login.divider}</span></div>

            <button className="secondary-button" type="button" onClick={signInWithGoogle} disabled={busy}>
              <span className="google-mark" aria-hidden="true">G</span>
              {text.login.googleAction}
            </button>
            <p className="sign-in-help">{text.login.googleHelp}</p>

            {demoMode && (
              <div className="demo-access">
                <p><strong>{text.login.demoTitle}</strong><span>{text.login.demoDescription}</span></p>
                <button className="demo-button" type="button" onClick={signInDemo} disabled={busy}>
                  <UserRound aria-hidden="true" />
                  {text.login.demoAction}
                </button>
              </div>
            )}

            {status && <p className="status-message" role="status">{statusMessage}</p>}
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="app-page" lang={locale === "hi" ? "hi" : "en-IN"}>
      <a className="skip-link" href="#main-content">{text.skipLink}</a>
      <p className="visually-hidden" aria-live="polite" aria-atomic="true">{languageAnnouncement}</p>
      <header className="app-header">
        <Brand ariaLabel={text.brandLabel} />
        <div className="header-actions">
          <button className="language-button" type="button" onClick={toggleLocale}>
            <Languages aria-hidden="true" />
            {text.languageAction}
          </button>
          <div className="profile-control">
            <button
              className="profile-button"
              type="button"
              aria-label={`${displayName} ${text.profileLabel}`}
              aria-expanded={profileOpen}
              aria-controls="profile-menu"
              onClick={() => setProfileOpen((open) => !open)}
            >
              <span className="avatar" aria-hidden="true">{firstName.charAt(0).toLocaleUpperCase(locale === "hi" ? "hi-IN" : "en-IN")}</span>
              <span className="profile-name">{firstName}</span>
            </button>
            {profileOpen && (
              <div id="profile-menu" className="profile-menu">
                <button type="button" onClick={signOut} disabled={busy}>
                  <LogOut aria-hidden="true" />
                  {text.signOut}
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="app-frame">
        <nav className="primary-navigation" aria-label={text.navigationLabel}>
          {navItems.map(({ id, icon: Icon }) => {
            const label = id === "today" ? text.today : id === "circle" ? text.circle : text.mentors;
            return (
              <a
                key={id}
                href={`#${id}`}
                className={destination === id ? "active" : undefined}
                aria-current={destination === id ? "page" : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  setDestination(id);
                }}
              >
                <Icon aria-hidden="true" />
                <span>{label}</span>
              </a>
            );
          })}
        </nav>

        <main id="main-content" className="app-main" tabIndex={-1}>
          <div className="main-toolbar">
            <p>{text.greeting}, {firstName}</p>
            <button className="help-button" type="button" onClick={() => setHelpOpen((open) => !open)} aria-expanded={helpOpen} aria-controls={helpId}>
              <CircleHelp aria-hidden="true" />
              {text.help}
            </button>
          </div>
          {helpOpen && (
            <aside id={helpId} className="help-panel" aria-label={text.help}>
              <strong>{locale === "en" ? "You are never stuck here." : "यहाँ आपको कभी अकेले समझने की ज़रूरत नहीं है।"}</strong>
              <span>{locale === "en" ? "Type your learning wish, then review every suggested detail before saving. Helpful explanations appear beneath unfamiliar sections." : "अपनी सीखने की इच्छा लिखें, फिर सेव करने से पहले हर सुझाया गया विवरण जाँचें। नए भागों के नीचे सरल समझाइश दिखाई देती है।"}</span>
            </aside>
          )}

          {destination === "today" && (
            <>
              <div className="today-tabs" role="tablist" aria-label={text.todayViewsLabel}>
                {(["today", "plan"] as const).map((view) => {
                  const selected = todayView === view;
                  const label = view === "today" ? text.today : text.myPlan;
                  return (
                    <button
                      id={`today-tab-${view}`}
                      key={view}
                      type="button"
                      role="tab"
                      aria-selected={selected}
                      aria-controls={`today-panel-${view}`}
                      tabIndex={selected ? 0 : -1}
                      onClick={() => setTodayView(view)}
                      onKeyDown={(event) => {
                        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                        event.preventDefault();
                        const nextView: TodayView = event.key === "ArrowRight" || event.key === "End" ? "plan" : "today";
                        setTodayView(nextView);
                        window.requestAnimationFrame(() => document.getElementById(`today-tab-${nextView}`)?.focus());
                      }}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>

              <div
                id="today-panel-today"
                role="tabpanel"
                aria-labelledby="today-tab-today"
                hidden={todayView !== "today"}
              >
                {restoredJourney ? (
                  <section className="plan-today-summary" aria-labelledby="today-heading">
                    <BookOpenText aria-hidden="true" />
                    <div>
                      <p className="section-label">{locale === "en" ? "Saved learning plan" : "सेव की हुई सीखने की योजना"}</p>
                      <h1 id="today-heading" data-screen-heading tabIndex={-1}>{text.savedPlanTodayHeading}</h1>
                      <p>{text.savedPlanTodayBody}</p>
                      <strong>{restoredJourney.title[locale]}</strong>
                    </div>
                    <button className="primary-button" type="button" onClick={() => setTodayView("plan")}>
                      {text.openMyPlan}
                    </button>
                  </section>
                ) : (
                  <>
                    {onboardingStarted && journeyStarted && journeyGateway && (
                      <JourneyFlow
                        locale={locale}
                        gateway={journeyGateway}
                        planWeeks={planWeeks}
                        recommendationGateway={recommendationGateway}
                        matchingConsent={matchingConsent}
                        onConfirmed={(journey) => {
                          setRestoredJourney(journey);
                          setPlanWeeks(journey.weeks.length);
                          setTodayView("plan");
                        }}
                      />
                    )}

                    {onboardingStarted && !journeyStarted && (
                      <OnboardingFlow
                        locale={locale}
                        transcriptAdapter={voiceAdapter}
                        profileGateway={profileBoundary}
                        extractionGateway={profileExtractionGateway}
                        onConfirmed={journeyGateway ? (profile) => {
                          setMatchingConsent(profile.matchingConsent);
                          setPlanWeeks(profile.planWeeks);
                          setJourneyStarted(true);
                        } : undefined}
                      />
                    )}

                    {!onboardingStarted && (
                      <section className="today-view" aria-labelledby="today-heading">
                        <div className="next-step-block">
                          <div>
                            <p className="section-label">{locale === "en" ? "Your next step" : "आपका अगला कदम"}</p>
                            <h1 id="today-heading" data-screen-heading tabIndex={-1}>{text.startHeading}</h1>
                            <p>{text.startBody}</p>
                          </div>
                          <button className="primary-button next-action" type="button" onClick={() => setOnboardingStarted(true)}>
                            <Sparkles aria-hidden="true" />
                            {text.startAction}
                          </button>
                        </div>

                        <div className="how-it-works" aria-label={locale === "en" ? "How SakhiCircle works" : "SakhiCircle कैसे काम करता है"}>
                          {isNarrowViewport ? (
                            <button
                              className="steps-toggle"
                              type="button"
                              aria-expanded={stepsOpen}
                              aria-controls={stepsId}
                              onClick={() => setStepsOpen((open) => !open)}
                            >
                              <span className="steps-toggle-title">{locale === "en" ? "How SakhiCircle works" : "SakhiCircle कैसे काम करता है"}</span>
                              <span className="section-note">{locale === "en" ? "Three simple steps" : "तीन आसान कदम"}</span>
                              <ChevronDown aria-hidden="true" />
                            </button>
                          ) : (
                            <div className="section-heading-row">
                              <h2>{locale === "en" ? "How SakhiCircle works" : "SakhiCircle कैसे काम करता है"}</h2>
                              <span className="section-note">{locale === "en" ? "Three simple steps" : "तीन आसान कदम"}</span>
                            </div>
                          )}
                          <ol id={stepsId} className={stepsOpen ? "steps-open" : undefined}>
                            <li><span>1</span><div><strong>{locale === "en" ? "Share your wish" : "अपनी इच्छा बताएँ"}</strong><p>{locale === "en" ? "Type what you want to learn." : "जो सीखना चाहती हैं, लिखें।"}</p></div></li>
                            <li><span>2</span><div><strong>{locale === "en" ? "Review your plan" : "अपनी योजना देखें"}</strong><p>{locale === "en" ? "Nothing is saved until you confirm it." : "आपकी पुष्टि से पहले कुछ भी सेव नहीं होगा।"}</p></div></li>
                            <li><span>3</span><div><strong>{locale === "en" ? "Meet your people" : "अपने लोगों से मिलें"}</strong><p>{locale === "en" ? "See why each partner, circle, or mentor fits." : "जानें कि हर साथी, सर्कल या मेंटर आपके लिए सही क्यों है।"}</p></div></li>
                          </ol>
                        </div>
                      </section>
                    )}
                  </>
                )}
              </div>

              <div
                id="today-panel-plan"
                role="tabpanel"
                aria-labelledby="today-tab-plan"
                hidden={todayView !== "plan"}
              >
                {restoredJourney && journeyGateway ? (
                  <JourneyFlow
                    locale={locale}
                    gateway={journeyGateway}
                    planWeeks={planWeeks}
                    recommendationGateway={recommendationGateway}
                    matchingConsent={matchingConsent}
                    initialJourney={restoredJourney}
                  />
                ) : (
                  <section className="empty-view plan-empty-view" aria-labelledby="plan-empty-heading">
                    <BookOpenText aria-hidden="true" />
                    <h1 id="plan-empty-heading" data-screen-heading tabIndex={-1}>{text.emptyPlanHeading}</h1>
                    <p>{text.emptyPlanBody}</p>
                    <button className="primary-button" type="button" onClick={() => {
                      setTodayView("today");
                      setOnboardingStarted(true);
                    }}>
                      {text.createMyPlan}
                    </button>
                  </section>
                )}
              </div>
            </>
          )}

          {destination === "circle" && (
            <section className="empty-view" aria-labelledby="circle-heading">
              <UsersRound aria-hidden="true" />
              <h1 id="circle-heading" data-screen-heading tabIndex={-1}>{text.circleHeading}</h1>
              <p>{text.circleBody}</p>
              <button className="secondary-button" type="button">{locale === "en" ? "How matching works" : "मैचिंग कैसे काम करती है"}</button>
            </section>
          )}

          {destination === "mentors" && (
            demoMode ? <DemoActivityCenter locale={locale} /> : <section className="empty-view" aria-labelledby="mentors-heading">
              <GraduationCap aria-hidden="true" />
              <h1 id="mentors-heading" data-screen-heading tabIndex={-1}>{text.mentorsHeading}</h1>
              <p>{text.mentorsBody}</p>
              <button className="secondary-button" type="button">{locale === "en" ? "What makes a verified mentor?" : "सत्यापित मेंटर कौन होता है?"}</button>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}

function Brand({ ariaLabel }: { ariaLabel: string }) {
  return (
    <a className="brand" href="#top" aria-label={ariaLabel}>
      <span className="brand-mark" aria-hidden="true"><Sparkles /></span>
      <span>SakhiCircle</span>
    </a>
  );
}
