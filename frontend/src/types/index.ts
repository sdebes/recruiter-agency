export interface Listing {
  id: string;
  title: string;
  company: string;
  url?: string;
  description: string;
  source?: string;
  location?: string;
  salary_range?: string;
  posted_date?: string;
  archetype?: string;
  seniority?: string;
  start_date?: string;
  employment_duration?: string;
  employment_type?: string;
  is_active: number;
  created_at: string;
}

export interface Evaluation {
  id: string;
  listing_id: string;
  cv_match_score: number;
  north_star_score: number;
  comp_score: number;
  culture_score: number;
  red_flags: string[]; // Decoded from JSON array
  global_score: number;
  legitimacy: string;
  archetype_detected: string;
  detailed_notes?: string;
  report_path?: string;
  created_at: string;
}

export interface Application {
  id: string;
  listing_id?: string;
  company: string;
  role: string;
  status: 'Evaluated' | 'Applied' | 'Responded' | 'Interview' | 'Offer' | 'Rejected' | 'Discarded' | 'SKIP';
  score?: number;
  applied_date?: string;
  interview_dates: string[]; // Decoded from JSON array
  notes?: string;
  tailored_cv_path?: string;
  cover_letter_path?: string;
  report_link?: string;
  created_at: string;
  updated_at: string;
}

export interface TailoredCV {
  id: string;
  listing_id: string;
  cv_path: string;
  commentary?: string;
  google_doc_url?: string;
  resume_builder_url?: string;
  created_at: string;
}

export interface CandidateProfile {
  full_name: string;
  email: string;
  location: string;
  visa_status: string;
  linkedin: string;
  github: string;
}

export interface TargetRoles {
  primary: string[];
  secondary: string[];
}

export interface CompensationProfile {
  target_range: string;
  currency: string;
  minimum: string;
}

export interface SearchPreferences {
  country: string;
  cities: string;
}

export interface Profile {
  candidate: CandidateProfile;
  target_roles: TargetRoles;
  compensation: CompensationProfile;
  search_preferences: SearchPreferences;
}

export interface ScoringWeights {
  cv_match: number;
  north_star: number;
  compensation: number;
  culture: number;
  red_flags: number;
}

export interface Archetype {
  name: string;
  keywords: string[];
  scoring_weights: ScoringWeights;
  seniority_levels: string[];
}

export interface PipelineStats {
  total: number;
  by_status: Record<string, number>;
  avg_score: number;
}
