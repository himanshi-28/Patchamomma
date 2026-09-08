import {
  CalendarDays,
  CheckCircle2,
  Clock3,
  GraduationCap,
  Languages,
  MapPin,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";
import { FormEvent, useEffect, useId, useMemo, useRef, useState } from "react";

type Locale = "en" | "hi";
type ClassFormat = "Online" | "In person";

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
  categoryKey: string;
  level: LocalizedText;
  mentor: string;
  dateKey: string;
  dateShort: LocalizedText;
  dateFull: LocalizedText;
  time: LocalizedText;
  location: LocalizedText;
  format: ClassFormat;
  language: LocalizedText;
  duration: LocalizedText;
  seats: LocalizedText;
  referenceFee: string;
  joiningInstructions: LocalizedText;
}

const activities: DemoActivity[] = [
  {
    id: "kathak-rhythm",
    title: { en: "Kathak: Begin with rhythm", hi: "कथक: लय से शुरुआत" },
    category: { en: "Dance", hi: "नृत्य" },
    categoryKey: "Dance",
    level: { en: "Beginner", hi: "शुरुआती" },
    mentor: "Nandita Rao",
    dateKey: "2026-09-12",
    dateShort: { en: "Sat 12 Sep", hi: "शनि 12 सित॰" },
    dateFull: { en: "Saturday, 12 September 2026", hi: "शनिवार, 12 सितंबर 2026" },
    time: { en: "10:30 AM", hi: "सुबह 10:30" },
    location: { en: "Indiranagar, Bengaluru", hi: "इंदिरानगर, बेंगलुरु" },
    format: "In person",
    language: { en: "English & Hindi", hi: "अंग्रेज़ी और हिंदी" },
    duration: { en: "60 minutes", hi: "60 मिनट" },
    seats: { en: "4 demo seats left", hi: "4 डेमो सीट बाकी" },
    referenceFee: "₹450",
    joiningInstructions: { en: "Arrive 10 minutes early. The demo host will meet you at reception.", hi: "10 मिनट पहले आएँ। डेमो होस्ट रिसेप्शन पर मिलेंगी।" },
  },
  {
    id: "paint-postcard",
    title: { en: "Paint your first postcard", hi: "अपना पहला पोस्टकार्ड पेंट करें" },
    category: { en: "Painting", hi: "चित्रकला" },
    categoryKey: "Painting",
    level: { en: "Beginner", hi: "शुरुआती" },
    mentor: "Farida Khan",
    dateKey: "2026-09-13",
    dateShort: { en: "Sun 13 Sep", hi: "रवि 13 सित॰" },
    dateFull: { en: "Sunday, 13 September 2026", hi: "रविवार, 13 सितंबर 2026" },
    time: { en: "4:00 PM", hi: "शाम 4:00" },
    location: { en: "Online · Google Meet", hi: "ऑनलाइन · Google Meet" },
    format: "Online",
    language: { en: "Hindi", hi: "हिंदी" },
    duration: { en: "45 minutes", hi: "45 मिनट" },
    seats: { en: "7 demo seats left", hi: "7 डेमो सीट बाकी" },
    referenceFee: "₹300",
    joiningInstructions: { en: "A sample Google Meet link will appear here 15 minutes before class.", hi: "क्लास से 15 मिनट पहले यहाँ नमूना Google Meet लिंक दिखेगा।" },
  },
  {
    id: "garden-balcony",
    title: { en: "Balcony garden basics", hi: "बालकनी बागवानी की शुरुआत" },
    category: { en: "Gardening", hi: "बागवानी" },
    categoryKey: "Gardening",
    level: { en: "All levels", hi: "सभी स्तर" },
    mentor: "Meena Iyer",
    dateKey: "2026-09-15",
    dateShort: { en: "Tue 15 Sep", hi: "मंगल 15 सित॰" },
    dateFull: { en: "Tuesday, 15 September 2026", hi: "मंगलवार, 15 सितंबर 2026" },
    time: { en: "11:00 AM", hi: "सुबह 11:00" },
    location: { en: "Jayanagar, Bengaluru", hi: "जयनगर, बेंगलुरु" },
    format: "In person",
    language: { en: "English & Tamil", hi: "अंग्रेज़ी और तमिल" },
    duration: { en: "75 minutes", hi: "75 मिनट" },
    seats: { en: "5 demo seats left", hi: "5 डेमो सीट बाकी" },
    referenceFee: "₹250",
    joiningInstructions: { en: "Bring one photo of your balcony; tools are provided in this demo.", hi: "अपनी बालकनी की एक फोटो लाएँ; डेमो में औज़ार दिए जाएँगे।" },
  },
  {
    id: "phone-photography",
    title: { en: "Everyday phone photography", hi: "रोज़मर्रा की फ़ोन फ़ोटोग्राफ़ी" },
    category: { en: "Photography", hi: "फ़ोटोग्राफ़ी" },
    categoryKey: "Photography",
    level: { en: "Beginner", hi: "शुरुआती" },
    mentor: "Shobha Menon",
    dateKey: "2026-09-17",
    dateShort: { en: "Thu 17 Sep", hi: "गुरु 17 सित॰" },
    dateFull: { en: "Thursday, 17 September 2026", hi: "गुरुवार, 17 सितंबर 2026" },
    time: { en: "5:30 PM", hi: "शाम 5:30" },
    location: { en: "Cubbon Park, Bengaluru", hi: "कब्बन पार्क, बेंगलुरु" },
    format: "In person",
    language: { en: "English & Malayalam", hi: "अंग्रेज़ी और मलयालम" },
    duration: { en: "60 minutes", hi: "60 मिनट" },
    seats: { en: "3 demo seats left", hi: "3 डेमो सीट बाकी" },
    referenceFee: "₹400",
    joiningInstructions: { en: "Meet beside the main library entrance with your charged phone.", hi: "चार्ज किया हुआ फ़ोन लेकर मुख्य लाइब्रेरी प्रवेश के पास मिलें।" },
  },
  {
    id: "hindustani-voice",
    title: { en: "Hindustani voice warm-ups", hi: "हिंदुस्तानी गायन का रियाज़" },
    category: { en: "Music", hi: "संगीत" },
    categoryKey: "Music",
    level: { en: "Restarting", hi: "फिर शुरुआत" },
    mentor: "Rukmini Das",
    dateKey: "2026-09-19",
    dateShort: { en: "Sat 19 Sep", hi: "शनि 19 सित॰" },
    dateFull: { en: "Saturday, 19 September 2026", hi: "शनिवार, 19 सितंबर 2026" },
    time: { en: "9:00 AM", hi: "सुबह 9:00" },
    location: { en: "Online · Zoom", hi: "ऑनलाइन · Zoom" },
    format: "Online",
    language: { en: "Hindi & Bengali", hi: "हिंदी और बंगाली" },
    duration: { en: "45 minutes", hi: "45 मिनट" },
    seats: { en: "6 demo seats left", hi: "6 डेमो सीट बाकी" },
    referenceFee: "₹350",
    joiningInstructions: { en: "A sample Zoom link will appear here 15 minutes before class.", hi: "क्लास से 15 मिनट पहले यहाँ नमूना Zoom लिंक दिखेगा।" },
  },
  {
    id: "block-printing",
    title: { en: "Block-print a table runner", hi: "ब्लॉक-प्रिंट टेबल रनर बनाएँ" },
    category: { en: "Craft", hi: "हस्तकला" },
    categoryKey: "Craft",
    level: { en: "All levels", hi: "सभी स्तर" },
    mentor: "Asha Kulkarni",
    dateKey: "2026-09-20",
    dateShort: { en: "Sun 20 Sep", hi: "रवि 20 सित॰" },
    dateFull: { en: "Sunday, 20 September 2026", hi: "रविवार, 20 सितंबर 2026" },
    time: { en: "2:00 PM", hi: "दोपहर 2:00" },
    location: { en: "Malleshwaram, Bengaluru", hi: "मल्लेश्वरम, बेंगलुरु" },
    format: "In person",
    language: { en: "English, Hindi & Marathi", hi: "अंग्रेज़ी, हिंदी और मराठी" },
    duration: { en: "90 minutes", hi: "90 मिनट" },
    seats: { en: "4 demo seats left", hi: "4 डेमो सीट बाकी" },
    referenceFee: "₹550",
    joiningInstructions: { en: "The demo studio provides fabric, blocks, and washable colours.", hi: "डेमो स्टूडियो कपड़ा, ब्लॉक और धुलने वाले रंग देगा।" },
  },
];

