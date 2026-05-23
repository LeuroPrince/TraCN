import type {
  Direction,
  DirectionCategory,
  LlmConfig,
  LlmConfigCreate,
  MatchProfileResponse,
  ReclassifyTeachersResponse,
  TeacherDetail,
  TeacherSummary
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  directions: () => request<Direction[]>("/api/directions"),
  directionCategories: () => request<DirectionCategory[]>("/api/direction-categories"),
  reclassifyTeachers: () =>
    request<ReclassifyTeachersResponse>("/api/teachers/reclassify", {
      method: "POST"
    }),
  updateDirection: (id: number, weight: number) =>
    request<Direction>(`/api/directions/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weight })
    }),
  teachers: (status: string, q: string, direction: string) => {
    const params = new URLSearchParams({ status });
    if (q) params.set("q", q);
    if (direction) params.set("direction", direction);
    return request<TeacherSummary[]>(`/api/teachers?${params.toString()}`);
  },
  teacher: (id: number) => request<TeacherDetail>(`/api/teachers/${id}`),
  updateStatus: (id: number, status: string) =>
    request<TeacherDetail>(`/api/teachers/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status })
    }),
  importCsv: (file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<{ imported: number }>("/api/ingest/csv", { method: "POST", body: form });
  },
  urlPreview: (sourceUrl: string) => {
    const form = new FormData();
    form.set("source_url", sourceUrl);
    return request<{ url: string; title: string; text_preview: string }>("/api/ingest/url-preview", {
      method: "POST",
      body: form
    });
  },
  llmConfig: () => request<LlmConfig>("/api/llm/config"),
  llmConfigs: () => request<LlmConfig[]>("/api/llm/configs"),
  createLlmConfig: (payload: LlmConfigCreate) =>
    request<LlmConfig>("/api/llm/configs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }),
  selectLlmConfig: (id: number | string) =>
    request<LlmConfig>(`/api/llm/configs/${id}/select`, {
      method: "PATCH"
    }),
  testLlm: () => request<{ ok: boolean; message: string }>("/api/llm/config/test", { method: "POST" }),
  testLlmConfig: (id: number | string) =>
    request<{ ok: boolean; message: string }>(`/api/llm/configs/${id}/test`, { method: "POST" }),
  matchProfile: (file: File) => {
    const form = new FormData();
    form.set("file", file);
    return request<MatchProfileResponse>("/api/match/profile", { method: "POST", body: form });
  }
};
