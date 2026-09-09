import { ArrowLeft, Languages, ShieldCheck } from "lucide-react";
import { useState } from "react";

type Locale = "en" | "hi";

const copy = {
  en: {
    languageAction: "हिंदी में देखें",
    home: "Back to SakhiCircle home",
    eyebrow: "Your choices stay yours",
    title: "Privacy Policy",
    effective: "Effective 10 September 2026",
    intro: "This page explains how SakhiCircle uses YouTube API Services when you ask us to create a guided learning plan.",
    sections: [
      {
        title: "What we send to YouTube",
        body: "To find a suitable public course, we send only your normalized topic, learning level, and preferred plan language. We do not send your transcript, name, email address, city, accessibility choices, preferred learning format, or matching choices to YouTube.",
      },
      {
        title: "What we receive and how we use it",
        body: "We receive public playlist and video details such as IDs, exact titles, channel name, playlist order, duration, and available language or caption indicators. We use these details to select one sequential course and divide one or two videos into each week. SakhiCircle's learning overviews are not transcript summaries, and we do not access your YouTube account, history, subscriptions, or private videos.",
      },
      {
        title: "Storage and deletion",
        body: "Your written plan is stored separately from YouTube details. We keep recommended playlist and video metadata with your plan for no longer than 29 days, then it expires automatically. In a saved plan, choose “Remove video guide” to delete that metadata immediately while keeping your written plan.",
      },
      {
        title: "When you open YouTube",
        body: "Video links open YouTube without autoplay. Once you leave SakhiCircle, Google and YouTube control their own data and cookies. Removing a guide in SakhiCircle does not delete information held by YouTube.",
      },
    ],
    termsLead: "By using video recommendations, you also agree to the",
    youtubeTerms: "YouTube Terms of Service",
    googlePrivacy: "Google Privacy Policy",
  },
  hi: {
    languageAction: "View in English",
    home: "SakhiCircle होम पर वापस जाएँ",
    eyebrow: "आपकी पसंद पर आपका नियंत्रण",
    title: "गोपनीयता नीति",
    effective: "10 सितंबर 2026 से प्रभावी",
    intro: "यह पेज बताता है कि सीखने की गाइड वाली योजना बनाते समय SakhiCircle, YouTube API Services का उपयोग कैसे करता है।",
    sections: [
      {
        title: "हम YouTube को क्या भेजते हैं",
        body: "उपयुक्त सार्वजनिक पाठ्यक्रम खोजने के लिए हम केवल सामान्य किया हुआ विषय, सीखने का स्तर और योजना की पसंदीदा भाषा भेजते हैं। हम आपकी ट्रांसक्रिप्ट, नाम, ईमेल पता, शहर, सुविधाजनक विकल्प, सीखने का तरीका या मिलान की पसंद YouTube को नहीं भेजते।",
      },
      {
        title: "हमें क्या मिलता है और हम उसका उपयोग कैसे करते हैं",
        body: "हमें सार्वजनिक प्लेलिस्ट और वीडियो की ID, सही शीर्षक, चैनल का नाम, क्रम, अवधि और उपलब्ध भाषा या कैप्शन संकेत मिलते हैं। इनसे हम एक क्रमिक पाठ्यक्रम चुनकर हर सप्ताह में एक या दो वीडियो बाँटते हैं। SakhiCircle का सीखने का अवलोकन ट्रांसक्रिप्ट सारांश नहीं है। हम आपके YouTube खाते, इतिहास, सदस्यताओं या निजी वीडियो तक नहीं पहुँचते।",
      },
      {
        title: "स्टोरेज और हटाना",
        body: "आपकी लिखित योजना YouTube विवरण से अलग रखी जाती है। सुझाई गई प्लेलिस्ट और वीडियो का विवरण आपकी योजना के साथ 29 दिनों से अधिक नहीं रखा जाता और फिर अपने आप समाप्त हो जाता है। सेव की हुई योजना में “वीडियो गाइड हटाएँ” चुनकर आप यह विवरण तुरंत हटा सकती हैं; लिखित योजना बनी रहेगी।",
      },
      {
        title: "YouTube खोलने पर",
        body: "वीडियो लिंक YouTube को अपने आप चलाए बिना खोलते हैं। SakhiCircle से बाहर जाने के बाद Google और YouTube अपने डेटा और कुकीज़ को नियंत्रित करते हैं। SakhiCircle में गाइड हटाने से YouTube के पास मौजूद जानकारी नहीं मिटती।",
      },
    ],
    termsLead: "वीडियो सुझावों का उपयोग करके आप इनसे भी सहमत होती हैं:",
    youtubeTerms: "YouTube सेवा की शर्तें",
    googlePrivacy: "Google गोपनीयता नीति",
  },
} as const;

export function PrivacyPolicy() {
  const [locale, setLocale] = useState<Locale>("en");
  const text = copy[locale];

  return (
    <div className="privacy-page" lang={locale === "hi" ? "hi" : "en-IN"}>
      <a className="skip-link" href="#privacy-content">
        {locale === "en" ? "Skip to privacy policy" : "गोपनीयता नीति पर जाएँ"}
      </a>
      <header className="privacy-header">
        <a className="brand" href="/" aria-label={locale === "en" ? "SakhiCircle home" : "SakhiCircle होम"}>
          <span className="brand-mark" aria-hidden="true"><ShieldCheck /></span>
          <span>SakhiCircle</span>
        </a>
        <button className="language-button" type="button" onClick={() => setLocale(locale === "en" ? "hi" : "en")}>
          <Languages aria-hidden="true" />
          {text.languageAction}
        </button>
      </header>

      <main id="privacy-content" className="privacy-main">
        <a className="privacy-home-link" href="/"><ArrowLeft aria-hidden="true" />{text.home}</a>
        <p className="section-label">{text.eyebrow}</p>
        <h1>{text.title}</h1>
        <p className="privacy-effective">{text.effective}</p>
        <p className="privacy-intro">{text.intro}</p>
        <div className="privacy-sections">
          {text.sections.map((section) => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              <p>{section.body}</p>
            </section>
          ))}
        </div>
        <p className="privacy-third-party">
          {text.termsLead}{" "}
          <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">{text.youtubeTerms}</a>
          {" · "}
          <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">{text.googlePrivacy}</a>
        </p>
      </main>
    </div>
  );
}
