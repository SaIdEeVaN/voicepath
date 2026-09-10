/**
 * User-facing copy in Tamil, Hindi and English.
 *
 * The Tamil and Hindi are not translations of the English -- they are written
 * in each language, which is why the Tamil line about privacy is shorter than
 * the English one. Translated-sounding copy is exactly what a beneficiary
 * recognises as a government portal, and PRD section 2 rules that out.
 *
 * No bureaucratic vocabulary reaches this file: no "NSQF Level 3", no "match
 * vector score", no "eligibility criteria". If a string here needs a glossary,
 * it is the wrong string.
 */

import type { Language } from "./types";

export interface Copy {
  /* Landing */
  statement: string;
  speakHint: string;
  notKept: string;
  /* Speak */
  listening: string;
  stopHint: string;
  startOver: string;
  micDenied: string;
  micUnsupported: string;
  serverUnreachable: string;
  serverWaking: string;
  /* Understanding */
  weHeard: string;
  weHeardSub: string;
  confirm: string;
  addMore: string;
  youSaid: string;
  notSure: string;
  edit: string;
  remove: string;
  save: string;
  nothingHeard: string;
  nothingHeardSub: string;
  /* Disambiguation */
  whichOne: string;
  resay: string;
  skip: string;
  /* Passport */
  passportLabel: string;
  passportTitle: string;
  playEvidence: string;
  retainCopy: string;
  retainOn: string;
  retainOff: string;
  statYears: string;
  statSkills: string;
  statLanguages: string;
  /* Opportunities */
  matchesTitle: string;
  matchesSub: string;
  matchWord: string;
  noMatches: string;
  back: string;
  apply: string;
  opportunityTypes: Record<string, string>;
  applyHow: string;
  applyRefLabel: string;
  applyNote: string;
  viewPassport: string;
  fromRecord: string;
  /* Score bars */
  barSkills: string;
  barExperience: string;
  barRequirements: string;
  barDistance: string;
  /* Ask */
  askTitle: string;
  askLabel: string;
  listeningLabel: string;
  askPlaceholder: string;
  send: string;
  /* System */
  thinking: string;
  loading: string;
  retry: string;
  offlineNotice: string;
}

const en: Copy = {
  statement: "Your experience has a voice.",
  speakHint: "Press and tell me about the work you have done.",
  notKept: "Your voice is not saved. Only what you said in words is kept.",
  listening: "Listening",
  stopHint: "Press to finish",
  startOver: "Start again",
  micDenied: "I cannot hear you. Allow the microphone in your browser and try again.",
  micUnsupported: "This browser cannot record. Try Chrome, or type what you do instead.",
  serverUnreachable:
    "VoicePath cannot reach its server, so the microphone is off. Start the backend and reload.",
  serverWaking: "Starting up. This takes about a minute the first time.",
  weHeard: "This is what I understood.",
  weHeardSub:
    "Change anything that is wrong. Every line shows the words you actually said.",
  confirm: "This is right",
  addMore: "Say something more",
  youSaid: "YOU SAID",
  notSure: "I am not fully sure about this one",
  edit: "Edit",
  remove: "Remove",
  save: "Save",
  nothingHeard: "I did not catch any work you have done.",
  nothingHeardSub: "Tell me again, and say the kind of work in your own words.",
  whichOne: "Which one did you mean?",
  resay: "Say it again",
  skip: "Leave it out",
  passportLabel: "SKILL PASSPORT",
  passportTitle: "Your work, in your own words.",
  playEvidence: "Play",
  retainCopy:
    "Keep my voice clips so employers can hear me say it. You can turn this off any time.",
  retainOn: "KEEPING CLIPS",
  retainOff: "NOT KEEPING",
  statYears: "years of work",
  statSkills: "kinds of work",
  statLanguages: "language",
  matchesTitle: "Places your work fits.",
  matchesSub: "Closest first. Each one says why, using only what you told me.",
  matchWord: "fit for your work",
  noMatches: "Nothing here fits your work yet. Tell me more about what you do.",
  back: "Back",
  apply: "I want this",
  opportunityTypes: {
    "Full-time": "Full-time",
    "Part-time": "Part-time",
    Training: "Training",
    Apprenticeship: "Apprenticeship",
    "Self-employment support": "Self-employment support",
  },
  applyHow: "How to ask for this work",
  applyRefLabel: "Say this number at the office",
  applyNote:
    "VoicePath does not send the application for you. Say this number where you go, and they will find this same work.",
  viewPassport: "My passport",
  fromRecord: "Taken only from the record. Nothing beyond it has been added.",
  barSkills: "Your skills",
  barExperience: "Your experience",
  barRequirements: "What they need",
  barDistance: "Distance from you",
  askTitle: "Ask about this",
  askLabel: "Ask a question",
  listeningLabel: "Listening…",
  askPlaceholder: "Type your question",
  send: "Ask",
  thinking: "Looking…",
  loading: "One moment",
  retry: "Try again",
  offlineNotice:
    "Running without the speech and language services, so I am reading only what you name directly.",
};

