"""
match.py — AI Resume ↔ Job Description Matcher
=================================================
A small, real LLM-powered tool: it reads one or more resumes and a job
description, sends each pair to Claude with instructions to return a
structured evaluation, and prints a match score with strengths, gaps,
and a recommendation — ranked, if you're scoring more than one resume.

This is written to be READ, not just run. Comments explain each Python
concept as it shows up, since this is a learning project as much as a
working tool.

Single resume:
    python match.py --resume sample_data/resume.txt --job sample_data/job_description.txt

Batch mode — score every resume in a folder against one job, ranked by fit:
    python match.py --resumes-dir sample_data/resumes --job sample_data/job_description.txt

Batch mode, also saving a CSV you can open in Excel:
    python match.py --resumes-dir sample_data/resumes --job sample_data/job_description.txt --csv results.csv
"""

# --- Imports -----------------------------------------------------------
# `os` lets us read environment variables (like our API key) without
# hardcoding secrets into the file.
import os

# `json` turns text into Python dicts/lists and back. Claude will reply
# with a JSON string; we need to parse it into something Python can use.
import json

# `csv` writes rows of data out as a .csv file — the same format Excel
# and Google Sheets open natively. Useful any time you want to hand
# results to someone who lives in a spreadsheet.
import csv

# `argparse` builds a command-line interface: --resume, --job, etc.
import argparse

# `dataclass` is a shortcut for defining a simple class that just holds
# data (like a lightweight struct). Less boilerplate than writing
# __init__ by hand.
from dataclasses import dataclass

# `Path` (from the standard library's `pathlib`) represents a file or
# folder location and gives us convenient methods like ".glob()" to
# list files inside it — nicer to work with than raw strings of
# forward/backslashes.
from pathlib import Path

# `dotenv` reads a ".env" file and loads its contents as environment
# variables, so you don't have to `export` your API key in the terminal
# every time.
from dotenv import load_dotenv

# The official Anthropic Python SDK — this is what actually talks to
# Claude's API over HTTPS.
from anthropic import Anthropic


# --- A small data structure for our result ------------------------------
# @dataclass auto-generates __init__, __repr__, etc. for us. This just
# says "a MatchResult always has these four fields, with these types."
@dataclass
class MatchResult:
    score: int              # 0-100 fit score
    strengths: list[str]    # what matches well
    gaps: list[str]         # what's missing or weak
    recommendation: str     # one-line verdict


def read_text_file(path: str) -> str:
    """Read a file and return its contents as a string.

    `-> str` is a type hint: it tells readers (and editors/linters) this
    function returns a string. Python doesn't enforce it at runtime, but
    it's good documentation and catches bugs early.
    """
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def build_prompt(resume_text: str, job_text: str) -> str:
    """Build the instruction we send to Claude.

    This is prompt engineering: we're being explicit about the task,
    the inputs, and — critically — the exact output format we want, so
    we can reliably parse the response in Python afterward.
    """
    # An f-string (f"...") lets us drop variables directly into text
    # using {curly_braces}.
    return f"""You are an expert technical recruiter evaluating a candidate's
fit for a role.

JOB DESCRIPTION:
{job_text}

CANDIDATE RESUME:
{resume_text}

Evaluate the fit and respond with ONLY a JSON object (no other text,
no markdown code fences) matching this exact shape:

{{
  "score": <integer 0-100>,
  "strengths": [<short strings, 2-4 items>],
  "gaps": [<short strings, 1-3 items>],
  "recommendation": "<one sentence>"
}}
"""


def call_claude(prompt: str) -> str:
    """Send the prompt to Claude and return the raw text reply.

    `Anthropic()` reads the ANTHROPIC_API_KEY environment variable
    automatically — that's why we called load_dotenv() first, so the
    key from our .env file is available as an env var by the time we
    get here.
    """
    client = Anthropic()

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    # `message.content` is a list of content blocks (usually one, for
    # a plain text reply). We grab the text of the first block.
    return message.content[0].text


