# AI Resume ↔ Job Matcher

A small hands-on project for learning to build with LLMs in Python. It
sends a resume and a job description to Claude and gets back a
structured fit evaluation (score, strengths, gaps, recommendation).

This ties recruiting/TA experience to a real LLM-building skill — the
kind of project worth mentioning in interviews for AI-adjacent roles.

## Setup (one time)

1. **Install Python 3.10+** if you don't already have it (check with
   `python3 --version` in a terminal).

2. **Install the dependencies:**

   ```
   pip install -r requirements.txt
   ```

3. **Get an Anthropic API key:**
   Go to https://console.anthropic.com/settings/keys, create a key.
   (New accounts get a small amount of free credit; after that it's
   pay-as-you-go — this project uses a tiny amount per run, well under
   a cent.)

4. **Set your key:**

   ```
   cp .env.example .env
   ```

   Then open `.env` in any text editor and paste your real key in place
   of `sk-ant-your-key-here`.

## Run it

```
python match.py --resume sample_data/resume.txt --job sample_data/job_description.txt
```

Try swapping in your own resume and a real job posting (save each as a
plain `.txt` file) to see how it scores.

## What this teaches

- Calling an LLM API from Python (the `anthropic` SDK)
- Prompt engineering for structured (JSON) output, not just chat text
- Parsing and validating LLM output safely (`try/except`, `json.loads`)
- Basic CLI design with `argparse`
- Light use of `dataclasses` for clean data structures
- Reading secrets from environment variables instead of hardcoding them

## Where this can go next

- Swap in resumes/job descriptions from real files (PDF, DOCX)
- Batch-score many candidates against one job at once
- Add a simple web UI (Streamlit is the fastest path)
- Track scored candidates in a small database
- Add automated tests for `parse_result`

See the roadmap Claude shared in chat for the fuller skill-building path.
