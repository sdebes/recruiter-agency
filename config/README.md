# Documents

Source documents for resume and cover letter tailoring. Place your files here so the resume-tailer agent can reference them.

## What goes here

- **resume.md** — Your master/base resume (full version). The resume-tailer agent reads this and generates tailored versions based on the target job description.
- **cover-letter-template.md** — Your cover letters.
- Any other reference documents (reference letters, transcripts, certifications) that should inform your tailored applications.

## What does NOT go here

- Generated/tailored PDFs → `output/`
- Writing samples for style calibration → `writing-samples/`
- Interview prep materials → `interview-prep/`
- Job descriptions → `jds/`

## Usage

When running resume-tailoring workflows, the agent will read from this folder to understand your base materials, then tailor them to the target role and store results in `output/`.
