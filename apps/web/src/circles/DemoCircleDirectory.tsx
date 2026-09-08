import {
  CalendarDays,
  CarFront,
  ChefHat,
  Footprints,
  Languages,
  MapPin,
  Music2,
  Palette,
  Scissors,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

type Locale = "en" | "hi";

interface LocalizedText {
  en: string;
  hi: string;
}

interface DemoCircle {
  id: string;
  icon: LucideIcon;
  title: LocalizedText;
  description: LocalizedText;
  schedule: LocalizedText;
  place: LocalizedText;
  language: LocalizedText;
  pace: LocalizedText;
}

const circles: DemoCircle[] = [
  {
    id: "confident-driving",
    icon: CarFront,
    title: { en: "Confident Driving Circle", hi: "आत्मविश्वास से ड्राइविंग सर्कल" },
    description: {
      en: "Build road confidence through calm, supervised practice and shared preparation.",
      hi: "शांत, निगरानी वाले अभ्यास और साझा तैयारी से सड़क पर आत्मविश्वास बढ़ाएँ।",
    },
    schedule: { en: "Saturday · 8:00 AM", hi: "शनिवार · सुबह 8:00 बजे" },
    place: { en: "Practice ground · Indiranagar", hi: "अभ्यास मैदान · इंदिरानगर" },
    language: { en: "Hindi & English", hi: "हिंदी और अंग्रेज़ी" },
    pace: { en: "Beginner · Weekly", hi: "शुरुआती · हर सप्ताह" },
  },
  {
    id: "everyday-painting",
    icon: Palette,
    title: { en: "Everyday Painting Circle", hi: "रोज़मर्रा की पेंटिंग सर्कल" },
    description: {
      en: "Explore colour and simple watercolour studies using objects already at home.",
      hi: "घर में मौजूद वस्तुओं से रंग और सरल वॉटरकलर अभ्यास सीखें।",
    },
    schedule: { en: "Sunday · 4:00 PM", hi: "रविवार · शाम 4:00 बजे" },
    place: { en: "Online · Google Meet", hi: "ऑनलाइन · Google Meet" },
    language: { en: "English & Hindi", hi: "अंग्रेज़ी और हिंदी" },
    pace: { en: "Beginner · Weekly", hi: "शुरुआती · हर सप्ताह" },
  },
  {
    id: "dance-with-rhythm",
    icon: Music2,
    title: { en: "Joyful Dancing Circle", hi: "लय के साथ नृत्य सर्कल" },
    description: {
      en: "Restart dance with gentle rhythm practice and seated alternatives when needed.",
      hi: "हल्के लय अभ्यास से नृत्य फिर शुरू करें; ज़रूरत पर बैठकर करने का विकल्प भी है।",
    },
    schedule: { en: "Wednesday · 6:00 PM", hi: "बुधवार · शाम 6:00 बजे" },
    place: { en: "Community hall · Jayanagar", hi: "सामुदायिक हॉल · जयनगर" },
    language: { en: "Kannada & Hindi", hi: "कन्नड़ और हिंदी" },
    pace: { en: "Restarting · Weekly", hi: "फिर शुरुआत · हर सप्ताह" },
  },
  {
    id: "steady-steps",
    icon: Footprints,
    title: { en: "Steady Steps Walking Circle", hi: "सहज कदम वॉकिंग सर्कल" },
    description: {
      en: "Take a comfortable park walk with pauses, conversation, and a clear meeting point.",
      hi: "आराम से पार्क में चलें, बीच में रुकें, बात करें और तय जगह पर मिलें।",
    },
    schedule: { en: "Tuesday & Thursday · 7:00 AM", hi: "मंगलवार और गुरुवार · सुबह 7:00 बजे" },
    place: { en: "Cubbon Park · Central Library gate", hi: "कब्बन पार्क · सेंट्रल लाइब्रेरी गेट" },
    language: { en: "Kannada, Hindi & English", hi: "कन्नड़, हिंदी और अंग्रेज़ी" },
    pace: { en: "Comfortable pace · Twice weekly", hi: "सहज गति · सप्ताह में दो बार" },
  },
  {
    id: "sew-and-mend",
    icon: Scissors,
    title: { en: "Neighbourhood Sewing Circle", hi: "सिलाई और मरम्मत सर्कल" },
    description: {
      en: "Practise useful hand stitches and simple repairs in a patient small group.",
      hi: "धैर्य वाले छोटे समूह में उपयोगी हाथ की सिलाई और सरल मरम्मत का अभ्यास करें।",
    },
    schedule: { en: "Tuesday · 11:00 AM", hi: "मंगलवार · सुबह 11:00 बजे" },
    place: { en: "Neighbourhood studio · Malleshwaram", hi: "पड़ोस का स्टूडियो · मल्लेश्वरम" },
    language: { en: "Hindi & Kannada", hi: "हिंदी और कन्नड़" },
    pace: { en: "All levels · Fortnightly", hi: "सभी स्तर · हर दो सप्ताह" },
  },
  {
    id: "home-kitchen",
    icon: ChefHat,
    title: { en: "Home Cooking Exchange Circle", hi: "घर की रसोई साझा सर्कल" },
    description: {
      en: "Learn one practical recipe at a time and exchange trusted kitchen techniques.",
      hi: "एक बार में एक उपयोगी व्यंजन सीखें और भरोसेमंद रसोई तरीके साझा करें।",
    },
    schedule: { en: "Friday · 3:30 PM", hi: "शुक्रवार · दोपहर 3:30 बजे" },
    place: { en: "Online · Google Meet", hi: "ऑनलाइन · Google Meet" },
    language: { en: "Hindi & English", hi: "हिंदी और अंग्रेज़ी" },
    pace: { en: "All levels · Weekly", hi: "सभी स्तर · हर सप्ताह" },
  },
];

const copy = {
  en: {
    label: "Demo circle directory",
    title: "Find a circle to begin with",
    intro: "Choose a small, purpose-led group for shared practice. These sample circles use synthetic details and do not rank people or groups.",
    synthetic: "Synthetic demo circle",
    schedule: "Schedule",
    place: "Meeting place",
    language: "Languages",
    pace: "Level and pace",
    join: "Join",
    joined: "Joined",
    confirmation: (circle: DemoCircle) => `You joined ${circle.title.en}. Your first meetup is ${circle.schedule.en.replace(" · ", " at ")}.`,
  },
  hi: {
    label: "डेमो सर्कल सूची",
    title: "शुरुआत के लिए अपना सर्कल चुनें",
    intro: "साथ मिलकर अभ्यास करने के लिए छोटा, उद्देश्यपूर्ण समूह चुनें। ये नमूना सर्कल काल्पनिक हैं और लोकप्रियता के अंक नहीं दिखाते।",
    synthetic: "काल्पनिक डेमो सर्कल",
    schedule: "समय",
    place: "मिलने की जगह",
    language: "भाषाएँ",
    pace: "स्तर और गति",
    join: "जुड़ें",
    joined: "जुड़ गईं",
    confirmation: (circle: DemoCircle) => `आप ${circle.title.hi} से जुड़ गई हैं। आपकी पहली बैठक ${circle.schedule.hi.replace(" · ", " ")} है।`,
  },
} as const;

interface DemoCircleDirectoryProps {
  locale: Locale;
  title?: string;
}

export function DemoCircleDirectory({ locale, title }: DemoCircleDirectoryProps) {
  const [joinedIds, setJoinedIds] = useState<Set<string>>(() => new Set());
  const [lastJoinedId, setLastJoinedId] = useState<string | null>(null);
  const [matchingOpen, setMatchingOpen] = useState(false);
  const text = copy[locale];
  const joinedCircle = circles.find((circle) => circle.id === lastJoinedId);

  const joinCircle = (circleId: string) => {
    setJoinedIds((current) => new Set(current).add(circleId));
    setLastJoinedId(circleId);
  };

  return (
    <section className="circle-directory" aria-labelledby="circle-directory-title">
      <header className="circle-directory-heading">
        <p className="section-label"><ShieldCheck aria-hidden="true" /> {text.label}</p>
        <h1 id="circle-directory-title" data-screen-heading tabIndex={-1}>{title ?? text.title}</h1>
        <p>{text.intro}</p>
        <button
          className="circle-matching-button"
          type="button"
          aria-expanded={matchingOpen}
          aria-controls="circle-matching-note"
          onClick={() => setMatchingOpen((open) => !open)}
        >
          {locale === "en" ? "How matching works" : "मैचिंग कैसे काम करती है"}
        </button>
        {matchingOpen && (
          <p id="circle-matching-note" className="circle-matching-note">
            {locale === "en"
              ? "Circles are chosen by activity, language, pace, format, and compatible timing—not popularity."
              : "सर्कल गतिविधि, भाषा, गति, तरीके और सुविधाजनक समय से चुने जाते हैं—लोकप्रियता से नहीं।"}
          </p>
        )}
      </header>

      {joinedCircle && <p className="circle-confirmation" role="status">{text.confirmation(joinedCircle)}</p>}

      <div className="circle-list">
        {circles.map((circle) => {
          const Icon = circle.icon;
          const joined = joinedIds.has(circle.id);
          return (
            <article className="circle-listing" key={circle.id}>
              <span className="circle-icon" aria-hidden="true"><Icon /></span>
              <div className="circle-listing-main">
                <span className="synthetic-label">{text.synthetic}</span>
                <h2>{circle.title[locale]}</h2>
                <p>{circle.description[locale]}</p>
                <dl className="circle-details">
                  <div><dt><CalendarDays aria-hidden="true" /><span>{text.schedule}</span></dt><dd>{circle.schedule[locale]}</dd></div>
                  <div><dt><MapPin aria-hidden="true" /><span>{text.place}</span></dt><dd>{circle.place[locale]}</dd></div>
                  <div><dt><Languages aria-hidden="true" /><span>{text.language}</span></dt><dd>{circle.language[locale]}</dd></div>
                  <div><dt>{text.pace}</dt><dd>{circle.pace[locale]}</dd></div>
                </dl>
              </div>
              <button
                className={joined ? "secondary-button" : "primary-button"}
                type="button"
                onClick={() => joinCircle(circle.id)}
                disabled={joined}
                aria-label={`${joined ? text.joined : text.join} ${circle.title[locale]}`}
              >
                {joined ? text.joined : text.join}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}
