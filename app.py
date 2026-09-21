"""
app.py — Streamlit web UI for the AI Resume ↔ Job Matcher
=============================================================
The exact same scoring logic as match.py, wrapped in a clickable
browser page instead of a terminal command. Notice this file does NOT
redefine build_prompt / call_claude / parse_result / evaluate_fit — it
imports them from match.py and reuses them. That's the payoff of
having pulled that logic into its own functions earlier: the same
"brain" now powers two different front ends (a CLI and a web UI)
without copy-pasting a single line of the actual LLM-calling code.

Run it with:
    streamlit run app.py

That starts a local web server and opens a browser tab automatically.
"""

# --- Imports -------------------------------------------------------------
# `io` gives us StringIO — an in-memory "fake file" we can write CSV
# text into without ever touching the real filesystem. Useful here
# because the CSV only needs to exist long enough to hand to the
# browser as a download, not to be saved on disk by our own code.
import io
import csv
import os

# `streamlit` is the library that turns this plain Python script into
# a web app. Every st.something() call adds one piece to the page,
# top to bottom, in the order you call it.
import streamlit as st

from dotenv import load_dotenv

# Reusing our own code from match.py instead of rewriting it here.
from match import evaluate_fit, MatchResult


# --- Page setup ------------------------------------------------------------
load_dotenv(override=True)

st.set_page_config(page_title="AI Resume Matcher", page_icon="🧑‍💼")
st.title("AI Resume ↔ Job Matcher")
st.write(
    "Upload a job description and one or more resumes (.txt files) to get "
    "an AI-scored, ranked fit evaluation for each candidate."
)

# Fail fast with a clear message if there's no API key, instead of
# letting the user click "Score" and get a confusing error later.
if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error(
        "No ANTHROPIC_API_KEY found. Copy .env.example to .env, add your "
        "real key, and restart this app (Ctrl+C in the terminal, then "
        "`streamlit run app.py` again)."
    )
    st.stop()  # st.stop() halts the script here — nothing below it runs.


# --- Inputs ------------------------------------------------------------
# st.file_uploader returns None until the user picks a file, then an
# "UploadedFile" object (behaves like a file, but lives in memory).
job_file = st.file_uploader("Job description", type="txt")

# accept_multiple_files=True makes this return a LIST of UploadedFile
# objects (empty list if none chosen yet) — this is what lets one
# resume or twenty resumes both work through the exact same code path.
resume_files = st.file_uploader(
    "Resume(s) — select one file for a single evaluation, or several for a ranked batch",
    type="txt",
    accept_multiple_files=True,
)

# The button is disabled until both a job description and at least one
# resume have been uploaded, so there's nothing to click prematurely.
score_clicked = st.button(
    "Score candidates",
    disabled=not (job_file and resume_files),
)


def read_uploaded_text(uploaded_file) -> str:
    """Turn a Streamlit UploadedFile into plain text.

    Uploaded files come through as raw bytes (b"..."), not a Python
    str — .decode("utf-8") converts those bytes into text we can pass
    to our existing functions, which all expect plain strings.
    """
    return uploaded_file.read().decode("utf-8")


def results_to_csv_text(ranked: list[tuple[str, MatchResult]]) -> str:
    """Build a CSV file's contents as a string, entirely in memory.

    This mirrors write_csv() in match.py, but writes into an io.StringIO
    (an in-memory buffer) instead of a real file on disk, since
    st.download_button just needs the text/bytes to offer for download —
    there's no need to save a file locally first.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["rank", "resume_file", "score", "strengths", "gaps", "recommendation"])

    for rank, (name, result) in enumerate(ranked, start=1):
        writer.writerow([
            rank,
            name,
            result.score,
            " | ".join(result.strengths),
            " | ".join(result.gaps),
            result.recommendation,
        ])

    return buffer.getvalue()


# --- Scoring, when the button is clicked --------------------------------
if score_clicked:
    job_text = read_uploaded_text(job_file)

    results: list[tuple[str, MatchResult]] = []

    # st.progress draws a progress bar we update as we go, so the user
    # sees movement instead of a frozen page while each API call runs.
    progress_bar = st.progress(0.0)

    for i, resume_file in enumerate(resume_files):
        resume_text = read_uploaded_text(resume_file)
        try:
            result = evaluate_fit(resume_text, job_text)
            results.append((resume_file.name, result))
        except Exception as e:
            # Same "don't let one bad resume kill the batch" idea as
            # the CLI version, but shown as a small warning banner
            # instead of a printed line.
            st.warning(f"Skipped {resume_file.name}: {e}")

        progress_bar.progress((i + 1) / len(resume_files))

    progress_bar.empty()  # remove the progress bar once done

    if not results:
        st.error("No resumes were scored successfully.")
    else:
        ranked = sorted(results, key=lambda pair: pair[1].score, reverse=True)

        st.subheader("Ranked results")

        # st.dataframe renders a nice sortable table from a list of
        # dicts — one dict per row, keys become column headers.
        table_rows = [
            {"Rank": i, "Resume": name, "Score": result.score}
            for i, (name, result) in enumerate(ranked, start=1)
        ]
        st.dataframe(table_rows, hide_index=True, use_container_width=True)

        # One collapsible section per candidate with the full detail —
        # st.expander keeps the page tidy when there are many resumes.
        for i, (name, result) in enumerate(ranked, start=1):
            with st.expander(f"{i}. {name} — {result.score}/100"):
                st.markdown("**Strengths**")
                for item in result.strengths:
                    st.write(f"- {item}")

                st.markdown("**Gaps**")
                for item in result.gaps:
                    st.write(f"- {item}")

                st.markdown(f"**Recommendation:** {result.recommendation}")

        csv_text = results_to_csv_text(ranked)
        st.download_button(
            "Download results as CSV",
            data=csv_text,
            file_name="match_results.csv",
            mime="text/csv",
        )
