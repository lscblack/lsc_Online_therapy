// Bilingual landing copy kept local (not in the strict i18n Dict) so marketing prose can evolve
// without forcing a matching key into every screen's dictionary.
export interface LandingCopy {
  heroBadge: string;
  heroTitle: string;
  heroSub: string;
  ctaStart: string;
  ctaLearn: string;
  stats: { value: string; label: string }[];
  featuresTitle: string;
  features: { icon: string; title: string; body: string }[];
  stepsTitle: string;
  steps: { title: string; body: string }[];
  safetyTitle: string;
  safetyBody: string;
  privacyTitle: string;
  privacyBody: string;
  partner: string;
  footerCta: string;
  footerStart: string;
}

const en: LandingCopy = {
  heroBadge: "SRHR health navigator • Rwanda",
  heroTitle: "Private answers about your health, in your language.",
  heroSub:
    "Ubuzima is a youth-friendly companion for sexual and reproductive health. Ask anything by chat or voice, in English or Kinyarwanda — and get clear, judgement-free answers drawn from reviewed health information.",
  ctaStart: "Start chatting",
  ctaLearn: "How it works",
  stats: [
    { value: "EN + RW", label: "English & Kinyarwanda" },
    { value: "100%", label: "Private & anonymous" },
    { value: "Reviewed", label: "Answers from approved sources" },
    { value: "24/7", label: "Always available" },
  ],
  featuresTitle: "What Ubuzima can do",
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
  safetyTitle: "Care, not crisis",
  safetyBody:
    "Ubuzima recognises when a question needs a person, not an app. For anything urgent or about safety, it points you to a trusted health worker and, for violence, to Rwanda's Isange One Stop Centres.",
  privacyTitle: "Private by default",
  privacyBody:
    "You start anonymous. Sensitive details you choose to share are encrypted at rest, and you can delete everything from your device and our servers at any time.",
  partner: "Built with Health Development Initiative (HDI)",
  footerCta: "Ready when you are.",
  footerStart: "Open Ubuzima",
};

const rw: LandingCopy = {
  heroBadge: "Umuyobozi w'ubuzima bw'imyororokere • u Rwanda",
  heroTitle: "Ibisubizo by'ibanga ku buzima bwawe, mu rurimi rwawe.",
  heroSub:
    "Ubuzima ni inshuti y'urubyiruko ku buzima bw'imyororokere. Baza ikibazo cyose ukoresheje ikiganiro cyangwa ijwi, mu Cyongereza cyangwa Ikinyarwanda — uhabwe ibisubizo byumvikana, bitagucira urubanza, bishingiye ku makuru y'ubuzima yasuzumwe.",
  ctaStart: "Tangira ikiganiro",
  ctaLearn: "Uko bikora",
  stats: [
    { value: "EN + RW", label: "Icyongereza & Ikinyarwanda" },
    { value: "100%", label: "Ibanga kandi utamenyekana" },
    { value: "Byasuzumwe", label: "Ibisubizo biva mu nkomoko zemewe" },
    { value: "24/7", label: "Bihari igihe cyose" },
  ],
  featuresTitle: "Icyo Ubuzima ishobora gukora",
  features: [
    { icon: "chat", title: "Ikiganiro ku buryo bwawe",
      body: "Baza ibibazo by'ubuzima mu magambo yoroshye uhabwe igisubizo gituje, cyumvikana — nta rurimi rukomeye, nta rubanza." },
    { icon: "mic", title: "Vuga mu ijwi",
      body: "Ukunda kuvuga? Koresha ijwi mu kubaza no kumva igisubizo, nta kwandika." },
    { icon: "book", title: "Gishingiye ku nkomoko nyazo",
      body: "Ibisubizo biva mu nyandiko z'ubuzima zasuzumwe na Health Development Initiative — ntabwo byahimbwe." },
    { icon: "shield", title: "Umutekano mu ishusho",
      body: "Iyo hari ikisaba umuganga, Ubuzima ikwereka neza ivuriro cyangwa umujyanama." },
    { icon: "globe", title: "Indimi ebyiri",
      body: "Hindura hagati y'Icyongereza n'Ikinyarwanda igihe cyose. Ubuzima yumva byombi." },
    { icon: "lock", title: "Ni ibyawe ubigenga",
      body: "Utamenyekana ku buryo busanzwe. Ibyihariro birabikwa mu ibanga, ushobora kubisiba igihe ushakiye." },
  ],
  stepsTitle: "Uko bikora",
  steps: [
    { title: "Ramutsa", body: "Hitamo izina ryo guhimba n'ururimi. Nta zina nyako cyangwa kwiyandikisha bisabwa." },
    { title: "Baza utagize uburakari", body: "Andika cyangwa uvuge ikibazo ku mubiri wawe, imibanire cyangwa ubuzima bwawe." },
    { title: "Bona ubufasha busobanutse", body: "Uhabwa igisubizo gishingiye ku kuri, n'ukwoherezwa ku mukozi w'ubuzima igihe bikenewe." },
  ],
  safetyTitle: "Kwita, atari igihirahiro",
  safetyBody:
    "Ubuzima imenya igihe ikibazo gisaba umuntu, atari porogaramu. Ku byihutirwa cyangwa umutekano, ikwereka umukozi w'ubuzima wizewe, kandi ku ihohoterwa, ikwereka Ikigo Isange One Stop Centre.",
  privacyTitle: "Ibanga ku buryo busanzwe",
  privacyBody:
    "Utangira utamenyekana. Amakuru yihariye uhitamo gusangiza abikwa mu ibanga, kandi ushobora gusiba byose ku gikoresho cyawe no kuri seriveri zacu igihe cyose.",
  partner: "Byubakanye na Health Development Initiative (HDI)",
  footerCta: "Twiteguye igihe cyose.",
  footerStart: "Fungura Ubuzima",
};

export const LANDING: Record<"en" | "rw", LandingCopy> = { en, rw };
