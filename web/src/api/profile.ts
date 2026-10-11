import { apiFetch } from "./client";
import type { Profile, ProfileUpdate } from "./types";

export const profile = {
  get: () => apiFetch<Profile>("/v1/profile"),
  put: (data: ProfileUpdate) => apiFetch<Profile>("/v1/profile", { method: "PUT", body: data }),
  wipe: () => apiFetch<void>("/v1/profile", { method: "DELETE" }),
};
