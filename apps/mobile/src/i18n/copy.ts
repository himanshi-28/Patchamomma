import type { Destination, Locale } from "@/features/auth/types";

export type AppCopy = {
  brand: string;
  languageAction: string;
  welcome: string;
  welcomeNote: string;
  emailLabel: string;
  emailPlaceholder: string;
  emailAction: string;
  googleAction: string;
  or: string;
  demoLabel: string;
  demoNote: string;
  demoAction: string;
  invalidEmail: string;
  emailSetup: string;
  googleSetup: string;
  helpTrigger: string;
  helpTitle: string;
  close: string;
  helpTopics: [string, string, string];
  helpReplies: [string, string, string];
  greeting: string;
  today: string;
  circle: string;
  mentors: string;
  nextStep: string;
  nextChapter: string;
  nextDescription: string;
  chooseHobby: string;
  howItWorks: string;
  howLink: string;
  steps: Array<{ title: string; description: string }>;
  empty: Record<Exclude<Destination, "today">, { title: string; message: string; note: string }>;
};

const english: AppCopy = {
  brand: "SakhiCircle",
  languageAction: "हिंदी में देखें",
  welcome: "Welcome to SakhiCircle",
  welcomeNote: "Sign in securely. No password to remember.",
  emailLabel: "Email address",
  emailPlaceholder: "you@example.com",
  emailAction: "Send sign-in link",
  googleAction: "Continue with Google",
  or: "or",
  demoLabel: "Local demonstration",
  demoNote: "Uses synthetic data and no cloud account.",
  demoAction: "Continue as Meera",
  invalidEmail: "Enter a valid email address.",
  emailSetup: "Email sign-in is not configured yet.",
  googleSetup: "Google sign-in is not configured yet.",
  helpTrigger: "Hi, let me help you",
  helpTitle: "Sakhi help",
  close: "Close help",
  helpTopics: ["Signing in", "Finding a hobby", "Using voice"],
  helpReplies: [
    "Choose email, Google, or the local demo. You will never be asked for a password here.",
    "Start with something you miss, something useful, or something you have always wanted to try.",
    "Every voice action has a text option. You stay in control and can review before anything is saved.",
  ],
  greeting: "Namaste, Meera",
  today: "Today",
  circle: "My Circle",
  mentors: "Mentors",
  nextStep: "Your next step",
  nextChapter: "Your next chapter starts here",
  nextDescription: "Tell us what you have always wanted to learn. We will shape it around your time, pace, and comfort.",
  chooseHobby: "Choose my first hobby",
  howItWorks: "How SakhiCircle works",
  howLink: "How this works",
  steps: [
    { title: "Share your wish", description: "Speak or type what you want to learn." },
    { title: "Review your plan", description: "Nothing is saved until you confirm it." },
    { title: "Meet your people", description: "See why each partner, circle, or mentor fits." },
  ],
  empty: {
    circle: {
      title: "My Circle",
      message: "Your circle is ready when you are.",
      note: "People you choose to learn and share with will appear here.",
    },
    mentors: {
      title: "Mentors",
      message: "Find guidance at your pace.",
      note: "Your confirmed mentor matches will appear here with clear reasons.",
    },
  },
};

const hindi: AppCopy = {
  brand: "SakhiCircle",
  languageAction: "View in English",
  welcome: "SakhiCircle में आपका स्वागत है",
  welcomeNote: "सुरक्षित रूप से साइन इन करें। पासवर्ड याद रखने की ज़रूरत नहीं।",
  emailLabel: "ईमेल पता",
  emailPlaceholder: "you@example.com",
  emailAction: "साइन-इन लिंक भेजें",
  googleAction: "Google से जारी रखें",
  or: "या",
  demoLabel: "स्थानीय डेमो",
  demoNote: "इसमें नमूना डेटा है और कोई क्लाउड खाता नहीं है।",
  demoAction: "मीरा के रूप में जारी रखें",
  invalidEmail: "सही ईमेल पता दर्ज करें।",
  emailSetup: "ईमेल साइन-इन अभी जोड़ा नहीं गया है।",
  googleSetup: "Google साइन-इन अभी जोड़ा नहीं गया है।",
  helpTrigger: "नमस्ते, मैं आपकी मदद करूँ?",
  helpTitle: "सखी की मदद",
  close: "मदद बंद करें",
  helpTopics: ["साइन इन करना", "शौक ढूँढना", "आवाज़ का उपयोग"],
  helpReplies: [
    "ईमेल, Google या स्थानीय डेमो चुनें। यहाँ आपसे कभी पासवर्ड नहीं माँगा जाएगा।",
    "उस चीज़ से शुरू करें जिसकी आपको याद आती है, जो उपयोगी है, या जिसे आप हमेशा सीखना चाहती थीं।",
    "हर आवाज़ वाले विकल्प का लिखित विकल्प भी है। कुछ भी सहेजने से पहले आप उसे जाँच सकती हैं।",
  ],
  greeting: "नमस्ते, मीरा",
  today: "आज",
  circle: "मेरा समूह",
  mentors: "मार्गदर्शक",
  nextStep: "आपका अगला कदम",
  nextChapter: "आपकी अगली शुरुआत यहाँ से होती है",
  nextDescription: "हमें बताएँ कि आप हमेशा से क्या सीखना चाहती थीं। हम इसे आपके समय, गति और सुविधा के अनुसार बनाएँगे।",
  chooseHobby: "मेरा पहला शौक चुनें",
  howItWorks: "SakhiCircle कैसे काम करता है",
  howLink: "यह कैसे काम करता है",
  steps: [
    { title: "अपनी इच्छा बताएँ", description: "जो सीखना चाहती हैं, उसे बोलें या लिखें।" },
    { title: "अपनी योजना देखें", description: "आपकी पुष्टि से पहले कुछ भी सहेजा नहीं जाएगा।" },
    { title: "अपने लोगों से मिलें", description: "जानें कि हर साथी, समूह या मार्गदर्शक आपके लिए क्यों सही है।" },
  ],
  empty: {
    circle: {
      title: "मेरा समूह",
      message: "जब आप तैयार हों, आपका समूह भी तैयार है।",
      note: "जिन लोगों के साथ आप सीखना और साझा करना चुनेंगी, वे यहाँ दिखेंगे।",
    },
    mentors: {
      title: "मार्गदर्शक",
      message: "अपनी गति से सही मार्गदर्शन पाएँ।",
      note: "आपके चुने हुए मार्गदर्शक और उनके मिलने के कारण यहाँ दिखेंगे।",
    },
  },
};

export const copyByLocale: Record<Locale, AppCopy> = {
  en: english,
  hi: hindi,
};
