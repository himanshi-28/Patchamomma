import { CalendarDays, Clock3, IndianRupee, MapPin, ShieldCheck, UserRoundCheck } from "lucide-react";
import { useState } from "react";

type Locale = "en" | "hi";

interface DemoActivityCenterProps {
  locale: Locale;
}

interface LocalizedText {
  en: string;
  hi: string;
}

interface DemoActivity {
  id: string;
  title: LocalizedText;
  category: LocalizedText;
  mentor: string;
  time: LocalizedText;
  location: LocalizedText;
  price: string;
}

const activities: DemoActivity[] = [
  {
    id: "kathak-rhythm",
    title: { en: "Kathak: Begin with rhythm", hi: "कथक: लय से शुरुआत" },
    category: { en: "Dance · Beginner", hi: "नृत्य · शुरुआती" },
    mentor: "Nandita Rao",
    time: { en: "Sat, 12 Sep · 10:30 AM", hi: "शनि, 12 सित॰ · सुबह 10:30" },
    location: { en: "Indiranagar, Bengaluru", hi: "इंदिरानगर, बेंगलुरु" },
    price: "₹450",
  },
  {
    id: "paint-postcard",
    title: { en: "Paint your first postcard", hi: "अपना पहला पोस्टकार्ड पेंट करें" },
    category: { en: "Painting · Beginner", hi: "चित्रकला · शुरुआती" },
    mentor: "Farida Khan",
    time: { en: "Sun, 13 Sep · 4:00 PM", hi: "रवि, 13 सित॰ · शाम 4:00" },
    location: { en: "Online · Google Meet", hi: "ऑनलाइन · Google Meet" },
    price: "₹300",
  },
  {
    id: "garden-balcony",
    title: { en: "Balcony garden basics", hi: "बालकनी बागवानी की शुरुआत" },
    category: { en: "Gardening · All levels", hi: "बागवानी · सभी स्तर" },
    mentor: "Meena Iyer",
    time: { en: "Tue, 15 Sep · 11:00 AM", hi: "मंगल, 15 सित॰ · सुबह 11:00" },
    location: { en: "Jayanagar, Bengaluru", hi: "जयनगर, बेंगलुरु" },
    price: "₹250",
  },
  {
    id: "phone-photography",
    title: { en: "Everyday phone photography", hi: "रोज़मर्रा की फ़ोन फ़ोटोग्राफ़ी" },
    category: { en: "Photography · Beginner", hi: "फ़ोटोग्राफ़ी · शुरुआती" },
    mentor: "Shobha Menon",
    time: { en: "Thu, 17 Sep · 5:30 PM", hi: "गुरु, 17 सित॰ · शाम 5:30" },
    location: { en: "Cubbon Park, Bengaluru", hi: "कब्बन पार्क, बेंगलुरु" },
    price: "₹400",
  },
  {
    id: "hindustani-voice",
    title: { en: "Hindustani voice warm-ups", hi: "हिंदुस्तानी गायन का रियाज़" },
    category: { en: "Music · Restarting", hi: "संगीत · फिर शुरुआत" },
    mentor: "Rukmini Das",
    time: { en: "Sat, 19 Sep · 9:00 AM", hi: "शनि, 19 सित॰ · सुबह 9:00" },
    location: { en: "Online · Zoom", hi: "ऑनलाइन · Zoom" },
    price: "₹350",
  },
  {
    id: "block-printing",
    title: { en: "Block-print a table runner", hi: "ब्लॉक-प्रिंट टेबल रनर बनाएँ" },
    category: { en: "Craft · All levels", hi: "हस्तकला · सभी स्तर" },
    mentor: "Asha Kulkarni",
    time: { en: "Sun, 20 Sep · 2:00 PM", hi: "रवि, 20 सित॰ · दोपहर 2:00" },
    location: { en: "Malleshwaram, Bengaluru", hi: "मल्लेश्वरम, बेंगलुरु" },
    price: "₹550",
  },
];

const copy = {
  en: {
    title: "Activities near you",
    intro: "Try a small-group session with a demo mentor. These sample listings never charge you.",
    demoHeader: "Demo activity centre",
    synthetic: "Synthetic demo listing",
    mentor: "Demo mentor",
    join: "Join",
    joined: "Joined",
    confirmation: (activity: DemoActivity) => `Demo booking saved for ${activity.title.en} with ${activity.mentor}. No payment was taken.`,
  },
  hi: {
    title: "आपके पास की गतिविधियाँ",
    intro: "डेमो मेंटर के साथ छोटा समूह सत्र आज़माएँ। इन नमूना सूचियों में कोई भुगतान नहीं लिया जाएगा।",
    demoHeader: "डेमो गतिविधि केंद्र",
    synthetic: "काल्पनिक डेमो सूची",
    mentor: "डेमो मेंटर",
    join: "जुड़ें",
    joined: "जुड़ गईं",
    confirmation: (activity: DemoActivity) => `${activity.mentor} के साथ ${activity.title.hi} की डेमो बुकिंग सेव हुई। कोई भुगतान नहीं लिया गया।`,
  },
} as const;

export function DemoActivityCenter({ locale }: DemoActivityCenterProps) {
  const [joinedIds, setJoinedIds] = useState<Set<string>>(() => new Set());
  const [lastJoinedId, setLastJoinedId] = useState<string | null>(null);
  const text = copy[locale];
  const joinedActivity = activities.find((activity) => activity.id === lastJoinedId);

  const join = (activityId: string) => {
    setJoinedIds((current) => new Set(current).add(activityId));
    setLastJoinedId(activityId);
  };

  return (
    <section className="activity-center" aria-labelledby="activity-center-title">
      <header className="activity-center-heading">
        <div>
          <p className="section-label"><ShieldCheck aria-hidden="true" /> {text.demoHeader}</p>
          <h1 id="activity-center-title" data-screen-heading tabIndex={-1}>{text.title}</h1>
          <p>{text.intro}</p>
        </div>
      </header>

      {joinedActivity && (
        <p className="activity-confirmation" role="status">
          {text.confirmation(joinedActivity)}
        </p>
      )}

      <div className="activity-list">
        {activities.map((activity) => {
          const joined = joinedIds.has(activity.id);
          return (
            <article className="activity-listing" key={activity.id}>
              <div className="activity-listing-main">
                <span className="activity-category">{activity.category[locale]}</span>
                <h2>{activity.title[locale]}</h2>
                <p className="activity-mentor"><UserRoundCheck aria-hidden="true" /> {activity.mentor} · {text.mentor}</p>
                <dl className="activity-details">
                  <div><dt><CalendarDays aria-hidden="true" /><span className="visually-hidden">{locale === "en" ? "Date" : "तारीख"}</span></dt><dd>{activity.time[locale]}</dd></div>
                  <div><dt><MapPin aria-hidden="true" /><span className="visually-hidden">{locale === "en" ? "Location" : "स्थान"}</span></dt><dd>{activity.location[locale]}</dd></div>
                  <div><dt><IndianRupee aria-hidden="true" /><span className="visually-hidden">{locale === "en" ? "Price" : "कीमत"}</span></dt><dd>{activity.price}</dd></div>
                </dl>
                <p className="synthetic-label"><Clock3 aria-hidden="true" /> {text.synthetic}</p>
              </div>
              <button
                className={joined ? "secondary-button" : "primary-button"}
                type="button"
                onClick={() => join(activity.id)}
                disabled={joined}
                aria-label={`${joined ? text.joined : text.join} ${activity.title[locale]}`}
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
