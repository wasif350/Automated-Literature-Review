import streamlit as st
import pandas as pd
import os
import requests
import time

st.set_page_config(page_title="Literature Review Pipeline", layout="wide")
st.title("Literature Review Pipeline")
st.write("Fetch papers from the selected source and save to a master CSV.")

# ----------------------------
# Inputs
# ----------------------------
query = st.text_input("Enter primary keywords:", "healthcare AND device AND security")
fetch_all = st.checkbox("Fetch all related papers from selected sources")
max_results = st.number_input(
    "Max results per source:", min_value=1, max_value=50, value=5, disabled=fetch_all
)

# Dropdown to select one or more sources
sources_selected = st.multiselect(
    "Select source(s)",
    options=["arXiv", "Semantic Scholar", "IEEE Xplore", "ACM Digital Library", "Google Scholar"],
    default=["arXiv"]
)

api_source_map = {
    "arXiv": "arxiv",
    "Semantic Scholar": "semantic",
    "IEEE Xplore": "ieee",
    "ACM Digital Library": "acm",
    "Google Scholar": "google",
}

ALLOWED_FIELDS = {
    "paper_id", "title", "authors", "venue", "year", "doi", "source",
    "abstract", "abstract_hit", "primary_keywords", "pdf_status",
    "pdf_url" ,"secondary_keywords_present", "secondary_keyword_counts",
    "paper_type", "last_updated"
}

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

def sanitize_paper(paper: dict) -> dict:
    """Keep only allowed fields in each paper row."""
    return {k: v for k, v in paper.items() if k in ALLOWED_FIELDS}

def safe_year(p):
    y = p.get("year")
    try:
        return int(y)
    except (TypeError, ValueError):
        return 0

def deduplicate(all_papers):
    """
    Deduplicate papers across multiple sources using DOI or (title + first author).
    """
    seen_keys = set()
    unique_papers = []
    duplicates = []

    for paper in all_papers:
        key = paper.get("doi") or (
            paper.get("title", "").lower(),
            paper.get("authors")[0] if paper.get("authors") else "",
        )
        if key not in seen_keys:
            seen_keys.add(key)
            unique_papers.append(paper)

    return unique_papers

papers = [] 

# Button to fetch papers
if st.button("Fetch Papers"):
    if not query.strip():
        st.warning("Please enter at least one keyword.")
    elif not sources_selected:
        st.warning("Please select at least one source.")
    else:
        try:
            status_placeholder = st.empty()
            placeholder = st.empty()
            for source in sources_selected:
                status_placeholder.info(f"Fetching papers from {source}...")
                selected_sources_api = api_source_map[source]
                send_max_results = 0 if fetch_all else max_results

                response = requests.get(
                    f"{BACKEND_URL}/papers",
                    params={
                        "query": query,
                        "fetch_all": fetch_all,
                        "max_results": send_max_results,
                        "sources": selected_sources_api
                    },
                )
                if response.status_code != 200:
                    status_placeholder.error(f"API error from {source}: {response.status_code} {response.text}")
                    continue

                new_papers = response.json().get("results", [])
                if not new_papers:
                    status_placeholder.warning(f"No papers found from {source}.")
                    continue
                papers.extend(new_papers)

                status_placeholder.info(f"Downloading PDFs for {source} papers...")
                for i, paper in enumerate(new_papers, start=1):
                    status_placeholder.info(f"Downloading PDF {i}/{len(new_papers)} from {source}...")
                    download_resp = requests.post(
                        f"{BACKEND_URL}/download_papers",
                        json={"papers": [paper]} 
                    )
                    if download_resp.status_code == 200:
                        downloaded = download_resp.json().get("results", [])
                        for updated in downloaded:
                            for idx, p in enumerate(papers):
                                if p["paper_id"] == updated.get("paper_id"):
                                    papers[idx] = updated
                                    break
                    else:
                        status_placeholder.warning(f"PDF download failed for {paper.get('title','Unknown')}")

                scan_paper = 1
                for i, paper in enumerate(papers, start=1):
                    status_placeholder.info(f"Scanning PDF {scan_paper}/{len(new_papers)} from {source}...")
                    scan_resp = requests.post(
                        f"{BACKEND_URL}/scan_papers",
                        json={"papers": [paper], "query": query}
                    )
                    if scan_resp.status_code == 200:
                        scanned = scan_resp.json().get("results", [])
                        for updated in scanned:
                            for idx, p in enumerate(papers):
                                if p["paper_id"] == updated.get("paper_id"):
                                    papers[idx] = updated
                                    break
                    else:
                        status_placeholder.warning(f"PDF scan failed for {paper.get('title','Unknown')}")
                    if scan_paper < len(new_papers):
                        scan_paper += 1

                df = pd.DataFrame(papers)
                df_display = [sanitize_paper(p) for p in papers]
                df_display.sort(key=lambda p: (-safe_year(p), p.get("title", "")))

                df = pd.DataFrame(df_display)
                df["year"] = df["year"].apply(lambda x: str(x) if x is not None else "")

                placeholder.dataframe(df)
                time.sleep(2)
            # Save final CSV after all sources
            if papers:
                papers = deduplicate(papers)
                df_file = [sanitize_paper(p) for p in papers]
                df_file.sort(key=lambda p: (-safe_year(p), p.get("title", "")))

                df = pd.DataFrame(df_file)
                df["year"] = df["year"].apply(lambda x: str(x) if x is not None else "")

                placeholder.dataframe(df) 
                os.makedirs("../data", exist_ok=True)
                df.to_csv("../data/master.csv", index=False)

                status_placeholder.success(f"All sources processed. Unique papers: {len(df)}")

        except Exception as e:
            st.error(f"Error fetching papers: {e}")