const copy = {
  en: {
    title: "Find a class that fits your week",
    intro: "Browse trusted demo mentors by interest, date, and format. Reserve a sample seat without payment.",
    demoHeader: "Mentor sessions · deterministic demo",
    register: "Register as a mentor",
    closeRegistration: "Close mentor registration",
    registrationTitle: "Share what you would love to teach",
    registrationIntro: "Tell us your teaching interest. This demo does not publish a course or collect bank details, identity documents, or payment information.",
    name: "Your name",
    expertise: "What would you like to teach?",
    language: "Preferred teaching language",
    format: "Preferred class format",
    chooseLanguage: "Choose a language",
    chooseFormat: "Choose a format",
    submitRegistration: "Submit mentor interest",
    registrationConfirmation: (name: string, expertise: string) => `Thank you, ${name}. Your demo mentor interest for ${expertise} is recorded for review. No public profile was created.`,
    browseTitle: "Browse mentor classes",
    interest: "Interest",
    allInterests: "All interests",
    classFormat: "Class format",
    anyFormat: "Any format",
    online: "Online",
    inPerson: "In person",
    dateGroup: "Choose a class date",
    allDates: "All dates",
    results: (count: number) => count === 1 ? "1 demo class found" : `${count} demo classes found`,
    noResults: "No demo classes match these filters",
    noResultsHelp: "Try another interest, format, or date.",
    clearFilters: "Clear filters",
    synthetic: "Synthetic demo class",
    mentor: "Verified demo mentor",
    referenceFee: "Reference fee",
    demoNoCharge: "Demo does not charge",
    book: (title: string) => `Book demo seat for ${title}`,
    booked: (title: string) => `Booked ${title}`,
    ticketTitle: "Your demo session ticket",
    ticketIntro: "Your sample seat is saved for this visit. Keep these details handy.",
    ticketLabels: ["Mentor", "Topic", "Language", "Date", "Time", "Payment status", "Joining instructions"],
    paymentStatus: "No payment taken — demo seat",
  },
  hi: {
    title: "अपने सप्ताह के लिए सही क्लास खोजें",
    intro: "रुचि, तारीख और तरीके के अनुसार भरोसेमंद डेमो मेंटर खोजें। बिना भुगतान के नमूना सीट बुक करें।",
    demoHeader: "मेंटर सेशन · निश्चित डेमो",
    register: "मेंटर के रूप में रजिस्टर करें",
    closeRegistration: "मेंटर रजिस्ट्रेशन बंद करें",
    registrationTitle: "बताएँ कि आप क्या सिखाना चाहेंगी",
    registrationIntro: "अपनी सिखाने की रुचि बताएँ। यह डेमो कोई कोर्स प्रकाशित नहीं करता और बैंक, पहचान या भुगतान की जानकारी नहीं लेता।",
    name: "आपका नाम",
    expertise: "आप क्या सिखाना चाहेंगी?",
    language: "सिखाने की पसंदीदा भाषा",
    format: "क्लास का पसंदीदा तरीका",
    chooseLanguage: "भाषा चुनें",
    chooseFormat: "तरीका चुनें",
    submitRegistration: "मेंटर रुचि भेजें",
    registrationConfirmation: (name: string, expertise: string) => `धन्यवाद, ${name}। ${expertise} सिखाने की आपकी डेमो मेंटर रुचि समीक्षा के लिए दर्ज हुई। कोई सार्वजनिक प्रोफ़ाइल नहीं बनी।`,
    browseTitle: "मेंटर क्लास खोजें",
    interest: "रुचि",
    allInterests: "सभी रुचियाँ",
    classFormat: "क्लास का तरीका",
    anyFormat: "कोई भी तरीका",
    online: "ऑनलाइन",
    inPerson: "आमने-सामने",
    dateGroup: "क्लास की तारीख चुनें",
    allDates: "सभी तारीखें",
    results: (count: number) => `${count} डेमो क्लास मिलीं`,
    noResults: "इन फ़िल्टर से कोई डेमो क्लास नहीं मिली",
    noResultsHelp: "दूसरी रुचि, तरीका या तारीख आज़माएँ।",
    clearFilters: "फ़िल्टर हटाएँ",
    synthetic: "काल्पनिक डेमो क्लास",
    mentor: "सत्यापित डेमो मेंटर",
    referenceFee: "संदर्भ शुल्क",
    demoNoCharge: "डेमो में शुल्क नहीं",
    book: (title: string) => `${title} के लिए डेमो सीट बुक करें`,
    booked: (title: string) => `${title} बुक हो गई`,
    ticketTitle: "आपका डेमो सेशन टिकट",
    ticketIntro: "इस विज़िट के लिए आपकी नमूना सीट सेव है। ये जानकारी अपने पास रखें।",
    ticketLabels: ["मेंटर", "विषय", "भाषा", "तारीख", "समय", "भुगतान स्थिति", "जुड़ने की जानकारी"],
    paymentStatus: "कोई भुगतान नहीं लिया — डेमो सीट",
  },
} as const;

