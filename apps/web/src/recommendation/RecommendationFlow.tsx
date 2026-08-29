import { CheckCircle2, ShieldCheck, UsersRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "../onboarding/runtime";
import type { RecommendationGateway, RecommendationResponse } from "./runtime";


interface RecommendationFlowProps {
  locale: Locale;
  matchingConsent: boolean;
  gateway: RecommendationGateway;
}

type FlowState = "idle" | "loading" | "matched" | "no_matches" | "error";

const copy = {
  en: {
    inviteTitle: "Your plan is saved. Meet a learning partner when you are ready.",
    inviteBody: "We will check compatible synthetic profiles using only your reviewed matching details.",
    find: "Find my learning partner",
    loading: "Checking compatible demo profiles…",
    resultTitle: "Your demo learning partner",
    synthetic: "Demo match — synthetic profile",
    score: (score: number) => `Match score: ${score} out of 100`,
    why: "Why this match fits",
    explanation: "This score explains compatibility; it is not a guarantee, popularity measure, or assessment of either woman.",
    how: "How matching works",
    howIntro: "We first remove profiles without active permission or compatible hobby, language, practice capacity, format, and safety preferences. Remaining profiles need at least 65 out of 100.",
    factor: "Factor",
    weight: "Maximum points",
    factors: [
      ["Hobby and goal", "30"],
      ["Schedule", "20"],
      ["Language", "15"],
      ["Skill level", "15"],
      ["Pace", "10"],
      ["Format", "10"],
      ["Price (not used yet)", "0"],
    ],
    noMatch: "We couldn't find a compatible demo match yet. Your learning plan is still ready, and you can try again later.",
    error: "We couldn't check matches right now. Your saved plan is still ready; check the connection and retry.",
    retry: "Try matching again",
    consentTitle: "Your learning plan is ready",
    consentBody: "Matching permission is off, so SakhiCircle will not request or show partner suggestions.",
    reviewConsent: "Review matching permission",
    consentDetail: "Matching uses only your reviewed hobby, language, practice capacity, learning format, and city when in-person learning is selected. It never uses accessibility needs to rank people.",
  },
  hi: {
    inviteTitle: "आपकी योजना सेव है। तैयार होने पर सीखने की साथी से मिलें।",
    inviteBody: "हम केवल आपकी जाँची हुई मैचिंग जानकारी से अनुकूल काल्पनिक प्रोफ़ाइल देखेंगे।",
    find: "मेरी सीखने की साथी खोजें",
    loading: "अनुकूल डेमो प्रोफ़ाइल देखी जा रही हैं…",
    resultTitle: "आपकी डेमो सीखने की साथी",
    synthetic: "डेमो मैच — काल्पनिक प्रोफ़ाइल",
    score: (score: number) => `मैच स्कोर: 100 में से ${score}`,
    why: "यह साथी क्यों उपयुक्त है",
    explanation: "यह स्कोर केवल अनुकूलता समझाता है; यह गारंटी, लोकप्रियता या किसी महिला का मूल्यांकन नहीं है।",
    how: "मैचिंग कैसे काम करती है",
    howIntro: "पहले हम बिना सक्रिय अनुमति या असंगत शौक, भाषा, अभ्यास क्षमता, सीखने के तरीके और सुरक्षा पसंद वाली प्रोफ़ाइल हटाते हैं। बाकी प्रोफ़ाइल को 100 में से कम से कम 65 अंक चाहिए।",
    factor: "कारक",
    weight: "अधिकतम अंक",
    factors: [
      ["शौक और लक्ष्य", "30"],
      ["समय", "20"],
      ["भाषा", "15"],
      ["कौशल स्तर", "15"],
      ["गति", "10"],
      ["सीखने का तरीका", "10"],
      ["कीमत (अभी उपयोग नहीं)", "0"],
    ],
    noMatch: "अभी कोई उपयुक्त डेमो मैच नहीं मिला। आपकी सीखने की योजना तैयार है और आप बाद में फिर कोशिश कर सकती हैं।",
    error: "अभी मैच नहीं देख सके। आपकी सेव की हुई योजना तैयार है; कनेक्शन जाँचकर फिर कोशिश करें।",
    retry: "मैचिंग फिर आज़माएँ",
    consentTitle: "आपकी सीखने की योजना तैयार है",
    consentBody: "मैचिंग की अनुमति बंद है, इसलिए SakhiCircle साथी के सुझाव नहीं माँगेगा या दिखाएगा।",
    reviewConsent: "मैचिंग की अनुमति जाँचें",
    consentDetail: "मैचिंग में केवल आपका जाँचा हुआ शौक, भाषा, अभ्यास क्षमता, सीखने का तरीका और आमने-सामने सीखने पर शहर इस्तेमाल होता है। सुविधा की ज़रूरतों से कभी लोगों की रैंकिंग नहीं होती।",
  },
} as const;

export function RecommendationFlow({ locale, matchingConsent, gateway }: RecommendationFlowProps) {
  const [state, setState] = useState<FlowState>("idle");
  const [response, setResponse] = useState<RecommendationResponse | null>(null);
  const [permissionOpen, setPermissionOpen] = useState(false);
  const gatewayRef = useRef(gateway);
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const text = copy[locale];

  useEffect(() => {
    gatewayRef.current = gateway;
  }, [gateway]);

  useEffect(() => {
    if (!matchingConsent) {
      setResponse(null);
      setState("idle");
    }
  }, [matchingConsent]);

  useEffect(() => {
    if (state === "matched") resultHeading.current?.focus();
  }, [state]);

  const find = async () => {
    if (!matchingConsent) return;
    setState("loading");
    setResponse(null);
    try {
      const found = await gatewayRef.current.find("partner");
      setResponse(found);
      setState(found.status === "matched" && found.results.length ? "matched" : "no_matches");
    } catch {
      setState("error");
    }
  };

  if (!matchingConsent) {
    return (
      <section className="recommendation-flow recommendation-consent" aria-labelledby="recommendation-consent-title">
        <ShieldCheck aria-hidden="true" />
        <div>
          <h2 id="recommendation-consent-title">{text.consentTitle}</h2>
          <p>{text.consentBody}</p>
          <button
            className="secondary-button"
            type="button"
            aria-expanded={permissionOpen}
            aria-controls="matching-permission-detail"
            onClick={() => setPermissionOpen((open) => !open)}
          >
            {text.reviewConsent}
          </button>
          {permissionOpen && <p id="matching-permission-detail" className="permission-detail">{text.consentDetail}</p>}
        </div>
      </section>
    );
  }

  if (state === "loading") {
    return (
      <section className="recommendation-flow recommendation-loading" aria-busy="true">
        <p role="status">{text.loading}</p>
        <span aria-hidden="true" />
        <span aria-hidden="true" />
        <span aria-hidden="true" />
      </section>
    );
  }

  if (state === "error") {
    return (
      <section className="recommendation-flow recommendation-state">
        <p className="save-error" role="alert">{text.error}</p>
        <button className="secondary-button" type="button" onClick={find}>{text.retry}</button>
      </section>
    );
  }

  if (state === "no_matches") {
    return (
      <section className="recommendation-flow recommendation-state" aria-live="polite">
        <UsersRound aria-hidden="true" />
        <p>{text.noMatch}</p>
        <button className="secondary-button" type="button" onClick={find}>{text.retry}</button>
      </section>
    );
  }

  if (state === "matched" && response?.results[0]) {
    const result = response.results[0];
    return (
      <section className="recommendation-flow recommendation-result" aria-labelledby="recommendation-result-title">
        <header className="recommendation-result-heading">
          <span className="synthetic-label"><CheckCircle2 aria-hidden="true" />{text.synthetic}</span>
          <h2 id="recommendation-result-title" ref={resultHeading} tabIndex={-1}>{text.resultTitle}</h2>
          <p className="recommendation-name">{result.displayName}</p>
          <p>{result.hobby[locale]}</p>
          <p className="match-score">{text.score(result.score)}</p>
        </header>
        <div className="recommendation-reasons">
          <h3>{text.why}</h3>
          <ol>
            {result.reasons.map((reason) => (
              <li key={reason.factor}>
                <CheckCircle2 aria-hidden="true" />
                <span>{reason.text[locale]}</span>
              </li>
            ))}
          </ol>
          <p>{text.explanation}</p>
        </div>
        <details className="matching-disclosure">
          <summary>{text.how}</summary>
          <div>
            <p>{text.howIntro}</p>
            <table>
              <thead><tr><th scope="col">{text.factor}</th><th scope="col">{text.weight}</th></tr></thead>
              <tbody>
                {text.factors.map(([factor, weight]) => (
                  <tr key={factor}><th scope="row">{factor}</th><td>{weight}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>
    );
  }

  return (
    <section className="recommendation-flow recommendation-invitation" aria-labelledby="recommendation-invite-title">
      <UsersRound aria-hidden="true" />
      <div>
        <h2 id="recommendation-invite-title">{text.inviteTitle}</h2>
        <p>{text.inviteBody}</p>
        <button className="primary-button" type="button" onClick={find}>{text.find}</button>
      </div>
    </section>
  );
}

