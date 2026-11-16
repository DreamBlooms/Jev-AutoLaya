import i18n from "i18next";
import LanguageDetector from "i18next-browser-languagedetector";
import { initReactI18next } from "react-i18next";

import en from "./locales/en.json";
import zh from "./locales/zh.json";

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh },
    },
    fallbackLng: "zh",
    supportedLngs: ["zh", "en"],
    nonExplicitSupportedLngs: true,
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator", "htmlTag"],
      lookupLocalStorage: "autolaya-lang",
      caches: ["localStorage"],
    },
  });

i18n.on("languageChanged", (language) => {
  const normalized = language.startsWith("zh") ? "zh" : "en";
  localStorage.setItem("autolaya-lang", normalized);
  document.documentElement.lang = normalized === "zh" ? "zh-CN" : "en";
});

export default i18n;
