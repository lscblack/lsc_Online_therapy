const en = {
  appName: "Ubuzima",
  greeting: "Muraho! How can I help you today?",
  navHome: "Home",
  navChat: "Chat",
  navAdmin: "Admin",
  send: "Send",
  settings: "Settings",
  login: "Log in",
  logout: "Log out",
  language: "Language",
  switchToLang: "Kinyarwanda",
  theme: "Theme",
  themeLight: "Light",
  themeDark: "Dark",
  adminTitle: "Admin panel",
  adminPlaceholder: "Coming soon.",
} as const;

export type Dict = Record<keyof typeof en, string>;
export default en as Dict;