const ta: Copy = {
  statement: "உங்கள் அனுபவத்திற்கு ஒரு குரல் இருக்கிறது.",
  speakHint: "அழுத்தி, நீங்கள் செய்த வேலையைப் பற்றி சொல்லுங்கள்.",
  notKept: "உங்கள் குரல் சேமிக்கப்படுவதில்லை. நீங்கள் சொன்ன வார்த்தைகள் மட்டுமே வைக்கப்படும்.",
  listening: "கேட்டுக்கொண்டிருக்கிறேன்",
  stopHint: "முடிக்க அழுத்துங்கள்",
  startOver: "மீண்டும் தொடங்கு",
  micDenied:
    "உங்கள் குரல் கேட்கவில்லை. உலாவியில் மைக்ரோஃபோனை அனுமதித்து மீண்டும் முயலுங்கள்.",
  micUnsupported:
    "இந்த உலாவியில் பதிவு செய்ய முடியாது. Chrome பயன்படுத்துங்கள், அல்லது தட்டச்சு செய்யுங்கள்.",
  serverUnreachable:
    "VoicePath சேவையகத்தை அடைய முடியவில்லை, அதனால் மைக்ரோஃபோன் இயங்கவில்லை. சேவையகத்தைத் தொடங்கி மீண்டும் ஏற்றுங்கள்.",
  serverWaking: "தொடங்குகிறது. முதல் முறை ஒரு நிமிடம் ஆகும்.",
  weHeard: "நான் புரிந்துகொண்டது இதுதான்.",
  weHeardSub:
    "தவறு இருந்தால் மாற்றுங்கள். ஒவ்வொரு வரியிலும் நீங்கள் சொன்ன வார்த்தைகள் இருக்கும்.",
  confirm: "இது சரி",
  addMore: "இன்னும் சொல்லுங்கள்",
  youSaid: "நீங்கள் சொன்னது",
  notSure: "இதில் எனக்கு முழு உறுதி இல்லை",
  edit: "மாற்று",
  remove: "நீக்கு",
  save: "சேமி",
  nothingHeard: "நீங்கள் செய்த வேலை எதுவும் எனக்குப் புரியவில்லை.",
  nothingHeardSub: "மீண்டும் சொல்லுங்கள், எந்த வேலை என்பதை உங்கள் வார்த்தையில் சொல்லுங்கள்.",
  whichOne: "எதைச் சொன்னீர்கள்?",
  resay: "மீண்டும் சொல்லுங்கள்",
  skip: "இதை விட்டுவிடு",
  passportLabel: "திறன் பாஸ்போர்ட்",
  passportTitle: "உங்கள் வேலை, உங்கள் வார்த்தைகளில்.",
  playEvidence: "கேளுங்கள்",
  retainCopy:
    "என் குரல் பதிவுகளை வைத்துக்கொள்ளுங்கள் — வேலை தருபவர்கள் நேரடியாகக் கேட்கலாம். எப்போது வேண்டுமானாலும் நிறுத்தலாம்.",
  retainOn: "வைக்கப்படுகிறது",
  retainOff: "வைக்கப்படவில்லை",
  statYears: "வருட வேலை",
  statSkills: "வகை வேலை",
  statLanguages: "மொழி",
  matchesTitle: "உங்கள் வேலைக்குப் பொருந்தும் இடங்கள்.",
  matchesSub: "மிக அருகில் இருப்பது முதலில். நீங்கள் சொன்னதை வைத்து மட்டுமே காரணம் சொல்கிறேன்.",
  matchWord: "உங்கள் வேலைக்குப் பொருத்தம்",
  noMatches: "உங்கள் வேலைக்கு இங்கு இன்னும் எதுவும் பொருந்தவில்லை. இன்னும் சொல்லுங்கள்.",
  back: "பின்னால்",
  apply: "இது வேண்டும்",
  opportunityTypes: {
    "Full-time": "முழு நேரம்",
    "Part-time": "பகுதி நேரம்",
    Training: "பயிற்சி",
    Apprenticeship: "பயிற்சிப் பணி",
    "Self-employment support": "சொந்தத் தொழில் உதவி",
  },
  applyHow: "இந்த வேலையை எப்படிக் கேட்பது",
  applyRefLabel: "அலுவலகத்தில் இந்த எண்ணைச் சொல்லுங்கள்",
  applyNote:
    "VoicePath உங்களுக்காக விண்ணப்பத்தை அனுப்பாது. நீங்கள் போகும் இடத்தில் இந்த எண்ணைச் சொன்னால், இதே வேலையை அவர்கள் கண்டுபிடிப்பார்கள்.",
  viewPassport: "என் பாஸ்போர்ட்",
  fromRecord: "பதிவில் உள்ளது மட்டுமே. அதற்கு மேல் எதுவும் சேர்க்கப்படவில்லை.",
  barSkills: "உங்கள் திறன்கள்",
  barExperience: "உங்கள் அனுபவம்",
  barRequirements: "அவர்கள் கேட்பது",
  barDistance: "உங்கள் ஊரிலிருந்து",
  askTitle: "இதைப் பற்றிக் கேளுங்கள்",
  askLabel: "ஒரு கேள்வி கேளுங்கள்",
  listeningLabel: "கேட்கிறேன்…",
  askPlaceholder: "உங்கள் கேள்வியை எழுதுங்கள்",
  send: "கேளுங்கள்",
  thinking: "பார்க்கிறேன்…",
  loading: "ஒரு நிமிடம்",
  retry: "மீண்டும் முயலுங்கள்",
  offlineNotice:
    "பேச்சு மற்றும் மொழி சேவைகள் இல்லாமல் இயங்குகிறது, நீங்கள் நேரடியாகச் சொன்னதை மட்டுமே படிக்கிறேன்.",
};

