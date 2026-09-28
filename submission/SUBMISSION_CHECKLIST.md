# Submission checklist (30 Sep 2026, 11:59 PM)

Form: https://forms.gle/C4u1ox5aQqaJsLuy5

Team name format: `SRM_<TeamName>_Theme2`

## Before submit

1. Rename `submission/SRM_TeamName_Submission_TEMPLATE.pptx` → `SRM_<YourTeam>_Submission.pptx` and fill all slides.
2. Fill `submission/LangAI3.0_AI_Disclosure.docx` with your details.
3. Record demo video (≤5 min): cold query → cache hit → paraphrase → unseen SIIS. Upload to YouTube/Drive; link in README.
4. Push public GitHub repo with everything in this `Project/` folder.
5. Create release tag on final commit:

```bash
git tag -a PRISM_GENAI_HACKATHON_Y2026 -m "PRISM Gen AI Hackathon Y2026 Final Submission"
git push origin PRISM_GENAI_HACKATHON_Y2026
```

6. Deploy Hugging Face Docker Space; add live URL to README.
7. Submit form with GitHub link (must include code, README, PPT, video link, disclosure, tag).

## Current automated score (local)

Run:

```bash
python scripts/build_results.py
python scripts/eval_local.py --url http://127.0.0.1:7860
```

See `metrics.md` for latest gate and block scores.

## Optional Gemini upgrade

With `GEMINI_API_KEY` in `.env`:

```bash
python scripts/build_results.py --use-llm
```

Then re-run eval and refresh metrics/PPT numbers.
