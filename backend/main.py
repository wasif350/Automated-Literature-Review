from fastapi import FastAPI, Query
from api.papers import PapersFetcher, PaperProcessor
from utils.pdf_utils import PDFHandler, PDFScanner, PdfProcessor
from config import Config
from logs.logging_config import logger

app = FastAPI(title="Literature Review API")

fetcher = PapersFetcher(
    semantic_api_key=Config.SEMANTIC_API_KEY,
    ieee_api_key=Config.IEEE_API_KEY
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
    "pdf_url",
    "secondary_keywords_present",
    "secondary_keyword_counts",
    "paper_type",
    "last_updated",
}

def sanitize_paper(paper: dict) -> dict:
    """Keep only allowed fields in each paper row."""
    return {k: v for k, v in paper.items() if k in ALLOWED_FIELDS}

 def safe_year(p):
            y = p.get("year")
            try:
                return int(y)
            except (TypeError, ValueError):
                return 0


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 FastAPI app started")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 FastAPI app shutting down")


@app.get("/papers")
def get_papers(query: str, fetch_all: bool, max_results: int = 5, sources: str = Query("arxiv,semantic,ieee,acm")):
    """
    API endpoint to fetch research papers from multiple sources 
    (arXiv, Semantic Scholar, IEEE, ACM, Google Scholar).
    Applies deduplication, PDF processing, and sanitization before returning results.
    """
    logger.info(f"Fetching papers | query='{query}', max_results={max_results}, sources={sources}")

    results = []
    try:
        selected_sources = [s.strip().lower() for s in sources.split(",")]

        if "arxiv" in selected_sources:
            results.extend(fetcher.fetch_arxiv(query, max_results, fetch_all))
        if "semantic" in selected_sources:
            results.extend(fetcher.fetch_semantic_scholar(query, max_results, fetch_all))
        if "ieee" in selected_sources:
            results.extend(fetcher.fetch_ieee(query, max_results, fetch_all))
        if "acm" in selected_sources:
            results.extend(fetcher.fetch_acm_by_member(query, max_results, fetch_all))
        if "google" in selected_sources:
            results.extend(fetcher.fetch_google_scholar(query, max_results, fetch_all))

        logger.info(f"Fetched {len(results)} raw papers")

        results = processor.deduplicate(results)
        results = pdf_processer.process(results, query)
        results = [sanitize_paper(p) for p in results]

        results.sort(key=lambda p: (-safe_year(p), p.get("title", "")))
        # results.sort(key=lambda p: (p.get('year') is None, -(p.get('year') or 0)))

        logger.info(f"Returning {len(results)} papers after processing")
        return {"results": results}

    except Exception as e:
        logger.exception(f"Error fetching papers: {e}")
        return {"error": "Something went wrong"}