def strip_code_fence(text: str) -> str:
    """Remove a surrounding ```json ... ``` (or plain ``` ... ```) fence, if present.

    Even when a prompt explicitly says "no markdown code fences," LLMs
    sometimes wrap JSON in one anyway — it's not perfectly reliable
    instruction-following, and real code that talks to an LLM has to
    plan for that instead of assuming the model will always comply.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # drop the opening ``` or ```json line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # drop the closing ``` line
        text = "\n".join(lines).strip()
    return text


def parse_result(raw_text: str) -> MatchResult:
    """Turn Claude's JSON text reply into a MatchResult object.

    Wrapped in try/except because LLM output, even when asked for JSON,
    can occasionally be malformed — real-world AI engineering means
    handling that gracefully instead of letting the whole program crash.
    """
    cleaned = strip_code_fence(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Claude's reply wasn't valid JSON. Raw reply was:\n{raw_text}"
        ) from e

    return MatchResult(
        score=data["score"],
        strengths=data["strengths"],
        gaps=data["gaps"],
        recommendation=data["recommendation"],
    )


def evaluate_fit(resume_text: str, job_text: str) -> MatchResult:
    """Run the full pipeline for one resume: prompt -> Claude -> parsed result.

    This just chains together three functions we already had
    (build_prompt, call_claude, parse_result). Pulling that chain into
    its own function means both single-resume mode and batch mode can
    call this one thing instead of repeating the same three lines —
    a small example of not repeating yourself (often called "DRY").
    """
    prompt = build_prompt(resume_text, job_text)
    raw_reply = call_claude(prompt)
    return parse_result(raw_reply)


def find_resume_files(folder: str) -> list[Path]:
    """Return every .txt file in a folder, sorted by name.

    Path(folder).glob("*.txt") finds files matching a pattern — "*.txt"
    means "any name, ending in .txt". It returns them in arbitrary
    order, so we wrap it in sorted() to get a predictable, repeatable
    order (alphabetical by filename) every time we run this.
    """
    return sorted(Path(folder).glob("*.txt"))


def print_result(result: MatchResult) -> None:
    """Pretty-print a single result to the terminal."""
    print(f"\nMatch score: {result.score}/100\n")

    print("Strengths:")
    for item in result.strengths:
        print(f"  + {item}")

    print("\nGaps:")
    for item in result.gaps:
        print(f"  - {item}")

    print(f"\nRecommendation: {result.recommendation}\n")


def print_batch_summary(ranked: list[tuple[Path, MatchResult]]) -> None:
    """Print a ranked, one-line-per-candidate summary, best fit first.

    `ranked` is a list of (path, result) pairs, already sorted by score.
    We print a short table first, then the full detail for each
    candidate below it — the short table is what you'd actually scan
    when triaging a stack of resumes.
    """
    print("\n=== Ranked summary (best fit first) ===\n")
    for rank, (path, result) in enumerate(ranked, start=1):
        # enumerate(ranked, start=1) gives us both a 1-based counter
        # (rank) and each (path, result) pair, in one loop.
        print(f"{rank}. {path.name} — {result.score}/100")

    print("\n=== Full detail ===")
    for path, result in ranked:
        print(f"\n--- {path.name} ---")
        print_result(result)


def write_csv(ranked: list[tuple[Path, MatchResult]], output_path: str) -> None:
    """Write ranked results out to a CSV file for opening in Excel/Sheets.

    `newline=""` on the open() call is a Windows-specific quirk the csv
    module docs recommend — without it, CSV files written on Windows
    can end up with a blank line after every row.
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "resume_file", "score", "strengths", "gaps", "recommendation"])

        for rank, (path, result) in enumerate(ranked, start=1):
            writer.writerow([
                rank,
                path.name,
                result.score,
                # " | ".join(...) turns a list like ["a", "b"] into the
                # single string "a | b", since a CSV cell can't hold a
                # Python list directly.
                " | ".join(result.strengths),
                " | ".join(result.gaps),
                result.recommendation,
            ])

    print(f"\nSaved results to {output_path}")


def run_single(resume_path: str, job_text: str) -> None:
    """Handle the original single-resume mode."""
    resume_text = read_text_file(resume_path)
    result = evaluate_fit(resume_text, job_text)
    print_result(result)


def run_batch(resumes_dir: str, job_text: str, csv_path: str | None) -> None:
    """Handle batch mode: score every resume in a folder, then rank them."""
    resume_files = find_resume_files(resumes_dir)

    if not resume_files:
        print(f"No .txt resumes found in {resumes_dir}")
        return

    results: list[tuple[Path, MatchResult]] = []

    for path in resume_files:
        print(f"Scoring {path.name}...")
        try:
            resume_text = read_text_file(str(path))
            result = evaluate_fit(resume_text, job_text)
            results.append((path, result))
        except Exception as e:
            # If one resume fails (bad file, API hiccup, malformed
            # reply), we don't want that to kill the whole batch — log
            # it and move on to the rest.
            print(f"  Skipped {path.name}: {e}")

    if not results:
        print("No resumes were scored successfully.")
        return

    # sorted() with a `key` function: for each (path, result) pair, look
    # at result.score, and sort by that. reverse=True means highest
    # score first instead of Python's default lowest-first.
    ranked = sorted(results, key=lambda pair: pair[1].score, reverse=True)

    print_batch_summary(ranked)

    if csv_path:
        write_csv(ranked, csv_path)


def main() -> None:
    # Load variables from a local .env file (if present) into the
    # environment, so ANTHROPIC_API_KEY becomes readable by os.environ.
    # override=True makes .env always win over any stale system-level
    # environment variable of the same name.
    load_dotenv(override=True)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "No ANTHROPIC_API_KEY found.\n"
            "Copy .env.example to .env and paste in your real key, "
            "or set the environment variable directly."
        )
        return

    # Set up the command-line interface. Running `python match.py --help`
    # will show these options automatically.
    parser = argparse.ArgumentParser(description="Match resumes against a job description using Claude.")

    # A mutually exclusive group means: exactly one of these two options
    # must be given, never both, never neither (required=True enforces
    # "at least one"; add_mutually_exclusive_group enforces "not both").
    resume_source = parser.add_mutually_exclusive_group(required=True)
    resume_source.add_argument("--resume", help="Path to a single resume text file")
    resume_source.add_argument("--resumes-dir", help="Path to a folder of resume .txt files (batch mode)")

    parser.add_argument("--job", required=True, help="Path to a job description text file")
    parser.add_argument("--csv", help="Optional: path to save batch results as a CSV file")
    args = parser.parse_args()

    job_text = read_text_file(args.job)

    if args.resumes_dir:
        run_batch(args.resumes_dir, job_text, args.csv)
    else:
        run_single(args.resume, job_text)


# This is a common Python idiom: code here only runs when the file is
# executed directly (`python match.py`), not when it's imported by
# another script. Good practice for anything meant to be reusable.
if __name__ == "__main__":
    main()
