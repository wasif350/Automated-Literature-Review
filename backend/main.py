from fastapi import FastAPI, Query
from api.papers import PapersFetcher
from utils.pdf_utils import PDFHandler

app = FastAPI(title="Literature Review API")

pdf_handler = PDFHandler(download_dir="./downloads")

fetcher = PapersFetcher(
    semantic_api_key="wD0HXTHe8g8siv01xtVyd76yTeqpgoV75KBzGKv5",
    ieee_api_key="nw5ez8vktv2dtxrxud6xy6av"
)

def deduplicate_papers(all_papers):
    """
    Deduplicate papers across multiple sources using DOI or (title + first author).
    """
    seen_keys = set()
    unique_papers = []
    duplicates = []

    for paper in all_papers:
        key = paper.get("doi") or (paper.get("title", "").lower(), 
                                   paper.get("authors")[0] if paper.get("authors") else "")
        if key not in seen_keys:
            seen_keys.add(key)
            unique_papers.append(paper)
        else:
            duplicates.append(paper)

    print(f"Total papers before deduplication: {len(all_papers)}")
    print(f"Total papers after deduplication: {len(unique_papers)}")
    print(f"Duplicate papers skipped: {len(duplicates)}")

    return unique_papers


@app.get("/papers")
def get_papers(query: str, max_results: int = 5, sources: str = Query("arxiv,semantic,ieee,acm")):
    results = []
    selected_sources = [s.strip().lower() for s in sources.split(",")]

    if "arxiv" in selected_sources:
        results.extend(fetcher.fetch_arxiv(query, max_results))
    if "semantic" in selected_sources:
        results.extend(fetcher.fetch_semantic_scholar(query, max_results))
    if "ieee" in selected_sources:
        results.extend(fetcher.fetch_ieee(query, max_results))
    if "acm" in selected_sources:
        results.extend(fetcher.fetch_acm_by_member(query, max_results))
    if "google" in selected_sources:
        results.extend(fetcher.fetch_google_scholar(query, scholar_pages=1, max_results=max_results))
    print(len(results))
    results = deduplicate_papers(results)
    print(len(results))
    # print(results)
    results = pdf_handler.batch_download(results)
    return {"results": results}
