// Bilingual landing copy kept local (not in the strict i18n Dict) so marketing prose can evolve
// without forcing a matching key into every screen's dictionary.
export interface LandingCopy {
  heroBadge: string;
  heroTitle: string;
  heroSub: string;
  ctaStart: string;
  ctaLearn: string;
  stats: { value: string; label: string }[];
  servicesTitle: string;
  servicesSub: string;
  services: { icon: string; title: string; body: string }[];
  featuresTitle: string;
  features: { icon: string; title: string; body: string }[];
  stepsTitle: string;
  steps: { title: string; body: string }[];
  whyTitle: string;
  whyPoints: string[];
  whyStat: { value: string; label: string };
  safetyTitle: string;
  safetyBody: string;
  privacyTitle: string;
  privacyBody: string;
  faqTitle: string;
  faqs: { q: string; a: string }[];
  partner: string;
  footerCta: string;
  footerStart: string;
  footerTagline: string;
  footerCols: { title: string; links: string[] }[];
  footerRights: string;
}

const en: LandingCopy = {
  heroBadge: "SRHR health navigator • Rwanda",
  heroTitle: "Private answers about your health, in your language.",
  heroSub:
    "Ubuzima is a youth-friendly companion for sexual and reproductive health. Ask anything by chat or voice, in English or Kinyarwanda — and get clear, judgement-free answers drawn from reviewed health information, with a doctor's referral whenever it matters.",
  ctaStart: "Start chatting",
  ctaLearn: "How it works",
  stats: [
    { value: "EN + RW", label: "English & Kinyarwanda" },
    { value: "100%", label: "Private & anonymous" },
    { value: "Reviewed", label: "Approved health sources" },
    { value: "24/7", label: "Always available" },
  ],
  servicesTitle: "What you can ask about",
  servicesSub: "No topic is too small or too awkward. Ubuzima answers with care and respect.",
  services: [
    { icon: "heart", title: "Contraception & family planning", body: "Methods, how they work, and how to choose with a health worker." },
    { icon: "shield", title: "HIV & STIs", body: "Prevention, testing, treatment, and staying healthy — no judgement." },
    { icon: "leaf", title: "Pregnancy", body: "Signs, testing, prevention and where to get supportive care." },
    { icon: "book", title: "Menstrual health & puberty", body: "Understanding your cycle and the changes your body goes through." },
    { icon: "lock", title: "Consent & relationships", body: "What consent means, healthy relationships, and how to get help." },
    { icon: "mic", title: "Anything on your mind", body: "Worries, questions, or just needing someone to explain clearly." },
  ],
  featuresTitle: "How Ubuzima helps",
  features: [
    { icon: "chat", title: "Chat, your way",
      body: "Ask health questions in plain words and get a calm, clear reply — no jargon, no judgement." },
    { icon: "mic", title: "Talk out loud",
      body: "Prefer speaking? Use voice to ask and listen to the answer, hands-free." },
    { icon: "book", title: "Grounded in real sources",
      body: "Answers come from health documents reviewed by Health Development Initiative — not made up." },
    { icon: "shield", title: "Safe by design",
      body: "If something needs a professional, Ubuzima gently refers you to a clinic or counsellor." },
    { icon: "globe", title: "Two languages",
      body: "Switch between English and Kinyarwanda any time. Ubuzima understands both." },
    { icon: "lock", title: "Yours to control",
      body: "Anonymous by default. Anything sensitive is encrypted, and you can wipe it whenever you want." },
  ],
  stepsTitle: "How it works",
  steps: [
    { title: "Say hello", body: "Pick a nickname and a language. No real name or sign-up needed." },
    { title: "Ask freely", body: "Type or speak your question about your body, relationships or wellbeing." },
    { title: "Get clear help", body: "Receive a grounded answer, and a referral to a health worker when it matters." },
  ],
  whyTitle: "Built for young people, made to be trusted",
  whyPoints: [
    "Answers only from approved, clinically-reviewed information",
    "Never guesses — refers you to a health worker when unsure",
    "Recognises crisis and gender-based violence, and points to real help",
    "Anonymous first; your sensitive details are encrypted",
    "Works in English and Kinyarwanda, by chat and by voice",
  ],
  whyStat: { value: "0", label: "sign-up required to start" },
  safetyTitle: "Care, not crisis",
  safetyBody:
    "Ubuzima recognises when a question needs a person, not an app. For anything urgent or about safety, it points you to a trusted health worker and, for violence, to Rwanda's Isange One Stop Centres.",
  privacyTitle: "Private by default",
  privacyBody:
    "You start anonymous. Sensitive details you choose to share are encrypted at rest, and you can delete everything from your device and our servers at any time.",
  faqTitle: "Questions, answered",
  faqs: [
    { q: "Is it really private?", a: "Yes. You start anonymous, nothing needs your real name, and you can wipe your data any time." },
    { q: "Is it free?", a: "Yes — Ubuzima is free to use for health information and guidance." },
    { q: "Can it replace a doctor?", a: "No. Ubuzima gives clear information and refers you to a health worker whenever professional care is needed." },
    { q: "What languages does it speak?", a: "English and Kinyarwanda, by chat and by voice — switch any time." },
  ],
  partner: "Built with Health Development Initiative (HDI)",
  footerCta: "Ready when you are.",
  footerStart: "Open Ubuzima",
  footerTagline: "A private, youth-friendly SRHR health navigator for Rwanda.",
  footerCols: [
    { title: "Explore", links: ["Start chatting", "How it works", "Privacy"] },
    { title: "Topics", links: ["Contraception", "HIV & STIs", "Pregnancy", "Consent"] },
    { title: "Support", links: ["Find a clinic", "Isange One Stop Centre", "Talk to a human"] },
  ],
  footerRights: "Ubuzima — in partnership with Health Development Initiative.",
};

