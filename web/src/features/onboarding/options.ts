import type { AgeBand } from "../../api/types";
import type { TKey } from "../../i18n/useT";

export const AGE_OPTIONS: [AgeBand, TKey][] = [
  ["under15", "obAgeUnder15"], ["15_17", "obAge1517"], ["18_19", "obAge1819"],
  ["20_24", "obAge2024"], ["25_plus", "obAge25"],
];
export const GENDERS: [string, TKey][] = [["female", "obGenderFemale"], ["male", "obGenderMale"], ["nonbinary", "obGenderNonbinary"]];
export const PRONOUNS = ["she/her", "he/him", "they/them"];
export const PRONOUN_KEYS: TKey[] = ["obPronounsShe", "obPronounsHe", "obPronounsThey"];
export const TONES: [string, TKey][] = [["casual", "obToneCasual"], ["gentle", "obToneGentle"], ["direct", "obToneDirect"]];
export const INTERESTS: [string, TKey][] = [
  ["sleep", "obInterestSleep"], ["stress", "obInterestStress"], ["relationships", "obInterestRelationships"],
  ["nutrition", "obInterestNutrition"], ["sexual_health", "obInterestSexualHealth"], ["fitness", "obInterestFitness"],
];
