from fastapi import FastAPI, Query
from api.papers import PapersFetcher , PaperProcessor
from utils.pdf_utils import PDFHandler , PDFScanner , PdfProcessor

app = FastAPI(title="Literature Review API")

fetcher = PapersFetcher(
    semantic_api_key="wD0HXTHe8g8siv01xtVyd76yTeqpgoV75KBzGKv5",
    ieee_api_key="nw5ez8vktv2dtxrxud6xy6av"
)
processor = PaperProcessor()

pdf_handler = PDFHandler(download_dir="./downloads")
pdf_processer = PdfProcessor(download_dir="./downloads")
ALLOWED_FIELDS = {
    "paper_id",
    "title",
    "authors",
    "venue",
    "year",
    "doi",
    "source",
    "abstract",
    "abstract_hit",
    "primary_keywords",
    "pdf_status",
    "secondary_keywords_present",
    "secondary_keyword_counts",
    "paper_type",
    "last_updated",
}


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

def process_papers(papers , query):
     # Build secondary keyword list from query
    raw_keywords = query.replace("AND", " ").replace("and", " ").split()
    secondary_keywords = [kw.strip() for kw in raw_keywords if kw.strip()]
    pdf_scanner = PDFScanner(secondary_keywords=secondary_keywords)
    # Step 1: Download PDFs
    papers = pdf_handler.batch_download(papers)

    # Step 2: Scan PDFs for secondary keywords
    for i, paper in enumerate(papers):
        print(paper)
        if paper.get("pdf_status") == "downloaded":
            scan_results = pdf_scanner.scan_pdf(paper["pdf_path"])
            print(scan_results)
            papers[i].update(scan_results)

    return papers

def sanitize_paper(paper: dict) -> dict:
    """Keep only allowed fields in each paper row."""
    return {k: v for k, v in paper.items() if k in ALLOWED_FIELDS}

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
    results = processor.deduplicate(results)
    results = pdf_processer.process(results , query)
    results = [sanitize_paper(p) for p in results]
    
    return {"results": results}