const rw: LandingCopy = {
  heroBadge: "Umuyobozi w'ubuzima bw'imyororokere • u Rwanda",
  heroTitle: "Ibisubizo by'ibanga ku buzima bwawe, mu rurimi rwawe.",
  heroSub:
    "Ubuzima ni inshuti y'urubyiruko ku buzima bw'imyororokere. Baza ikibazo cyose ukoresheje ikiganiro cyangwa ijwi, mu Cyongereza cyangwa Ikinyarwanda — uhabwe ibisubizo byumvikana, bitagucira urubanza, bishingiye ku makuru y'ubuzima yasuzumwe, n'ukwoherezwa ku muganga igihe bikenewe.",
  ctaStart: "Tangira ikiganiro",
  ctaLearn: "Uko bikora",
  stats: [
    { value: "EN + RW", label: "Icyongereza & Ikinyarwanda" },
    { value: "100%", label: "Ibanga, utamenyekana" },
    { value: "Byasuzumwe", label: "Inkomoko zemewe" },
    { value: "24/7", label: "Bihari igihe cyose" },
  ],
  servicesTitle: "Ibyo ushobora kubaza",
  servicesSub: "Nta kibazo gito cyangwa gitera ipfunwe. Ubuzima isubiza yitonze kandi yubaha.",
  services: [
    { icon: "heart", title: "Kuboneza urubyaro", body: "Uburyo, uko bukora, n'uko wabuhitamo ufatanyije n'umukozi w'ubuzima." },
    { icon: "shield", title: "SIDA n'indwara zandurira mu mibonano", body: "Kwirinda, gupimisha, kuvurwa — nta rubanza." },
    { icon: "leaf", title: "Gutwita", body: "Ibimenyetso, gupima, kwirinda n'aho wabonera ubufasha." },
    { icon: "book", title: "Imihango n'ubugimbi/ubwangavu", body: "Gusobanukirwa uruziga rwawe n'impinduka z'umubiri." },
    { icon: "lock", title: "Kwemeranya n'imibanire", body: "Icyo kwemeranya bisobanura, imibanire myiza, n'uko wabona ubufasha." },
    { icon: "mic", title: "Icyo ari cyo cyose", body: "Impungenge, ibibazo, cyangwa gusa ushaka usobanurirwa neza." },
  ],
  featuresTitle: "Uko Ubuzima igufasha",
  features: [
    { icon: "chat", title: "Ikiganiro ku buryo bwawe",
      body: "Baza ibibazo by'ubuzima mu magambo yoroshye uhabwe igisubizo gituje — nta rurimi rukomeye, nta rubanza." },
    { icon: "mic", title: "Vuga mu ijwi",
      body: "Ukunda kuvuga? Koresha ijwi mu kubaza no kumva igisubizo, nta kwandika." },
    { icon: "book", title: "Gishingiye ku nkomoko nyazo",
      body: "Ibisubizo biva mu nyandiko zasuzumwe na Health Development Initiative — ntabwo byahimbwe." },
    { icon: "shield", title: "Umutekano mu ishusho",
      body: "Iyo hari ikisaba umuganga, Ubuzima ikwereka neza ivuriro cyangwa umujyanama." },
    { icon: "globe", title: "Indimi ebyiri",
      body: "Hindura hagati y'Icyongereza n'Ikinyarwanda igihe cyose. Ubuzima yumva byombi." },
    { icon: "lock", title: "Ni ibyawe ubigenga",
      body: "Utamenyekana ku buryo busanzwe. Ibyihariro birabikwa mu ibanga, ushobora kubisiba." },
  ],
  stepsTitle: "Uko bikora",
  steps: [
    { title: "Ramutsa", body: "Hitamo izina ryo guhimba n'ururimi. Nta zina nyako cyangwa kwiyandikisha bisabwa." },
    { title: "Baza utagize uburakari", body: "Andika cyangwa uvuge ikibazo ku mubiri wawe, imibanire cyangwa ubuzima." },
    { title: "Bona ubufasha busobanutse", body: "Uhabwa igisubizo gishingiye ku kuri, n'ukwoherezwa ku mukozi w'ubuzima bimaze gukenerwa." },
  ],
  whyTitle: "Yubakiwe urubyiruko, yizewe",
  whyPoints: [
    "Ibisubizo biva gusa mu makuru yemewe kandi yasuzumwe n'abaganga",
    "Ntiyigera ikeka — ikwereka umukozi w'ubuzima iyo idafite ikizere",
    "Imenya igihirahiro n'ihohoterwa rishingiye ku gitsina, ikwereka ubufasha nyabwo",
    "Utamenyekana mbere; ibyihariro byawe birabikwa mu ibanga",
    "Ikora mu Cyongereza n'Ikinyarwanda, mu kiganiro no mu ijwi",
  ],
  whyStat: { value: "0", label: "kwiyandikisha bisabwa kugira utangire" },
  safetyTitle: "Kwita, atari igihirahiro",
  safetyBody:
    "Ubuzima imenya igihe ikibazo gisaba umuntu, atari porogaramu. Ku byihutirwa cyangwa umutekano, ikwereka umukozi w'ubuzima wizewe, kandi ku ihohoterwa, ikwereka Ikigo Isange One Stop Centre.",
  privacyTitle: "Ibanga ku buryo busanzwe",
  privacyBody:
    "Utangira utamenyekana. Amakuru yihariye uhitamo gusangiza abikwa mu ibanga, kandi ushobora gusiba byose igihe cyose.",
  faqTitle: "Ibibazo, bisubijwe",
  faqs: [
    { q: "Ese ni ibanga koko?", a: "Yego. Utangira utamenyekana, nta zina nyako risabwa, kandi ushobora gusiba amakuru yawe igihe cyose." },
    { q: "Ese ni ubuntu?", a: "Yego — Ubuzima ikoreshwa ku buntu ku makuru n'ubuyobozi bw'ubuzima." },
    { q: "Ese yasimbura umuganga?", a: "Oya. Ubuzima itanga amakuru asobanutse kandi ikwereka umukozi w'ubuzima igihe cyose bikenewe." },
    { q: "Ivuga izihe ndimi?", a: "Icyongereza n'Ikinyarwanda, mu kiganiro no mu ijwi — hindura igihe cyose." },
  ],
  partner: "Byubakanye na Health Development Initiative (HDI)",
  footerCta: "Twiteguye igihe cyose.",
  footerStart: "Fungura Ubuzima",
  footerTagline: "Umuyobozi w'ubuzima bw'imyororokere w'ibanga, w'urubyiruko, mu Rwanda.",
  footerCols: [
    { title: "Shakisha", links: ["Tangira ikiganiro", "Uko bikora", "Ibanga"] },
    { title: "Ingingo", links: ["Kuboneza urubyaro", "SIDA & STIs", "Gutwita", "Kwemeranya"] },
    { title: "Ubufasha", links: ["Shaka ivuriro", "Isange One Stop Centre", "Vugana n'umuntu"] },
  ],
  footerRights: "Ubuzima — ku bufatanye na Health Development Initiative.",
};

export const LANDING: Record<"en" | "rw", LandingCopy> = { en, rw };
