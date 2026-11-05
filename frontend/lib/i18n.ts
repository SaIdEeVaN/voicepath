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

import type { Language, NearbyCategory } from "./types";

export interface Copy {
  /* Landing */
  statement: string;
  speakHint: string;
  orType: string;
  typePlaceholder: string;
  typeSubmit: string;
  notKept: string;
  /**
   * What this is, under the hero.
   *
   * Three steps, because it is genuinely a sequence: speak, check, see. The
   * closing note says what VoicePath does not do, which matters more here than
   * anything it does -- people arrive at a government-looking site expecting
   * it to file something on their behalf.
   */
  aboutTitle: string;
  aboutSteps: { title: string; body: string }[];
  aboutNote: string;
  /* Navbar */
  navHome: string;
  navAbout: string;
  /**
   * The four steps of the journey, shown down the left of a wide screen.
   *
   * People lose track of where they are in this flow -- it is four screens
   * with no breadcrumb, and the person using it may not read the headings.
   */
  flowSteps: string[];
  flowHere: string;
  /** Link on a citation, to the government's own page. */
  readOnGovPage: string;
  /**
   * The About page.
   *
   * Only what is true of the product. No claims about who built it, because
   * inventing a team would be the one kind of fiction this whole codebase is
   * built to refuse.
   */
  aboutPageTitle: string;
  aboutPageLede: string;
  aboutPageSections: { heading: string; body: string }[];
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
  /**
   * Adding a skill by typing it, on the understanding screen.
   *
   * The mic stays first there, as on the landing page -- it asks least of
   * someone who cannot comfortably type. But every way of adding a skill
   * used to go back through the microphone, which leaves anyone in a noisy
   * room, or whose speech was misheard twice, with nothing else to try.
   */
  addByTyping: string;
  addSkillPlaceholder: string;
  addSkillSubmit: string;
  /** Typed text that was neither work nor a question. */
  notWork: string;
  /**
   * The experience read from what the person said, on the understanding
   * screen. `{years}` is replaced with the number.
   *
   * It is a quarter of a match score and was shown nowhere the person
   * could check it -- only on the passport, after the matching is done.
   */
  experienceHeard: string;
  experienceNotHeard: string;
  experienceChange: string;
  experienceAdd: string;
  experienceLabel: string;
  experienceSave: string;
  experienceCancel: string;
  experienceRematch: string;
  experienceInvalid: string;
  youSaid: string;
  notSure: string;
  edit: string;
  remove: string;
  save: string;
  nothingHeard: string;
  nothingHeardSub: string;
  answeredQuestion: string;
  /* Shown when someone says they, or a person near them, is in danger. */
  safetyTitle: string;
  safety112: string;
  safety181: string;
  safety1098: string;
  safety14416: string;
  safetyCannotSend: string;
  askedNotTold: string;
  /* Disambiguation */
  whichOne: string;
  resay: string;
  skip: string;
  /* Passport */
  passportLabel: string;
  passportTitle: string;
  /** The button that opens the browser's print dialog for the passport. */
  passportPrint: string;
  /** Under the button: how to keep a copy without a printer. */
  passportPrintHint: string;
  /** Printed at the foot of the page. `{date}` is replaced with today. */
  passportRecordedOn: string;
  /** Printed at the foot of the page: what this record is, and is not. */
  passportNotCertificate: string;
  /** On the passport: what happened to their recording. */
  passportVoiceNote: string;
  statYears: string;
  statSkills: string;
  statLanguages: string;
  /* Schemes */
  matchesTitle: string;
  matchesSub: string;
  matchWord: string;
  noMatches: string;
  back: string;
  apply: string;
  confidenceAccepted: string;
  confidenceAsking: string;
  confidenceThreshold: string;
  weightsLabel: string;
  schemeTypes: Record<string, string>;
  /** Taxonomy categories. A skill card shows one next to its code. */
  skillCategories: Record<string, string>;
  /** Pay, when only one end of the range is known. */
  payUpTo: string;
  payFrom: string;
  applyHow: string;
  applyRefLabel: string;
  applyNote: string;
  officialPage: string;
  viewPassport: string;
  fromRecord: string;
  /*
   * Facts under a scheme. These were English literals on the detail screen,
   * so a Tamil page said "Pay" and "2 years" in the middle of Tamil prose.
   */
  factPay: string;
  factExperience: string;
  factCertificates: string;
  /** `{years}` is replaced with the number. */
  yearsCount: string;
  /** Accessible name for the language switch. */
  languageSwitch: string;
  /*
   * Near you: the map.
   *
   * Two kinds of thing share it. Openings come from the catalogue and are
   * pinned at their town, because the record has no street address -- the
   * screen says so rather than letting a pin imply a doorstep. Support
   * offices come from OpenStreetMap, which is community-kept and can be out
   * of date; the screen says that too.
   */
  navNearby: string;
  nearbyTitle: string;
  nearbySub: string;
  nearbyUseLocation: string;
  nearbyLocating: string;
  nearbyGpsNote: string;
  nearbyLocationDenied: string;
  nearbyLocationFailed: string;
  nearbyCentreGps: string;
  /** `{place}` is replaced with the town the person said. */
  nearbyCentrePlace: string;
  /** `{place}` is replaced with the town the person picked. */
  nearbyCentreChosen: string;
  nearbyCentreDefault: string;
  nearbyChooseTown: string;
  nearbyWithin: string;
  nearbyYourMatches: string;
  nearbyAllOpenings: string;
  nearbyOpeningsHeading: string;
  nearbySupportHeading: string;
  nearbySupportNote: string;
  nearbySupportUnavailable: string;
  nearbySupportNone: string;
  nearbySupportOffline: string;
  nearbyApprox: string;
  /** `{km}` is replaced with the distance. */
  nearbyKm: string;
  nearbyYou: string;
  nearbyDirections: string;
  nearbyShowOnMap: string;
  /** `{count}` is replaced with how many openings share one town. */
  nearbyCount: string;
  nearbyCategories: Record<NearbyCategory, string>;
  nearbyOpenings: string;
  nearbyUnplaced: string;
  nearbyNationwide: string;
  nearbyNationwideNote: string;
  /** A national scheme's location, as the catalogue writes "All India". */
  allIndia: string;
  /** Scheme list filters (components/SchemeFilters.tsx). */
  filterKind: string;
  filterWhere: string;
  filterSkill: string;
  filterAll: string;
  filterJobs: string;
  filterTraining: string;
  /** Self-employment support: loans, subsidies, toolkits for one's own work. */
  filterOwnWork: string;
  /** Listings tied to a town, as opposed to open anywhere in India. */
  filterLocal: string;
  filterNone: string;
  filterClear: string;
  nearbyStraightLine: string;
  nearbyViewOnOsm: string;
  /** `{date}` is replaced with the day the bundled office list was fetched. */
  nearbySupportAsOf: string;
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
  /**
   * The last-resort failure sentence.
   *
   * Every screen had this hardcoded in English, so a Tamil speaker whose
   * request failed was handed an English sentence at the one moment they
   * were already confused.
   */
  somethingWentWrong: string;
  offlineNotice: string;
  llmBusyNotice: string;
  llmBackAround: string;
  /**
   * The database is configured but did not answer, so the server is running
   * on memory. Matching still works; what is said may not be kept.
   */
  storageOfflineNotice: string;
}

