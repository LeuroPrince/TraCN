export type Direction = {
  id: number;
  key: string;
  name: string;
  weight: number;
  description: string;
  sort_order: number;
};

export type DirectionMatch = {
  id: number;
  direction_id: number;
  direction_key: string;
  direction_name: string;
  effective_weight: number;
  evidence_sentence: string;
};

export type TeacherSummary = {
  id: number;
  name: string;
  avatar_url?: string | null;
  institution: string;
  department?: string | null;
  city?: string | null;
  latitude?: number | null;
  title?: string | null;
  homepage_url?: string | null;
  lab_url?: string | null;
  email?: string | null;
  status: string;
  bio: string;
  match_score: number;
  primary_direction_key?: string | null;
  primary_direction_name?: string | null;
  evidence_sentence?: string | null;
  directions: DirectionMatch[];
};

export type TeacherDetail = TeacherSummary & {
  phone?: string | null;
  publications: Publication[];
  grants: Grant[];
  sources: SourceEvidence[];
};

export type Publication = {
  id: number;
  title: string;
  year?: number | null;
  authors?: string | null;
  venue?: string | null;
  source_url?: string | null;
  doi_url?: string | null;
  scholar_url?: string | null;
  is_official_source: boolean;
};

export type Grant = {
  id: number;
  name: string;
  year?: number | null;
  funder?: string | null;
  source_url?: string | null;
};

export type SourceEvidence = {
  id: number;
  source_url: string;
  source_type: string;
  field_name?: string | null;
  quote?: string | null;
  trust_level: number;
};

export type LlmConfig = {
  id?: number | string | null;
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key_env_name: string;
  has_api_key: boolean;
  is_active: boolean;
  is_env: boolean;
};

export type LlmConfigCreate = {
  name: string;
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
};

export type TeacherMatchResult = {
  teacher: TeacherSummary;
  total_score: number;
  direction_score: number;
  ai_score: number;
  reason: string;
};

export type MatchProfileResponse = {
  profile_id: number;
  extracted_summary: string;
  results: TeacherMatchResult[];
};

export type DirectionCategory = {
  direction: Direction;
  teachers: TeacherSummary[];
};

export type TeacherReclassifyResult = {
  teacher_id: number;
  teacher_name: string;
  direction_keys: string[];
  evidence_sentence: string;
};

export type ReclassifyTeachersResponse = {
  updated: number;
  results: TeacherReclassifyResult[];
};