const categories = ["Dance", "Painting", "Gardening", "Photography", "Music", "Craft"];

export function DemoActivityCenter({ locale }: DemoActivityCenterProps) {
  const [registrationOpen, setRegistrationOpen] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState("");
  const [interest, setInterest] = useState("");
  const [classFormat, setClassFormat] = useState("");
  const [date, setDate] = useState("");
  const [bookedIds, setBookedIds] = useState<Set<string>>(() => new Set());
  const [lastBookedId, setLastBookedId] = useState<string | null>(null);
  const registrationId = useId();
  const titleId = useId();
  const ticketHeading = useRef<HTMLHeadingElement>(null);
  const text = copy[locale];
  const bookedActivity = activities.find((activity) => activity.id === lastBookedId);

  const filteredActivities = useMemo(() => activities.filter((activity) => (
    (!interest || activity.categoryKey === interest)
    && (!classFormat || activity.format === classFormat)
    && (!date || activity.dateKey === date)
  )), [classFormat, date, interest]);

  useEffect(() => {
    if (lastBookedId) ticketHeading.current?.focus();
  }, [lastBookedId]);

  const clearFilters = () => {
    setInterest("");
    setClassFormat("");
    setDate("");
  };

  const book = (activityId: string) => {
    setBookedIds((current) => new Set(current).add(activityId));
    setLastBookedId(activityId);
  };

  const submitRegistration = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setRegistrationMessage(text.registrationConfirmation(
      String(data.get("mentor-name") ?? ""),
      String(data.get("mentor-expertise") ?? ""),
    ));
  };

  return (
    <section className="activity-center" aria-labelledby={titleId}>
      <header className="activity-center-heading">
        <div>
          <p className="section-label"><ShieldCheck aria-hidden="true" /> {text.demoHeader}</p>
          <h1 id={titleId} data-screen-heading tabIndex={-1}>{text.title}</h1>
          <p>{text.intro}</p>
        </div>
        <button
          className="secondary-button mentor-register-trigger"
          type="button"
          aria-expanded={registrationOpen}
          aria-controls={registrationId}
          onClick={() => setRegistrationOpen((open) => !open)}
        >
          <GraduationCap aria-hidden="true" />
          {registrationOpen ? text.closeRegistration : text.register}
        </button>
      </header>

      {registrationOpen && (
        <section id={registrationId} className="mentor-registration" aria-labelledby={`${registrationId}-title`}>
          <div>
            <h2 id={`${registrationId}-title`}>{text.registrationTitle}</h2>
            <p>{text.registrationIntro}</p>
          </div>
          <form onSubmit={submitRegistration}>
            <label>{text.name}<input name="mentor-name" required autoComplete="name" /></label>
            <label>{text.expertise}<input name="mentor-expertise" required /></label>
            <label>{text.language}
              <select name="mentor-language" required defaultValue="">
                <option value="" disabled>{text.chooseLanguage}</option>
                <option value="English">English</option>
                <option value="Hindi">Hindi</option>
                <option value="English & Hindi">English & Hindi</option>
              </select>
            </label>
            <label>{text.format}
              <select name="mentor-format" required defaultValue="">
                <option value="" disabled>{text.chooseFormat}</option>
                <option value="Online">{text.online}</option>
                <option value="In person">{text.inPerson}</option>
              </select>
            </label>
            <button className="primary-button" type="submit">{text.submitRegistration}</button>
          </form>
          {registrationMessage && <p className="mentor-registration-confirmation" role="status"><CheckCircle2 aria-hidden="true" />{registrationMessage}</p>}
        </section>
      )}

      {bookedActivity && (
        <section className="mentor-ticket" role="region" aria-labelledby="mentor-ticket-title">
          <header>
            <CheckCircle2 aria-hidden="true" />
            <div>
              <h2 id="mentor-ticket-title" ref={ticketHeading} tabIndex={-1}>{text.ticketTitle}</h2>
              <p>{text.ticketIntro}</p>
            </div>
          </header>
          <dl>
            {[bookedActivity.mentor, bookedActivity.title[locale], bookedActivity.language[locale], bookedActivity.dateFull[locale], bookedActivity.time[locale], text.paymentStatus, bookedActivity.joiningInstructions[locale]].map((value, index) => (
              <div key={text.ticketLabels[index]}><dt>{text.ticketLabels[index]}</dt><dd>{value}</dd></div>
            ))}
          </dl>
        </section>
      )}

      <section className="mentor-browser" aria-labelledby="mentor-browser-title">
        <div className="mentor-browser-heading">
          <h2 id="mentor-browser-title">{text.browseTitle}</h2>
          <p role="status" aria-live="polite">{filteredActivities.length ? text.results(filteredActivities.length) : text.noResults}</p>
        </div>

        <div className="mentor-filters">
          <label>{text.interest}
            <select value={interest} onChange={(event) => setInterest(event.target.value)}>
              <option value="">{text.allInterests}</option>
              {categories.map((category) => {
                const activity = activities.find((item) => item.categoryKey === category)!;
                return <option key={category} value={category}>{activity.category[locale]}</option>;
              })}
            </select>
          </label>
          <label>{text.classFormat}
            <select value={classFormat} onChange={(event) => setClassFormat(event.target.value)}>
              <option value="">{text.anyFormat}</option>
              <option value="Online">{text.online}</option>
              <option value="In person">{text.inPerson}</option>
            </select>
          </label>
        </div>

        <div className="mentor-date-strip" role="group" aria-label={text.dateGroup}>
          <button type="button" aria-pressed={!date} onClick={() => setDate("")}>{text.allDates}</button>
          {activities.map((activity) => (
            <button key={activity.dateKey} type="button" aria-pressed={date === activity.dateKey} onClick={() => setDate(activity.dateKey)}>
              {activity.dateShort[locale]}
            </button>
          ))}
        </div>

        {filteredActivities.length === 0 ? (
          <div className="mentor-empty-state">
            <CalendarDays aria-hidden="true" />
            <h3>{text.noResults}</h3>
            <p>{text.noResultsHelp}</p>
            <button className="secondary-button" type="button" onClick={clearFilters}>{text.clearFilters}</button>
          </div>
        ) : (
          <div className="activity-list">
            {filteredActivities.map((activity) => {
              const booked = bookedIds.has(activity.id);
              return (
                <article className="activity-listing" key={activity.id}>
                  <div className="activity-listing-main">
                    <div className="activity-listing-labels">
                      <span className="activity-category">{activity.category[locale]} · {activity.level[locale]}</span>
                      <span className="synthetic-label"><ShieldCheck aria-hidden="true" /> {text.synthetic}</span>
                    </div>
                    <h2>{activity.title[locale]}</h2>
                    <p className="activity-mentor"><UserRoundCheck aria-hidden="true" /> {activity.mentor} · {text.mentor}</p>
                    <dl className="activity-details">
                      <div><dt><CalendarDays aria-hidden="true" /><span className="visually-hidden">{text.ticketLabels[3]}</span></dt><dd>{activity.dateShort[locale]} · {activity.time[locale]}</dd></div>
                      <div><dt><MapPin aria-hidden="true" /><span className="visually-hidden">{locale === "en" ? "Location" : "स्थान"}</span></dt><dd>{activity.location[locale]}</dd></div>
                      <div><dt><Languages aria-hidden="true" /><span className="visually-hidden">{text.ticketLabels[2]}</span></dt><dd>{activity.language[locale]}</dd></div>
                      <div><dt><Clock3 aria-hidden="true" /><span className="visually-hidden">{locale === "en" ? "Duration" : "अवधि"}</span></dt><dd>{activity.duration[locale]} · {activity.seats[locale]}</dd></div>
                    </dl>
                  </div>
                  <div className="activity-listing-action">
                    <p><span>{text.referenceFee}</span><strong>{activity.referenceFee}</strong><small>{text.demoNoCharge}</small></p>
                    <button
                      className={booked ? "secondary-button" : "primary-button"}
                      type="button"
                      onClick={() => book(activity.id)}
                      disabled={booked}
                      aria-label={booked ? text.booked(activity.title[locale]) : text.book(activity.title[locale])}
                    >
                      {booked ? locale === "en" ? "Booked" : "बुक हो गई" : locale === "en" ? "Book demo seat" : "डेमो सीट बुक करें"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </section>
  );
}