const en: Copy = {
  statement: "Your experience has a voice.",
  speakHint: "Press and tell me about the work you have done.",
  orType: "or type it",
  typePlaceholder: "I repair two-wheelers",
  typeSubmit: "Find work",
  notKept: "Your voice is not saved. Only what you said in words is kept.",
  aboutTitle: "What happens here",
  aboutSteps: [
    {
      title: "You speak",
      body:
        "Press the microphone and say the work you have done, in your own words. There is no form to fill.",
    },
    {
      title: "You check what I understood",
      body:
        "Every skill is shown with the words you said that produced it. Change or remove anything that is wrong.",
    },
    {
      title: "You see what fits",
      body:
        "Work, training and government schemes near you, each with the reason it matched what you said.",
    },
  ],
  aboutNote:
    "VoicePath does not apply for anything on your behalf. It tells you what exists, and what to say when you go.",
  navHome: "Home",
  navAbout: "About",
  flowSteps: [
    "Speak",
    "What I heard",
    "Your passport",
    "What fits",
    "The one you pick",
  ],
  flowHere: "you are here",
  readOnGovPage: "Read this on the government page",
  aboutPageTitle: "About VoicePath",
  aboutPageLede:
    "A way to find government work, training and schemes by saying what you have done — out loud, in your own language, without filling a form.",
  aboutPageSections: [
    {
      heading: "Who this is for",
      body:
        "People whose skill is real but undocumented. A mechanic who learned in a shed, a tailor taught by her mother, a welder with twenty years and no certificate. The work exists; the paperwork proving it usually does not, and most government portals ask for the paperwork first.",
    },
    {
      heading: "How it decides",
      body:
        "Your words are turned into skills, and every skill is shown back to you with the words that produced it, so you can correct anything that is wrong. Those skills are then scored against each listing — half on the work itself, and the rest on experience, requirements and distance. The score is arithmetic, not an opinion, and the same answer comes back every time.",
    },
    {
      heading: "What it will not do",
      body:
        "It does not apply for anything on your behalf. It does not say you are eligible — only what a listing asks for. It will not tell you something it cannot trace to your own words or to a published government document, and when it does not know, it says so instead of guessing.",
    },
    {
      heading: "Your voice",
      body:
        "Your recording is turned into text and then discarded. It is not kept unless you ask for it to be kept, and you can change that at any time on your passport. What is stored is the words, not the voice.",
    },
    {
      heading: "Where the information comes from",
      body:
        "Published government scheme documents and official government pages. Every answer about a scheme shows the document it came from, so you can check it yourself or quote it at an office. It is free to use, and always will be.",
    },
  ],
  listening: "Listening",
  stopHint: "Press to finish",
  startOver: "Start again",
  micDenied: "I cannot hear you. Allow the microphone in your browser and try again.",
  micUnsupported: "This browser cannot record. Try Chrome, or type what you do instead.",
  serverUnreachable:
    "VoicePath cannot reach its server right now, so the microphone is off. I am still trying — this page will start working by itself when it answers.",
  serverWaking: "Starting up. This takes about a minute the first time.",
  weHeard: "This is what I understood.",
  weHeardSub:
    "Change anything that is wrong. Every line shows the words you actually said.",
  confirm: "This is right",
  addMore: "Say something more",
  addByTyping: "Or type the work you do",
  addSkillPlaceholder: "carpentry",
  addSkillSubmit: "Add",
  notWork:
    "That is not work I can use. Tell me the kind of work you do — like carpentry, welding or driving — or ask about a scheme.",
  experienceHeard: "{years} years of work",
  experienceNotHeard: "You did not say how long you have done this work.",
  experienceChange: "Not right? Change it",
  experienceAdd: "Add it",
  experienceLabel: "How many years have you done this work?",
  experienceSave: "Save",
  experienceCancel: "Cancel",
  experienceRematch: "Your schemes will be matched again with this number.",
  experienceInvalid: "Enter a number of years from 0 to 70.",
  youSaid: "YOU SAID",
  notSure: "I am not fully sure about this one",
  edit: "Edit",
  remove: "Remove",
  save: "Save",
  nothingHeard: "I did not catch any work you have done.",
  nothingHeardSub: "Tell me again, and say the kind of work in your own words.",
  answeredQuestion: "You asked a question, so here is the answer.",
  safetyTitle: "If you or someone near you is in danger, call now. It is free.",
  safety112: "Emergency: police, ambulance, fire. Any language, day and night.",
  safety181: "Women's helpline",
  safety1098: "For a child",
  safety14416: "If you are thinking of ending your life",
  safetyCannotSend: "VoicePath cannot send help itself. These numbers can.",
  askedNotTold: "To find work for you, tell me what you have done instead.",
  whichOne: "Which one did you mean?",
  resay: "Say it again",
  skip: "Leave it out",
  passportLabel: "SKILL PASSPORT",
  passportTitle: "Your work, in your own words.",
  passportPrint: "Print or save as PDF",
  passportPrintHint: "To keep a copy on your phone, choose \u201cSave as PDF\u201d as the printer.",
  passportRecordedOn: "Recorded with VoicePath on {date}.",
  passportNotCertificate:
    "Each line is what the person said about their work, in their own words. This is not a certificate or a government document.",
  passportVoiceNote:
    "Your recording was used only to write down what you said. It is not kept, and no one else has heard it.",
  statYears: "years of work",
  statSkills: "kinds of work",
  statLanguages: "language",
  matchesTitle: "Places your work fits.",
  matchesSub: "Closest first. Each one says why, using only what you told me.",
  matchWord: "fit for your work",
  noMatches: "Nothing here fits your work yet. Tell me more about what you do.",
  back: "Back",
  apply: "I want this",
  confidenceAccepted: "accepted",
  confidenceAsking: "asking you",
  confidenceThreshold: "needs",
  weightsLabel: "Weights: skill 50% · experience 25% · eligibility 15% · place 10%",
  schemeTypes: {
    "Full-time": "Full-time",
    "Part-time": "Part-time",
    Training: "Training",
    Apprenticeship: "Apprenticeship",
    "Self-employment support": "Self-employment support",
  },
  skillCategories: {
    Agriculture: "Agriculture",
    "Traditional Crafts": "Traditional crafts",
    Commerce: "Commerce",
    Construction: "Construction",
    Electrical: "Electrical",
    Electronics: "Electronics",
    Hospitality: "Hospitality",
    Mechanical: "Mechanical",
    Metalwork: "Metalwork",
    Service: "Service",
    Textile: "Textile",
    Transport: "Transport",
  },
  payUpTo: "up to ₹{amount}",
  payFrom: "from ₹{amount}",
  applyHow: "How to ask for this work",
  applyRefLabel: "Say this number at the office",
  applyNote:
    "VoicePath does not send the application for you. Say this number where you go, and they will find this same work.",
  officialPage: "Read this on the government's own page",
  viewPassport: "My passport",
  fromRecord: "Taken only from the record. Nothing beyond it has been added.",
  factPay: "Pay",
  factExperience: "Experience asked for",
  factCertificates: "Certificates required",
  yearsCount: "{years} years",
  languageSwitch: "Language",
  navNearby: "Near you",
  nearbyTitle: "What is near you.",
  nearbySub:
    "The openings that fit your work, and the offices where you can ask about them.",
  nearbyUseLocation: "Use my location",
  nearbyLocating: "Finding where you are…",
  nearbyGpsNote:
    "Your exact spot is not sent — only the area, to about a kilometre, for this one search. Nothing is saved.",
  nearbyLocationDenied: "Location was not allowed, so the map stays where it was.",
  nearbyLocationFailed: "Your location could not be found, so the map stays where it was.",
  nearbyCentreGps: "Around where you are now",
  nearbyCentrePlace: "Around {place}, the place you told me",
  nearbyCentreChosen: "Around {place}",
  nearbyCentreDefault:
    "I do not know where you are, so this shows where the openings are. Choose your town, or use your location.",
  nearbyChooseTown: "Choose a town",
  nearbyWithin: "Within",
  nearbyYourMatches: "Your matches",
  nearbyAllOpenings: "All openings",
  nearbyOpeningsHeading: "Openings, nearest first",
  nearbySupportHeading: "Places that can help",
  nearbySupportNote:
    "From OpenStreetMap. Check the timings before you go — this list can be out of date.",
  nearbySupportUnavailable:
    "The nearby offices could not be loaded just now. The openings are still shown.",
  nearbySupportNone: "No offices of this kind are marked on the map near here.",
  nearbySupportOffline: "Nearby offices are not looked up on this server.",
  nearbyApprox:
    "Marked at the town centre — the record does not give a street address.",
  nearbyKm: "{km} km",
  nearbyYou: "You",
  nearbyDirections: "Directions",
  nearbyShowOnMap: "See on a map",
  nearbyCount: "{count} here",
  nearbyCategories: {
    training: "Training centres and ITIs",
    employment: "Employment offices",
    government: "Government offices",
    bank: "Banks",
  },
  nearbyOpenings: "Openings",
  nearbyUnplaced: "Not on the map yet — the map does not know its town.",
  nearbyNationwide: "Open anywhere in India",
  nearbyNationwideNote:
    "National schemes, not tied to one town. Open one to see who it is for and how to apply.",
  allIndia: "All India",
  filterKind: "Kind",
  filterWhere: "Where",
  filterSkill: "Fits my",
  filterAll: "All",
  filterJobs: "Jobs",
  filterTraining: "Training",
  filterOwnWork: "Own work & loans",
  filterLocal: "In a town",
  filterNone: "Nothing here with these filters.",
  filterClear: "Show everything",
  nearbyStraightLine: "Distances are in a straight line, not by road.",
  nearbyViewOnOsm: "On OpenStreetMap",
  nearbySupportAsOf: "OpenStreetMap data as of {date}.",
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
  somethingWentWrong: "Something went wrong.",
  offlineNotice:
    "Running without the speech and language services, so I am reading only what you name directly.",
  storageOfflineNotice:
    "Saving is paused right now, so your record may not be kept. Everything else works.",
  llmBusyNotice:
    "The language service is not answering right now: it is busy, or has used up today's allowance. Until it is back I read only the skills you name directly and give simpler answers.",
  llmBackAround: "It should be back around {time}.",
};

