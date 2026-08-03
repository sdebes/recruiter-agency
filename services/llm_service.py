# Recruiter Agency - LLM Service
#
# Wraps the Gemini API for consistent model access across all agents.
# Handles API key management, model selection by task, and error handling.

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

class LLM_models:
    evaluater = "gemini-3.5-flash-lite"
    cv_tailor = "gemini-3.5-flash"
    cover_letter_writer = "gemini-3.5-flash"
    default = "gemini-3.5-flash-lite"

# Find project root and load .env
def _load_env():
    current = os.path.abspath(os.path.dirname(__file__))
    while current != os.path.dirname(current):
        env_path = os.path.join(current, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
            return True
        current = os.path.dirname(current)
    load_dotenv() # Fallback
    return False

_load_env()

from utils.config_loader import get_cv_text


class LLMService:
    """Manages LLM calls for the recruiter agency pipeline.

    Model selection by task:
      - Archetype detection: flash-lite (fast, cheap)
      - A-F evaluation: flash (needs reasoning)
      - CV tailoring (high-score): flash (good quality)
      - CV tailoring (low-score): flash-lite
      - Interview prep: flash
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the LLM service.
        
        Uses Gemini (free tier) first, falls back to DeepSeek on OpenRouter (paid).
        """
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        
        if not self.api_key and not self.openrouter_key:
            raise ValueError(
                "Neither OPENROUTER_API_KEY nor GEMINI_API_KEY set. "
                "Please set at least one in your .env file."
            )
        
        self.client = None
        # Pre-init Gemini if key is available (catches missing pip package early)
        if self.api_key:
            try:
                self._init_client()
            except Exception:
                pass  # Will retry on first use

    def _init_client(self):
        """Initialize the Gemini client."""
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "google-genai package not installed. Run: pip install google-genai"
            )

    def _call_openrouter(
        self,
        model: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        """Call OpenRouter API. Tries multiple API URLs in case of endpoint changes."""
        if not self.openrouter_key:
            raise ValueError("OpenRouter API key not set.")

        import httpx
        
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "https://recruiter-agency.local",
            "X-Title": "Recruiter Agency",
        }
        
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        
        # List of possible OpenRouter API URLs to try
        urls = [
            "https://openrouter.ai/api/v1/chat/completions",
            "https://openrouter.ai/v1/chat/completions",
            "https://openrouter.ai/api/chat/completions",
            "https://api.openrouter.ai/v1/chat/completions",
        ]
        
        last_error = None
        for url in urls:
            try:
                with httpx.Client() as client:
                    response = client.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=60.0
                    )
                    if response.status_code != 200:
                        print(f"[llm] OpenRouter error {response.status_code} from {url} (model={model}): {response.text}")
                    response.raise_for_status()
                    return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print(f"[llm] OpenRouter call to {url} with model {model} failed: {e}")
                last_error = e
                continue
        
        raise last_error or RuntimeError("All OpenRouter endpoints failed")

    def _call(
        self,
        model: str,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        """Make a single LLM call. Uses Gemini (free) first, falls back to DeepSeek on OpenRouter (paid)."""
        last_error = None
        
        # 1. Try Gemini first (free tier)
        if self.api_key:
            try:
                if not self.client:
                    self._init_client()
                    
                kwargs = dict(
                    model=model,
                    contents=prompt,
                    config={
                        "temperature": temperature,
                        "max_output_tokens": 4096,
                    },
                )
                if system_instruction:
                    kwargs["config"]["system_instruction"] = system_instruction

                response = self.client.models.generate_content(**kwargs)
                return response.text
                
            except Exception as e:
                error_str = str(e)
                is_quota = any(tag in error_str for tag in ["429", "RESOURCE_EXHAUSTED", "quota"])
                quota_hint = " (quota exhausted)" if is_quota else ""
                print(f"[llm] Gemini failed{quota_hint}: {e}")
                last_error = e
                # Fall through to OpenRouter

        # 2. Fallback to DeepSeek on OpenRouter (paid)
        if self.openrouter_key:
            print(f"[llm] Falling back to DeepSeek on OpenRouter")
            try:
                return self._call_openrouter(
                    model="deepseek/deepseek-v4-flash",
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                )
            except Exception as e:
                print(f"[llm] OpenRouter DeepSeek fallback also failed: {e}")
                last_error = e
                raise e

        # 3. Nothing worked and no fallback available
        if self.api_key:
            raise Exception(
                f"Gemini error: {last_error}\n\n"
                "Suggestions:\n"
                "1. Wait for free tier quota to reset\n"
                "2. Add OPENROUTER_API_KEY=<your-key> to .env as a paid fallback"
            ) from last_error
        else:
            raise Exception(
                "All API calls failed. Make sure at least one of GEMINI_API_KEY or OPENROUTER_API_KEY is set."
            ) from last_error

    # ── Archetype Detection ──────────────────────────────────────────────

    def detect_archetype(
        self, jd_text: str, archetypes_config: Dict[str, Any]
    ) -> str:
        """Classify a job description into one of the configured archetypes.

        Uses flash-lite for fast, cheap classification.
        """
        archetype_names = [a["name"] for a in archetypes_config.get("archetypes", [])]
        prompt = f"""Given this job description, classify it into exactly one of these archetypes:
{', '.join(archetype_names)}

Also provide the detected seniority level (Junior, Mid, or Senior).

Respond in this exact format:
ARCHETYPE: <name>
SENIORITY: <level>

Job Description:
{jd_text[:4000]}"""
        result = self._call("gemini-3.1-flash-lite", prompt, temperature=0.2)
        return result.strip()

    # ── A-F Evaluation ───────────────────────────────────────────────────

    def evaluate_listing(
        self,
        jd_text: str,
        cv_text: str,
        profile: Dict[str, Any],
        archetype: str,
        archetype_weights: Dict[str, float],
    ) -> str:
        """Run a full A-F evaluation of a job listing against the user's CV.

        Returns structured markdown with all scoring blocks.
        """
        target_roles = profile.get("target_roles", {})
        comp = profile.get("compensation", {})
        narrative = profile.get("narrative", {})
        superpowers = "\n".join(f"- {s}" for s in narrative.get("superpowers", []))
        proof_points = "\n".join(
            f"- {p.get('title', '')}: {p.get('metric', '')} ({p.get('context', '')})"
            for p in narrative.get("proof_points", [])
        )

        prompt = f"""You are a career evaluation expert. Evaluate this job listing against the candidate's profile.

## Candidate Profile
- Target roles (primary): {', '.join(target_roles.get('primary', []))}
- Target roles (secondary): {', '.join(target_roles.get('secondary', []))}
- Superpowers: {superpowers}
- Key proof points: {proof_points}
- Compensation target: {comp.get('target_range', '')} {comp.get('currency', '')}
- Location flexibility: {comp.get('location_flexibility', '')}
- Detected archetype: {archetype}

## Scoring Weights (for {archetype})
- CV Match: {archetype_weights.get('cv_match', 0.25) * 100}%
- North Star Alignment: {archetype_weights.get('north_star', 0.20) * 100}%
- Compensation: {archetype_weights.get('compensation', 0.20) * 100}%
- Culture/Fit: {archetype_weights.get('culture', 0.20) * 100}%
- Red Flags: {archetype_weights.get('red_flags', 0.15) * 100}%

## Candidate's CV (excerpts):
{cv_text[:3000]}

## Job Description:
{jd_text[:4000]}

Provide your evaluation in this exact format:

**Archetype Detected:** {archetype}

**Block A — Role Summary:**
- Domain:
- Seniority Level:
- Remote/On-site:
- Key Technologies Required:

**Block B — CV Match Score: [X.X/5]**
For each key requirement in the JD, state whether it matches the CV. Provide the score as: (matched_requirements / total_requirements) * 5.

**Block C — North Star Alignment: [X.X/5]**
Rate how well this role aligns with the candidate's target archetypes.

**Block D — Compensation Score: [X.X/5]**
Evaluate the compensation against the candidate's target range.

**Block E — Culture/Fit Score: [X.X/5]**
Evaluate location, company stage, industry, and culture fit.

**Block F — Red Flags:**
List any red flags or concerns.

**Global Score: [X.X/5]**
(Weighted average using the scoring weights above)

**Legitimacy:** [High Confidence | Proceed with Caution | Suspicious]
Brief justification.

**Recommendation:** [Apply immediately | Worth applying | Apply only if specific reason | Recommend against applying]
"""
        return self._call("gemini-3.1-flash-lite", prompt, temperature=0.3)

    # ── CV Tailoring ─────────────────────────────────────────────────────

    def tailor_cv(
        self, jd_text: str, cv_text: str, company: str, role: str
    ) -> str:
        """Generate a tailored CV for a specific job listing."""
        prompt = f"""You are a professional CV writer. Tailor the candidate's CV for a specific job.

Rules:
1. NEVER invent experience or metrics the candidate doesn't have
2. NEVER add skills the candidate hasn't listed
3. Rephrase existing experience using keywords from the job description
4. Reorder bullet points to match JD priorities
5. Keep all facts, dates, and metrics accurate
6. Output in clean markdown

Target: {role} at {company}

Job Description:
{jd_text[:3000]}

Candidate's CV:
{cv_text}

Produce a tailored version of this CV optimized for ATS systems and the specific role."""
        return self._call("gemini-3.1-flash-lite", prompt, temperature=0.4)

    def critique_cv(
        self, jd_text: str, cv_text: str, company: str, role: str
    ) -> str:
        """Critique the candidate's CV against a specific job description."""
        prompt = f"""You are an expert technical recruiter and resume reviewer.
Provide a constructive, highly detailed critique of the candidate's CV in context of the target job description:

Role: {role} at {company}

Analyze the following:
1. **Critical Skill Gaps**: What key technologies, frameworks, or experience items mentioned in the JD are missing or weak in the CV?
2. **Impact & Metrics**: Are the bullet points sufficiently metric-driven (e.g. STAR methodology, results)? Identify bullet points that feel generic and suggest how to add impact.
3. **ATS Alignment & Keywords**: Which high-value terms from the JD should be included to pass automatic filters?
4. **Actionable Edits**: Provide 3-5 specific, drop-in phrasing or content suggestions.

Job Description:
{jd_text[:3000]}

Candidate's CV:
{cv_text}

Provide your feedback in clean, structured markdown with clear headings, bullet points, and bold text. Avoid generic advice; focus exclusively on the specific gaps between this CV and this JD."""
        return self._call("gemini-3.1-flash-lite", prompt, temperature=0.45)

    # ── Cover Letter Generation ──────────────────────────────────────────

    def generate_cover_letter(
        self, jd_text: str, cv_text: str, company: str, role: str
    ) -> str:
        """Generate a tailored cover letter for a specific job listing."""
        prompt = f"""Write a professional cover letter for the following job application.

Rules:
1. Keep it to one page
2. Map specific proof points from the CV to job requirements
3. Never invent experience or metrics
4. Professional but not robotic tone
5. Mention the specific company and role

Role: {role} at {company}

Job Description:
{jd_text[:3000]}

CV:
{cv_text[:2000]}"""
        return self._call("gemini-3.1-flash-lite", prompt, temperature=0.5)

    # ── Interview Prep ───────────────────────────────────────────────────

    def generate_interview_questions(
        self, jd_text: str, company: str, role: str
    ) -> str:
        """Generate likely interview questions based on a job description."""
        prompt = f"""Generate 10 likely interview questions for this role.

For each question:
1. The specific question
2. What the interviewer is looking for
3. How the candidate should prepare

Role: {role} at {company}

Job Description:
{jd_text[:3000]}"""
        return self._call("gemini-3.1-flash-lite", prompt, temperature=0.4)

    def select_star_stories(
        self, jd_text: str, story_bank: List[Dict[str, str]]
    ) -> str:
        """Select the best STAR stories from the story bank for a given JD."""
        stories_text = "\n\n".join(
            f"### {s.get('title', 'Untitled')}\n"
            f"S: {s.get('situation', '')}\n"
            f"T: {s.get('task', '')}\n"
            f"A: {s.get('action', '')}\n"
            f"R: {s.get('result', '')}\n"
            f"Tags: {', '.join(s.get('tags', []))}"
            for s in story_bank
        )
        prompt = f"""From this story bank, select the 3-5 most relevant stories for this job.

For each selected story, explain WHY it's relevant and how to present it.

Job Description:
{jd_text[:3000]}

Story Bank:
{stories_text}"""
        return self._call("gemini-3.1-flash-lite", prompt, temperature=0.3)

    # ── Utility ──────────────────────────────────────────────────────────

    def summarize_jd(self, jd_text: str) -> Dict[str, Any]:
        """Extract structured information and a clean description from raw job page text."""
        prompt = f"""Extract structured information from this job description.
Return ONLY a valid JSON object with the following fields:
- company: (string) The organization or company name that is hiring. Example: "Google", "Novartis", "Grundfos A/S", "ETH Zürich". NOT a person or job title.
- position: (string) The job title or role being offered. Example: "Software Engineer", "Senior Product Manager", "Systems Engineer", "Sales Associate". NOT the company name.
- seniority: (string: Junior, Mid, Senior, or Not specified)
- location: (string)
- salary: (string or number as string)
- start_date: (string, e.g. DD.MM.YYYY)
- employment duration: (string, e.g. 12 months, permanent)
- employment type: (string, e.g. Full-time, Part-time, Contract)
- cleaned_description: (string) The actual job description content only. Strip out all navigation, headers, footers, cookie banners, login prompts, site chrome, related jobs, and any other non-description boilerplate. Return just the relevant job posting text.

If a field is not found, use "Not specified".
IMPORTANT: Do NOT confuse company with position. The company is the employer (the organization hiring). The position is the job title (the role being offered). Make sure they are not swapped.

Job Description:
{jd_text[:5000]}"""
        
        import json
        try:
            result = self._call("gemini-3.1-flash-lite", prompt, temperature=0.1)
            # Clean up potential markdown formatting
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].strip()
            
            return json.loads(result)
        except Exception as e:
            print(f"[llm] Failed to parse JD JSON: {e}")
            return {
                "company": "Unknown",
                "position": "Unknown",
                "seniority": "Not specified",
                "location": "Not specified",
                "salary": "Not specified",
                "start_date": "Not specified",
                "employment duration": "Not specified",
                "employment type": "Not specified",
                "cleaned_description": "",
            }