const hi: Copy = {
  statement: "आपके अनुभव की एक आवाज़ है।",
  speakHint: "दबाइए और अपने किए हुए काम के बारे में बताइए।",
  notKept: "आपकी आवाज़ सहेजी नहीं जाती। सिर्फ़ आपके कहे शब्द रखे जाते हैं।",
  listening: "सुन रहा हूँ",
  stopHint: "खत्म करने के लिए दबाइए",
  startOver: "फिर से शुरू करें",
  micDenied: "आपकी आवाज़ नहीं आ रही। ब्राउज़र में माइक की अनुमति दीजिए और फिर कोशिश कीजिए।",
  micUnsupported: "यह ब्राउज़र रिकॉर्ड नहीं कर सकता। Chrome आज़माइए, या टाइप कीजिए।",
  serverUnreachable:
    "VoicePath अपने सर्वर तक नहीं पहुँच पा रहा, इसलिए माइक बंद है। बैकएंड चालू कीजिए और पेज दोबारा खोलिए।",
  serverWaking: "शुरू हो रहा है। पहली बार में करीब एक मिनट लगता है।",
  weHeard: "मैंने यही समझा।",
  weHeardSub: "जो गलत है उसे बदल दीजिए। हर पंक्ति में आपके ही कहे शब्द दिख रहे हैं।",
  confirm: "यह सही है",
  addMore: "कुछ और बताइए",
  youSaid: "आपने कहा",
  notSure: "इस बारे में मुझे पूरा भरोसा नहीं है",
  edit: "बदलें",
  remove: "हटाएँ",
  save: "सहेजें",
  nothingHeard: "आपने जो काम किया, वह मुझे समझ नहीं आया।",
  nothingHeardSub: "फिर से बताइए, और किस तरह का काम है वह अपने शब्दों में कहिए।",
  whichOne: "आपका मतलब किससे था?",
  resay: "फिर से बोलिए",
  skip: "इसे छोड़ दीजिए",
  passportLabel: "स्किल पासपोर्ट",
  passportTitle: "आपका काम, आपके ही शब्दों में।",
  playEvidence: "सुनिए",
  retainCopy:
    "मेरी आवाज़ के हिस्से रखिए ताकि काम देने वाले मुझे सुन सकें। इसे कभी भी बंद कर सकते हैं।",
  retainOn: "रखे जा रहे हैं",
  retainOff: "नहीं रखे जा रहे",
  statYears: "साल का काम",
  statSkills: "तरह के काम",
  statLanguages: "भाषा",
  matchesTitle: "जगहें जहाँ आपका काम बैठता है।",
  matchesSub: "सबसे नज़दीक पहले। हर एक का कारण आपके ही कहे पर आधारित है।",
  matchWord: "आपके काम से मेल",
  noMatches: "अभी यहाँ आपके काम से कुछ नहीं मिलता। अपने काम के बारे में और बताइए।",
  back: "वापस",
  apply: "मुझे यह चाहिए",
  opportunityTypes: {
    "Full-time": "पूरा समय",
    "Part-time": "आंशिक समय",
    Training: "प्रशिक्षण",
    Apprenticeship: "शिक्षुता",
    "Self-employment support": "स्वरोज़गार सहायता",
  },
  applyHow: "यह काम कैसे माँगें",
  applyRefLabel: "दफ़्तर में यह नंबर बताइए",
  applyNote:
    "VoicePath आपकी ओर से आवेदन नहीं भेजता। जहाँ जाएँ वहाँ यह नंबर बता दीजिए, वे यही काम ढूँढ़ लेंगे।",
  viewPassport: "मेरा पासपोर्ट",
  fromRecord: "सिर्फ़ रिकॉर्ड में जो है वही। उसके बाहर कुछ नहीं जोड़ा गया।",
  barSkills: "आपके हुनर",
  barExperience: "आपका अनुभव",
  barRequirements: "उनकी शर्तें",
  barDistance: "आपसे दूरी",
  askTitle: "इसके बारे में पूछिए",
  askLabel: "सवाल पूछिए",
  listeningLabel: "सुन रहा हूँ…",
  askPlaceholder: "अपना सवाल लिखिए",
  send: "पूछें",
  thinking: "देख रहा हूँ…",
  loading: "एक पल",
  retry: "फिर कोशिश करें",
  offlineNotice:
    "भाषा और आवाज़ की सेवाओं के बिना चल रहा है, इसलिए सिर्फ़ वही पढ़ रहा हूँ जो आपने सीधे कहा।",
};