const ta: Copy = {
  statement: "உங்கள் அனுபவத்திற்கு ஒரு குரல் இருக்கிறது.",
  speakHint: "அழுத்தி, நீங்கள் செய்த வேலையைப் பற்றி சொல்லுங்கள்.",
  orType: "அல்லது தட்டச்சு செய்யுங்கள்",
  typePlaceholder: "நான் டூ-வீலர் ரிப்பேர் செய்வேன்",
  typeSubmit: "வேலை தேடு",
  notKept: "உங்கள் குரல் சேமிக்கப்படுவதில்லை. நீங்கள் சொன்ன வார்த்தைகள் மட்டுமே வைக்கப்படும்.",
  aboutTitle: "இங்கே என்ன நடக்கிறது",
  aboutSteps: [
    {
      title: "நீங்கள் பேசுங்கள்",
      body:
        "மைக்கை அழுத்தி, நீங்கள் செய்த வேலையை உங்கள் வார்த்தையில் சொல்லுங்கள். நிரப்ப படிவம் எதுவும் இல்லை.",
    },
    {
      title: "நான் புரிந்ததைப் பாருங்கள்",
      body:
        "ஒவ்வொரு திறமையும், அதை உருவாக்கிய உங்கள் வார்த்தைகளுடன் காட்டப்படும். தவறானதை மாற்றலாம், நீக்கலாம்.",
    },
    {
      title: "பொருந்துவதைப் பாருங்கள்",
      body:
        "உங்கள் ஊருக்கு அருகில் உள்ள வேலை, பயிற்சி, அரசுத் திட்டங்கள் — ஒவ்வொன்றும் ஏன் பொருந்துகிறது என்பதுடன்.",
    },
  ],
  aboutNote:
    "VoicePath உங்களுக்காக விண்ணப்பம் அனுப்பாது. என்ன இருக்கிறது, அங்கே போய் என்ன சொல்ல வேண்டும் என்பதைச் சொல்கிறது.",
  navHome: "முகப்பு",
  navAbout: "பற்றி",
  flowSteps: [
    "பேசுங்கள்",
    "நான் கேட்டது",
    "உங்கள் பாஸ்போர்ட்",
    "பொருந்துவது",
    "நீங்கள் தேர்வது",
  ],
  flowHere: "நீங்கள் இங்கே",
  readOnGovPage: "அரசு பக்கத்தில் படியுங்கள்",
  aboutPageTitle: "VoicePath பற்றி",
  aboutPageLede:
    "நீங்கள் செய்த வேலையைச் சொன்னால் போதும் — உங்கள் மொழியில், படிவம் நிரப்பாமல் — அரசு வேலை, பயிற்சி, திட்டங்களைக் கண்டுபிடிக்க ஒரு வழி.",
  aboutPageSections: [
    {
      heading: "இது யாருக்கு",
      body:
        "திறமை இருக்கிறது, ஆனால் அதற்கு ஆவணம் இல்லாதவர்களுக்கு. கொட்டகையில் கற்ற மெக்கானிக், அம்மாவிடம் கற்ற தையல்காரர், இருபது வருடம் வேலை செய்த சான்றிதழ் இல்லாத வெல்டர். வேலை உண்மை; அதை நிரூபிக்கும் காகிதம் இல்லை — அரசுத் தளங்கள் முதலில் காகிதத்தையே கேட்கின்றன.",
    },
    {
      heading: "எப்படி முடிவு செய்கிறது",
      body:
        "உங்கள் வார்த்தைகள் திறமைகளாக மாறும். ஒவ்வொரு திறமையும், அதை உருவாக்கிய உங்கள் வார்த்தைகளுடன் காட்டப்படும் — தவறானதை மாற்றலாம். பிறகு ஒவ்வொரு பதிவுக்கும் மதிப்பெண் கொடுக்கப்படும்: பாதி வேலைக்கு, மீதி அனுபவம், தேவைகள், தூரத்துக்கு. இது கணக்கு, கருத்து அல்ல — ஒவ்வொரு முறையும் அதே பதில்.",
    },
    {
      heading: "இது என்ன செய்யாது",
      body:
        "உங்களுக்காக விண்ணப்பம் அனுப்பாது. நீங்கள் தகுதியானவர் என்று சொல்லாது — பதிவு என்ன கேட்கிறது என்பதை மட்டுமே சொல்லும். உங்கள் வார்த்தையிலோ அரசு ஆவணத்திலோ இல்லாத எதையும் சொல்லாது. தெரியாதபோது, ஊகிக்காமல் தெரியாது என்றே சொல்லும்.",
    },
    {
      heading: "உங்கள் குரல்",
      body:
        "உங்கள் பதிவு எழுத்தாக மாற்றப்பட்டு அழிக்கப்படும். நீங்கள் கேட்டால் மட்டுமே வைக்கப்படும்; அதை எப்போது வேண்டுமானாலும் உங்கள் பாஸ்போர்ட்டில் மாற்றலாம். சேமிக்கப்படுவது வார்த்தைகள், குரல் அல்ல.",
    },
    {
      heading: "தகவல் எங்கிருந்து",
      body:
        "வெளியிடப்பட்ட அரசுத் திட்ட ஆவணங்கள் மற்றும் அதிகாரப்பூர்வ அரசு பக்கங்களிலிருந்து. ஒவ்வொரு பதிலும் எந்த ஆவணத்திலிருந்து வந்தது என்பதைக் காட்டும் — நீங்களே சரிபார்க்கலாம், அலுவலகத்தில் சொல்லலாம். இது இலவசம், எப்போதும் இலவசமாகவே இருக்கும்.",
    },
  ],
  listening: "கேட்டுக்கொண்டிருக்கிறேன்",
  stopHint: "முடிக்க அழுத்துங்கள்",
  startOver: "மீண்டும் தொடங்கு",
  micDenied:
    "உங்கள் குரல் கேட்கவில்லை. உலாவியில் மைக்ரோஃபோனை அனுமதித்து மீண்டும் முயலுங்கள்.",
  micUnsupported:
    "இந்த உலாவியில் பதிவு செய்ய முடியாது. Chrome பயன்படுத்துங்கள், அல்லது தட்டச்சு செய்யுங்கள்.",
  serverUnreachable:
    "VoicePath இப்போது சேவையகத்தை அடைய முடியவில்லை, அதனால் மைக்ரோஃபோன் இயங்கவில்லை. நான் தொடர்ந்து முயற்சிக்கிறேன் — பதில் வந்ததும் இந்தப் பக்கம் தானாக வேலை செய்யும்.",
  serverWaking: "தொடங்குகிறது. முதல் முறை ஒரு நிமிடம் ஆகும்.",
  weHeard: "நான் புரிந்துகொண்டது இதுதான்.",
  weHeardSub:
    "தவறு இருந்தால் மாற்றுங்கள். ஒவ்வொரு வரியிலும் நீங்கள் சொன்ன வார்த்தைகள் இருக்கும்.",
  confirm: "இது சரி",
  addMore: "இன்னும் சொல்லுங்கள்",
  addByTyping: "அல்லது நீங்கள் செய்யும் வேலையைத் தட்டச்சு செய்யுங்கள்",
  addSkillPlaceholder: "தச்சு வேலை",
  addSkillSubmit: "சேர்",
  notWork:
    "அது வேலை போல் தெரியவில்லை. நீங்கள் செய்யும் வேலையைச் சொல்லுங்கள் — தச்சு, வெல்டிங், ஓட்டுநர் — அல்லது ஒரு திட்டத்தைப் பற்றிக் கேளுங்கள்.",
  experienceHeard: "{years} வருட வேலை",
  experienceNotHeard: "இந்த வேலையை எவ்வளவு காலம் செய்கிறீர்கள் என்று சொல்லவில்லை.",
  experienceChange: "சரியில்லையா? மாற்றுங்கள்",
  experienceAdd: "சேர்க்கவும்",
  experienceLabel: "இந்த வேலையை எத்தனை வருடங்களாகச் செய்கிறீர்கள்?",
  experienceSave: "சேமி",
  experienceCancel: "ரத்து",
  experienceRematch: "இந்த எண்ணை வைத்து உங்கள் திட்டங்கள் மீண்டும் பொருத்தப்படும்.",
  experienceInvalid: "0 முதல் 70 வரை வருடங்களின் எண்ணிக்கையை உள்ளிடவும்.",
  youSaid: "நீங்கள் சொன்னது",
  notSure: "இதில் எனக்கு முழு உறுதி இல்லை",
  edit: "மாற்று",
  remove: "நீக்கு",
  save: "சேமி",
  nothingHeard: "நீங்கள் செய்த வேலை எதுவும் எனக்குப் புரியவில்லை.",
  nothingHeardSub: "மீண்டும் சொல்லுங்கள், எந்த வேலை என்பதை உங்கள் வார்த்தையில் சொல்லுங்கள்.",
  answeredQuestion: "நீங்கள் ஒரு கேள்வி கேட்டீர்கள், பதில் இதோ.",
  safetyTitle: "நீங்களோ அருகில் உள்ள ஒருவரோ ஆபத்தில் இருந்தால், இப்போதே அழையுங்கள். இலவசம்.",
  safety112: "அவசரம்: காவல், ஆம்புலன்ஸ், தீயணைப்பு. தமிழில் பேசலாம், இரவும் பகலும்.",
  safety181: "பெண்கள் உதவி எண்",
  safety1098: "குழந்தைகளுக்கு",
  safety14416: "உயிரை மாய்த்துக்கொள்ள நினைத்தால்",
  safetyCannotSend: "VoicePath தானே உதவி அனுப்ப முடியாது. இந்த எண்கள் முடியும்.",
  askedNotTold: "உங்களுக்கு வேலை தேட, நீங்கள் செய்த வேலையைச் சொல்லுங்கள்.",
  whichOne: "எதைச் சொன்னீர்கள்?",
  resay: "மீண்டும் சொல்லுங்கள்",
  skip: "இதை விட்டுவிடு",
  passportLabel: "திறன் பாஸ்போர்ட்",
  passportTitle: "உங்கள் வேலை, உங்கள் வார்த்தைகளில்.",
  passportPrint: "அச்சிடு அல்லது PDF ஆகச் சேமி",
  passportPrintHint: "உங்கள் போனில் ஒரு நகலை வைத்திருக்க, பிரிண்டராக \u201cSave as PDF\u201d என்பதைத் தேர்ந்தெடுக்கவும்.",
  passportRecordedOn: "{date} அன்று VoicePath-இல் பதிவு செய்யப்பட்டது.",
  passportNotCertificate:
    "ஒவ்வொரு வரியும், அவர் தன் வேலையைப் பற்றித் தன் சொந்த வார்த்தைகளில் சொன்னது. இது சான்றிதழோ அரசு ஆவணமோ அல்ல.",
  passportVoiceNote:
    "உங்கள் குரல் பதிவு, நீங்கள் சொன்னதை எழுதுவதற்கு மட்டுமே பயன்பட்டது. அது வைக்கப்படவில்லை, வேறு யாரும் அதைக் கேட்கவில்லை.",
  statYears: "வருட வேலை",
  statSkills: "வகை வேலை",
  statLanguages: "மொழி",
  matchesTitle: "உங்கள் வேலைக்குப் பொருந்தும் இடங்கள்.",
  matchesSub: "மிக அருகில் இருப்பது முதலில். நீங்கள் சொன்னதை வைத்து மட்டுமே காரணம் சொல்கிறேன்.",
  matchWord: "உங்கள் வேலைக்குப் பொருத்தம்",
  noMatches: "உங்கள் வேலைக்கு இங்கு இன்னும் எதுவும் பொருந்தவில்லை. இன்னும் சொல்லுங்கள்.",
  back: "பின்னால்",
  apply: "இது வேண்டும்",
  confidenceAccepted: "ஏற்கப்பட்டது",
  confidenceAsking: "உங்களிடம் கேட்கிறோம்",
  confidenceThreshold: "தேவை",
  weightsLabel: "எடை: திறமை 50% · அனுபவம் 25% · தகுதி 15% · இடம் 10%",
  schemeTypes: {
    "Full-time": "முழு நேரம்",
    "Part-time": "பகுதி நேரம்",
    Training: "பயிற்சி",
    Apprenticeship: "பயிற்சிப் பணி",
    "Self-employment support": "சொந்தத் தொழில் உதவி",
  },
  skillCategories: {
    Agriculture: "விவசாயம்",
    "Traditional Crafts": "பாரம்பரிய கைவினை",
    Commerce: "வணிகம்",
    Construction: "கட்டிடம்",
    Electrical: "மின் வேலை",
    Electronics: "மின்னணு",
    Hospitality: "விருந்தோம்பல்",
    Mechanical: "இயந்திரம்",
    Metalwork: "உலோக வேலை",
    Service: "சேவை",
    Textile: "நெசவு",
    Transport: "போக்குவரத்து",
  },
  payUpTo: "₹{amount} வரை",
  payFrom: "₹{amount} முதல்",
  applyHow: "இந்த வேலையை எப்படிக் கேட்பது",
  applyRefLabel: "அலுவலகத்தில் இந்த எண்ணைச் சொல்லுங்கள்",
  applyNote:
    "VoicePath உங்களுக்காக விண்ணப்பத்தை அனுப்பாது. நீங்கள் போகும் இடத்தில் இந்த எண்ணைச் சொன்னால், இதே வேலையை அவர்கள் கண்டுபிடிப்பார்கள்.",
  officialPage: "அரசின் சொந்தப் பக்கத்தில் இதைப் படியுங்கள்",
  viewPassport: "என் பாஸ்போர்ட்",
  fromRecord: "பதிவில் உள்ளது மட்டுமே. அதற்கு மேல் எதுவும் சேர்க்கப்படவில்லை.",
  factPay: "தொகை",
  factExperience: "கேட்கும் அனுபவம்",
  factCertificates: "தேவையான சான்றிதழ்கள்",
  yearsCount: "{years} வருடம்",
  languageSwitch: "மொழி",
  navNearby: "அருகில்",
  nearbyTitle: "உங்கள் அருகில் என்ன இருக்கிறது.",
  nearbySub:
    "உங்கள் வேலைக்குப் பொருந்துபவை, அவற்றைப் பற்றிக் கேட்கக்கூடிய அலுவலகங்கள்.",
  nearbyUseLocation: "என் இருப்பிடத்தைப் பயன்படுத்து",
  nearbyLocating: "நீங்கள் எங்கே இருக்கிறீர்கள் என்று பார்க்கிறேன்…",
  nearbyGpsNote:
    "உங்கள் சரியான இடம் அனுப்பப்படாது — சுமார் ஒரு கிலோமீட்டர் பகுதி மட்டும், இந்த ஒரு தேடலுக்காக. எதுவும் சேமிக்கப்படாது.",
  nearbyLocationDenied:
    "இருப்பிடத்துக்கு அனுமதி கிடைக்கவில்லை, அதனால் வரைபடம் அப்படியே இருக்கிறது.",
  nearbyLocationFailed:
    "உங்கள் இருப்பிடம் கிடைக்கவில்லை, அதனால் வரைபடம் அப்படியே இருக்கிறது.",
  nearbyCentreGps: "நீங்கள் இப்போது இருக்கும் இடத்தைச் சுற்றி",
  nearbyCentrePlace: "நீங்கள் சொன்ன {place} அருகில்",
  nearbyCentreChosen: "{place} அருகில்",
  nearbyCentreDefault:
    "நீங்கள் எங்கே இருக்கிறீர்கள் என்று எனக்குத் தெரியாது, அதனால் வாய்ப்புகள் இருக்கும் இடத்தைக் காட்டுகிறேன். உங்கள் ஊரைத் தேர்ந்தெடுங்கள், அல்லது இருப்பிடத்தைப் பயன்படுத்துங்கள்.",
  nearbyChooseTown: "ஊரைத் தேர்ந்தெடுங்கள்",
  nearbyWithin: "சுற்றளவு",
  nearbyYourMatches: "உங்களுக்குப் பொருந்துபவை",
  nearbyAllOpenings: "எல்லா வாய்ப்புகளும்",
  nearbyOpeningsHeading: "வாய்ப்புகள், அருகில் உள்ளவை முதலில்",
  nearbySupportHeading: "உதவக்கூடிய இடங்கள்",
  nearbySupportNote:
    "OpenStreetMap-இலிருந்து. போகும் முன் நேரத்தைச் சரிபாருங்கள் — இந்தப் பட்டியல் பழையதாக இருக்கலாம்.",
  nearbySupportUnavailable:
    "அருகிலுள்ள அலுவலகங்களை இப்போது ஏற்ற முடியவில்லை. வாய்ப்புகள் இன்னும் காட்டப்படுகின்றன.",
  nearbySupportNone: "இந்த வகை அலுவலகம் இங்கு அருகில் வரைபடத்தில் குறிக்கப்படவில்லை.",
  nearbySupportOffline: "இந்தச் சர்வரில் அருகிலுள்ள அலுவலகங்கள் தேடப்படுவதில்லை.",
  nearbyApprox: "ஊரின் மையத்தில் குறிக்கப்பட்டுள்ளது — பதிவில் தெரு முகவரி இல்லை.",
  nearbyKm: "{km} கி.மீ",
  nearbyYou: "நீங்கள்",
  nearbyDirections: "வழி",
  nearbyShowOnMap: "வரைபடத்தில் பாருங்கள்",
  nearbyCount: "இங்கே {count}",
  nearbyCategories: {
    training: "பயிற்சி நிலையங்கள், ஐடிஐ",
    employment: "வேலைவாய்ப்பு அலுவலகங்கள்",
    government: "அரசு அலுவலகங்கள்",
    bank: "வங்கிகள்",
  },
  nearbyOpenings: "வாய்ப்புகள்",
  nearbyUnplaced: "இன்னும் வரைபடத்தில் இல்லை — இதன் ஊர் வரைபடத்துக்குத் தெரியாது.",
  nearbyNationwide: "இந்தியா முழுவதும் உள்ளவை",
  nearbyNationwideNote:
    "தேசியத் திட்டங்கள் — ஒரு ஊருக்கு மட்டும் அல்ல. யாருக்கு, எப்படி விண்ணப்பிப்பது என்று அறிய திறந்து பாருங்கள்.",
  allIndia: "இந்தியா முழுவதும்",
  filterKind: "வகை",
  filterWhere: "எங்கே",
  filterSkill: "என் திறன்",
  filterAll: "அனைத்தும்",
  filterJobs: "வேலைகள்",
  filterTraining: "பயிற்சி",
  filterOwnWork: "சொந்தத் தொழில், கடன்",
  filterLocal: "ஊரில்",
  filterNone: "இந்த வடிகட்டல்களுடன் எதுவும் இல்லை.",
  filterClear: "அனைத்தையும் காட்டு",
  nearbyStraightLine: "தூரம் நேர்கோட்டில், சாலை வழியாக அல்ல.",
  nearbyViewOnOsm: "OpenStreetMap-இல்",
  nearbySupportAsOf: "{date} நிலவரப்படி OpenStreetMap தரவு.",
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
  somethingWentWrong: "ஏதோ தவறாகி விட்டது. மீண்டும் முயற்சி செய்யுங்கள்.",
  offlineNotice:
    "பேச்சு மற்றும் மொழி சேவைகள் இல்லாமல் இயங்குகிறது, நீங்கள் நேரடியாகச் சொன்னதை மட்டுமே படிக்கிறேன்.",
  storageOfflineNotice:
    "இப்போது சேமிப்பு நிறுத்தப்பட்டுள்ளது, அதனால் உங்கள் பதிவு நிலைக்காமல் போகலாம். மற்றவை எல்லாம் வேலை செய்கின்றன.",
  llmBusyNotice:
    "மொழி சேவை இப்போது பதிலளிக்கவில்லை: அது பரபரப்பாக உள்ளது, அல்லது இன்றைய வரம்பை முடித்துவிட்டது. அது திரும்பும் வரை நீங்கள் நேரடியாகச் சொல்லும் திறன்களை மட்டுமே படித்து, எளிய பதில்களைத் தருகிறேன்.",
  llmBackAround: "திரும்பும் நேரம்: சுமார் {time}.",
};

const hi: Copy = {
  statement: "आपके अनुभव की एक आवाज़ है।",
  speakHint: "दबाइए और अपने किए हुए काम के बारे में बताइए।",
  orType: "या टाइप कीजिए",
  typePlaceholder: "मैं दोपहिया गाड़ी ठीक करता हूँ",
  typeSubmit: "काम खोजिए",
  notKept: "आपकी आवाज़ सहेजी नहीं जाती। सिर्फ़ आपके कहे शब्द रखे जाते हैं।",
  aboutTitle: "यहाँ क्या होता है",
  aboutSteps: [
    {
      title: "आप बोलिए",
      body:
        "माइक दबाइए और जो काम आपने किया है वह अपने शब्दों में बताइए। कोई फ़ॉर्म नहीं भरना है।",
    },
    {
      title: "जो मैंने समझा वह देखिए",
      body:
        "हर हुनर के साथ आपके वही शब्द दिखेंगे जिनसे वह बना। जो ग़लत हो उसे बदल या हटा दीजिए।",
    },
    {
      title: "जो मेल खाता है वह देखिए",
      body:
        "आपके पास का काम, प्रशिक्षण और सरकारी योजनाएँ — हर एक के साथ यह भी कि वह क्यों मेल खाती है।",
    },
  ],
  aboutNote:
    "VoicePath आपकी ओर से आवेदन नहीं भेजता। यह बताता है कि क्या मौजूद है, और वहाँ जाकर क्या कहना है।",
  navHome: "मुख्य पृष्ठ",
  navAbout: "परिचय",
  flowSteps: [
    "बोलिए",
    "जो मैंने सुना",
    "आपका पासपोर्ट",
    "जो मेल खाता है",
    "आपकी पसंद",
  ],
  flowHere: "आप यहाँ हैं",
  readOnGovPage: "सरकारी पन्ने पर पढ़िए",
  aboutPageTitle: "VoicePath के बारे में",
  aboutPageLede:
    "जो काम आपने किया है वह बोलकर सरकारी काम, प्रशिक्षण और योजनाएँ ढूँढ़ने का एक तरीक़ा — अपनी भाषा में, बिना कोई फ़ॉर्म भरे।",
  aboutPageSections: [
    {
      heading: "यह किसके लिए है",
      body:
        "उनके लिए जिनका हुनर असली है पर काग़ज़ नहीं। वह मिस्त्री जिसने शेड में सीखा, वह दर्ज़िन जिसे माँ ने सिखाया, वह वेल्डर जिसके बीस साल हैं और प्रमाणपत्र नहीं। काम सच है; उसे साबित करने वाला काग़ज़ नहीं — और सरकारी पोर्टल पहले काग़ज़ ही माँगते हैं।",
    },
    {
      heading: "यह कैसे तय करता है",
      body:
        "आपके शब्द हुनर में बदलते हैं, और हर हुनर के साथ वही शब्द दिखते हैं जिनसे वह बना — जो ग़लत हो बदल दीजिए। फिर हर पद के लिए अंक बनते हैं: आधा काम पर, बाक़ी अनुभव, ज़रूरतों और दूरी पर। यह गणित है, राय नहीं — हर बार वही उत्तर।",
    },
    {
      heading: "यह क्या नहीं करेगा",
      body:
        "यह आपकी ओर से आवेदन नहीं भेजता। यह नहीं कहता कि आप पात्र हैं — सिर्फ़ यह कि पद क्या माँगता है। जो आपके अपने शब्दों या किसी प्रकाशित सरकारी दस्तावेज़ में नहीं है, वह नहीं बताएगा। और जब पता न हो, तो अनुमान लगाने के बजाय कह देगा कि पता नहीं।",
    },
    {
      heading: "आपकी आवाज़",
      body:
        "आपकी रिकॉर्डिंग शब्दों में बदलकर मिटा दी जाती है। वह तभी रखी जाती है जब आप कहें, और इसे आप अपने पासपोर्ट पर कभी भी बदल सकते हैं। जो रखा जाता है वह शब्द हैं, आवाज़ नहीं।",
    },
    {
      heading: "जानकारी कहाँ से आती है",
      body:
        "प्रकाशित सरकारी योजना दस्तावेज़ों और आधिकारिक सरकारी पन्नों से। योजना के बारे में हर उत्तर यह दिखाता है कि वह किस दस्तावेज़ से आया — आप ख़ुद जाँच सकते हैं या दफ़्तर में बता सकते हैं। इसका उपयोग मुफ़्त है, और हमेशा रहेगा।",
    },
  ],
  listening: "सुन रहा हूँ",
  stopHint: "खत्म करने के लिए दबाइए",
  startOver: "फिर से शुरू करें",
  micDenied: "आपकी आवाज़ नहीं आ रही। ब्राउज़र में माइक की अनुमति दीजिए और फिर कोशिश कीजिए।",
  micUnsupported: "यह ब्राउज़र रिकॉर्ड नहीं कर सकता। Chrome आज़माइए, या टाइप कीजिए।",
  serverUnreachable:
    "VoicePath अभी अपने सर्वर तक नहीं पहुँच पा रहा, इसलिए माइक बंद है। मैं कोशिश करता रहूँगा — जवाब आते ही यह पेज अपने-आप काम करने लगेगा।",
  serverWaking: "शुरू हो रहा है। पहली बार में करीब एक मिनट लगता है।",
  weHeard: "मैंने यही समझा।",
  weHeardSub: "जो गलत है उसे बदल दीजिए। हर पंक्ति में आपके ही कहे शब्द दिख रहे हैं।",
  confirm: "यह सही है",
  addMore: "कुछ और बताइए",
  addByTyping: "या जो काम आप करते हैं वह लिखिए",
  addSkillPlaceholder: "बढ़ईगीरी",
  addSkillSubmit: "जोड़ें",
  notWork:
    "यह काम जैसा नहीं लगा। जो काम आप करते हैं वह बताइए — बढ़ईगीरी, वेल्डिंग, ड्राइविंग — या किसी योजना के बारे में पूछिए।",
  experienceHeard: "{years} साल का काम",
  experienceNotHeard: "आपने यह नहीं बताया कि यह काम कितने समय से कर रहे हैं।",
  experienceChange: "सही नहीं है? बदलिए",
  experienceAdd: "जोड़िए",
  experienceLabel: "आप यह काम कितने साल से कर रहे हैं?",
  experienceSave: "सहेजें",
  experienceCancel: "रद्द करें",
  experienceRematch: "इस संख्या के साथ आपकी योजनाएँ फिर से मिलाई जाएँगी।",
  experienceInvalid: "0 से 70 के बीच सालों की संख्या लिखिए।",
  youSaid: "आपने कहा",
  notSure: "इस बारे में मुझे पूरा भरोसा नहीं है",
  edit: "बदलें",
  remove: "हटाएँ",
  save: "सहेजें",
  nothingHeard: "आपने जो काम किया, वह मुझे समझ नहीं आया।",
  nothingHeardSub: "फिर से बताइए, और किस तरह का काम है वह अपने शब्दों में कहिए।",
  answeredQuestion: "आपने सवाल पूछा, उसका जवाब यह है।",
  safetyTitle: "अगर आप या आपके पास कोई ख़तरे में है, तो अभी कॉल कीजिए। यह मुफ़्त है।",
  safety112: "आपातकाल: पुलिस, एम्बुलेंस, दमकल। हिंदी में बात कीजिए, दिन-रात।",
  safety181: "महिला हेल्पलाइन",
  safety1098: "बच्चों के लिए",
  safety14416: "अगर आप अपनी जान लेने की सोच रहे हैं",
  safetyCannotSend: "VoicePath ख़ुद मदद नहीं भेज सकता। ये नंबर भेज सकते हैं।",
  askedNotTold: "आपके लिए काम ढूँढ़ने के लिए, आपने जो काम किया है वह बताइए।",
  whichOne: "आपका मतलब किससे था?",
  resay: "फिर से बोलिए",
  skip: "इसे छोड़ दीजिए",
  passportLabel: "स्किल पासपोर्ट",
  passportTitle: "आपका काम, आपके ही शब्दों में।",
  passportPrint: "प्रिंट करें या PDF में सहेजें",
  passportPrintHint: "फ़ोन में कॉपी रखने के लिए, प्रिंटर में \u201cSave as PDF\u201d चुनें।",
  passportRecordedOn: "{date} को VoicePath पर दर्ज किया गया।",
  passportNotCertificate:
    "हर पंक्ति वही है जो व्यक्ति ने अपने काम के बारे में अपने शब्दों में कहा। यह कोई प्रमाणपत्र या सरकारी दस्तावेज़ नहीं है।",
  passportVoiceNote:
    "आपकी रिकॉर्डिंग सिर्फ़ यह लिखने के लिए इस्तेमाल हुई कि आपने क्या कहा। उसे रखा नहीं गया, और किसी और ने उसे नहीं सुना।",
  statYears: "साल का काम",
  statSkills: "तरह के काम",
  statLanguages: "भाषा",
  matchesTitle: "जगहें जहाँ आपका काम बैठता है।",
  matchesSub: "सबसे नज़दीक पहले। हर एक का कारण आपके ही कहे पर आधारित है।",
  matchWord: "आपके काम से मेल",
  noMatches: "अभी यहाँ आपके काम से कुछ नहीं मिलता। अपने काम के बारे में और बताइए।",
  back: "वापस",
  apply: "मुझे यह चाहिए",
  confidenceAccepted: "स्वीकार",
  confidenceAsking: "आपसे पूछ रहे हैं",
  confidenceThreshold: "चाहिए",
  weightsLabel: "भार: कौशल 50% · अनुभव 25% · पात्रता 15% · जगह 10%",
  schemeTypes: {
    "Full-time": "पूरा समय",
    "Part-time": "आंशिक समय",
    Training: "प्रशिक्षण",
    Apprenticeship: "शिक्षुता",
    "Self-employment support": "स्वरोज़गार सहायता",
  },
  skillCategories: {
    Agriculture: "खेती",
    "Traditional Crafts": "पारंपरिक शिल्प",
    Commerce: "व्यापार",
    Construction: "निर्माण",
    Electrical: "बिजली का काम",
    Electronics: "इलेक्ट्रॉनिक्स",
    Hospitality: "आतिथ्य",
    Mechanical: "मशीन का काम",
    Metalwork: "धातु का काम",
    Service: "सेवा",
    Textile: "कपड़ा",
    Transport: "परिवहन",
  },
  payUpTo: "₹{amount} तक",
  payFrom: "₹{amount} से",
  applyHow: "यह काम कैसे माँगें",
  applyRefLabel: "दफ़्तर में यह नंबर बताइए",
  applyNote:
    "VoicePath आपकी ओर से आवेदन नहीं भेजता। जहाँ जाएँ वहाँ यह नंबर बता दीजिए, वे यही काम ढूँढ़ लेंगे।",
  officialPage: "इसे सरकार के अपने पेज पर पढ़िए",
  viewPassport: "मेरा पासपोर्ट",
  fromRecord: "सिर्फ़ रिकॉर्ड में जो है वही। उसके बाहर कुछ नहीं जोड़ा गया।",
  factPay: "रकम",
  factExperience: "माँगा गया अनुभव",
  factCertificates: "ज़रूरी प्रमाणपत्र",
  yearsCount: "{years} साल",
  languageSwitch: "भाषा",
  navNearby: "आसपास",
  nearbyTitle: "आपके आसपास क्या है।",
  nearbySub:
    "आपके काम से मेल खाने वाले मौके, और वे दफ़्तर जहाँ आप उनके बारे में पूछ सकते हैं।",
  nearbyUseLocation: "मेरी जगह इस्तेमाल करें",
  nearbyLocating: "देख रहा हूँ कि आप कहाँ हैं…",
  nearbyGpsNote:
    "आपकी सटीक जगह नहीं भेजी जाती — सिर्फ़ लगभग एक किलोमीटर का इलाका, इसी एक खोज के लिए। कुछ भी सहेजा नहीं जाता।",
  nearbyLocationDenied: "जगह की इजाज़त नहीं मिली, इसलिए नक्शा वहीं है जहाँ था।",
  nearbyLocationFailed: "आपकी जगह पता नहीं चल पाई, इसलिए नक्शा वहीं है जहाँ था।",
  nearbyCentreGps: "आप अभी जहाँ हैं, उसके आसपास",
  nearbyCentrePlace: "{place} के आसपास — जो जगह आपने बताई",
  nearbyCentreChosen: "{place} के आसपास",
  nearbyCentreDefault:
    "मुझे नहीं पता कि आप कहाँ हैं, इसलिए यह वहाँ दिखा रहा है जहाँ मौके हैं। अपना शहर चुनिए, या अपनी जगह इस्तेमाल कीजिए।",
  nearbyChooseTown: "शहर चुनिए",
  nearbyWithin: "दायरा",
  nearbyYourMatches: "आपसे मेल खाने वाले",
  nearbyAllOpenings: "सभी मौके",
  nearbyOpeningsHeading: "मौके, सबसे पास वाले पहले",
  nearbySupportHeading: "जहाँ से मदद मिल सकती है",
  nearbySupportNote:
    "OpenStreetMap से। जाने से पहले समय पता कर लीजिए — यह सूची पुरानी हो सकती है।",
  nearbySupportUnavailable:
    "आसपास के दफ़्तर अभी लोड नहीं हो पाए। मौके फिर भी दिख रहे हैं।",
  nearbySupportNone: "इस तरह का कोई दफ़्तर यहाँ आसपास नक्शे पर दर्ज नहीं है।",
  nearbySupportOffline: "इस सर्वर पर आसपास के दफ़्तर नहीं खोजे जाते।",
  nearbyApprox: "शहर के बीच में दिखाया गया है — रिकॉर्ड में गली का पता नहीं है।",
  nearbyKm: "{km} किमी",
  nearbyYou: "आप",
  nearbyDirections: "रास्ता",
  nearbyShowOnMap: "नक्शे पर देखिए",
  nearbyCount: "यहाँ {count}",
  nearbyCategories: {
    training: "प्रशिक्षण केंद्र और आईटीआई",
    employment: "रोज़गार दफ़्तर",
    government: "सरकारी दफ़्तर",
    bank: "बैंक",
  },
  nearbyOpenings: "मौके",
  nearbyUnplaced: "अभी नक्शे पर नहीं — नक्शे को इसका शहर पता नहीं।",
  nearbyNationwide: "पूरे भारत में खुली योजनाएँ",
  nearbyNationwideNote:
    "राष्ट्रीय योजनाएँ — किसी एक शहर तक सीमित नहीं। किसके लिए है और आवेदन कैसे करें, यह देखने के लिए खोलिए।",
  allIndia: "पूरे भारत में",
  filterKind: "प्रकार",
  filterWhere: "कहाँ",
  filterSkill: "मेरा कौशल",
  filterAll: "सभी",
  filterJobs: "नौकरियाँ",
  filterTraining: "प्रशिक्षण",
  filterOwnWork: "अपना काम और लोन",
  filterLocal: "किसी शहर में",
  filterNone: "इन फ़िल्टर के साथ कुछ नहीं मिला।",
  filterClear: "सब दिखाएँ",
  nearbyStraightLine: "दूरी सीधी रेखा में है, सड़क से नहीं।",
  nearbyViewOnOsm: "OpenStreetMap पर",
  nearbySupportAsOf: "{date} तक का OpenStreetMap डेटा।",
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
  somethingWentWrong: "कुछ गड़बड़ हो गई। फिर कोशिश कीजिए।",
  offlineNotice:
    "भाषा और आवाज़ की सेवाओं के बिना चल रहा है, इसलिए सिर्फ़ वही पढ़ रहा हूँ जो आपने सीधे कहा।",
  storageOfflineNotice:
    "अभी सहेजना रुका हुआ है, इसलिए हो सकता है आपका रिकॉर्ड न रहे। बाकी सब काम कर रहा है।",
  llmBusyNotice:
    "भाषा सेवा अभी जवाब नहीं दे रही: वह व्यस्त है, या आज की सीमा पूरी कर चुकी है। उसके लौटने तक मैं सिर्फ़ वही हुनर पढ़ूँगा जो आप सीधे बताएँ, और सरल जवाब दूँगा।",
  llmBackAround: "लगभग {time} तक वापस आ जानी चाहिए।",
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

/**
 * A scheme's place, in the reader's language where the app knows it.
 *
 * "All India" is translated here. A town comes with its names from the API
 * (`location_names`, from the gazetteer the map uses -- never a spelling made
 * up on the spot); a place the gazetteer does not know stays as the catalogue
 * wrote it.
 */
export function placeLabel(
  place: string | null | undefined,
  language: Language,
  names?: Record<string, string> | null,
): string {
  if (!place) return "";
  if (place === "All India") return copyFor(language).allIndia;
  return names?.[language] || place;
}

/** Localised label for a scheme type. Unknown values pass through. */
export function typeLabel(type: string, language: Language): string {
  return copyFor(language).schemeTypes[type] ?? type;
}

/**
 * Localised label for a taxonomy category.
 *
 * Categories arrive from the database in English because that is what the
 * taxonomy stores. Unknown values pass through rather than being hidden --
 * a category nobody has translated yet is still information.
 */
export function categoryLabel(
  category: string | null | undefined,
  language: Language,
): string {
  if (!category) return "";
  return copyFor(language).skillCategories[category] ?? category;
}

/**
 * Monthly pay, written the way each language writes it.
 *
 * The open-ended forms used to be English string literals -- "up to ₹8,000"
 * sat inside an otherwise Tamil row. The digits stay in the Indian
 * grouping, which all three languages use.
 */
export function payLabel(
  low: number | null | undefined,
  high: number | null | undefined,
  language: Language,
): string {
  const money = (value: number) => `₹${value.toLocaleString("en-IN")}`;
  const copy = copyFor(language);

  if (low && high) {
    return low === high ? money(low) : `${money(low)}–${money(high)}`;
  }
  if (high) return copy.payUpTo.replace("{amount}", high.toLocaleString("en-IN"));
  if (low) return copy.payFrom.replace("{amount}", low.toLocaleString("en-IN"));
  return "—";
}