export const COPY: Record<Language, Copy> = { en, ta, hi };

export const LANGUAGES: { code: Language; label: string; native: string }[] = [
  { code: "ta", label: "TA", native: "தமிழ்" },
  { code: "hi", label: "HI", native: "हिन्दी" },
  { code: "en", label: "EN", native: "English" },
];

export function copyFor(language: Language): Copy {
  return COPY[language] ?? en;
}

/**
 * The label for a skill in the reader's language.
 *
 * Falls back to English, then to whatever the person actually said. A skill
 * always has a name to show -- an unnormalized one still has their words.
 */
export function skillLabel(
  skill: {
    display_names?: Record<string, string>;
    normalized_name?: string | null;
    name?: string;
    raw_name?: string;
  },
  language: Language,
): string {
  const names = skill.display_names ?? {};
  return (
    names[language] ||
    names.en ||
    skill.normalized_name ||
    skill.name ||
    skill.raw_name ||
    ""
  );
}

/** BCP-47 tag for `lang` attributes and the Web Speech API. */
export function localeFor(language: Language): string {
  return { ta: "ta-IN", hi: "hi-IN", en: "en-IN" }[language];
}

/** Localised label for an opportunity type. Unknown values pass through. */
export function typeLabel(type: string, language: Language): string {
  return copyFor(language).opportunityTypes[type] ?? type;
}
