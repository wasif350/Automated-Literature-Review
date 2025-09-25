import os
import re
import requests
from urllib.parse import urlparse
from PyPDF2 import PdfReader
from logs.logging_config import logger


class PDFHandler:
    def __init__(self, download_dir="./downloads"):
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)

    def _get_headers(self, paper, pdf_url):
        """
        Return headers based on the source to bypass common bot restrictions.
        """
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive"
        }

        source = paper.get("source")
        if source in ["ACM Digital Library", "Semantic Scholar"]:
            headers["Referer"] = pdf_url

        return headers

    def _get_safe_filename(self, paper, pdf_url):
        """
        Construct a safe filename for the PDF.
        """
        base_name = paper.get("doi") or paper.get("paper_id") or os.path.basename(urlparse(pdf_url).path)
        filename = "".join([c if c.isalnum() or c in "-_." else "_" for c in base_name]) + ".pdf"
        return os.path.join(self.download_dir, filename)

    def normalize_pdf_url(self, pdf_url: str) -> str:
        """
        Ensure the given URL points to a PDF.
        Fixes arXiv 'abs' links into 'pdf' links.
        """
        if not pdf_url:
            return None

        if "arxiv.org/abs/" in pdf_url:
            return pdf_url.replace("/abs/", "/pdf/")

        return pdf_url

    def download_pdf(self, paper):
        """
        Download a PDF for a single paper and update pdf_status.
        """
        pdf_url = self.normalize_pdf_url(paper.get("pdf_url") or paper.get("open_access_url"))
        if not pdf_url:
            paper["pdf_status"] = "unavailable"
            return paper

        filepath = self._get_safe_filename(paper, pdf_url)
        if os.path.exists(filepath):
            logger.info(f"PDF already exists: {filepath}")
            paper["pdf_status"] = "downloaded"
            paper["pdf_path"] = filepath
            return paper

        headers = self._get_headers(paper, pdf_url)

        try:
            resp = requests.get(pdf_url, headers=headers, stream=True, timeout=30, allow_redirects=True)
            content_type = resp.headers.get("Content-Type", "").lower()

            if resp.status_code == 200 and "pdf" in content_type:
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(1024):
                        f.write(chunk)
                paper["pdf_status"] = "downloaded"
                paper["pdf_path"] = filepath
                logger.info(f"Downloaded PDF: {paper.get('title')} -> {filepath}")

            else:
                paper["pdf_status"] = "manual"
                msg = f"Blocked ({resp.status_code}) for {paper.get('title')} -> {pdf_url}"
                logger.error(msg)

        except Exception as e:
            msg = f"Failed to download PDF for {paper.get('title')}: {e}"
            print(msg)
            logger.exception(msg)
            paper["pdf_status"] = "unavailable"

        return paper

    def batch_download(self, papers):
        """
        Download PDFs for a list of papers.
        """
        for i, paper in enumerate(papers):
            msg = f"Downloading PDF for paper {i+1}/{len(papers)}: {paper.get('title')}"
            logger.info(msg)
            papers[i] = self.download_pdf(paper)
        return papers


class PDFScanner:
    def __init__(self, secondary_keywords=None, window=40):
        """
        :param secondary_keywords: list of keywords to scan for
        :param window: number of chars before/after keyword to include as snippet
        """
        self.secondary_keywords = secondary_keywords or []
        self.window = window

    def scan_pdf(self, pdf_path: str) -> dict:
        """
        Scan a PDF for secondary keywords.
        Returns dict with counts + snippets.
        """
        results = {
            "secondary_keywords_present": {},
            "secondary_keyword_counts": {},
        }

        if not pdf_path or not pdf_path.endswith(".pdf"):
            return results

        try:
            reader = PdfReader(pdf_path)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() or ""

            full_text_lower = full_text.lower()

            for kw in self.secondary_keywords:
                pattern = re.compile(re.escape(kw.lower()))
                matches = list(pattern.finditer(full_text_lower))

                count = len(matches)
                results["secondary_keyword_counts"][kw] = count
                results["secondary_keywords_present"][kw] = count > 0

                # Grab snippets
                snippets = []
                for m in matches[:5]:
                    start = max(0, m.start() - self.window)
                    end = min(len(full_text), m.end() + self.window)
                    snippets.append(full_text[start:end].replace("\n", " "))
                if snippets:
                    results[f"{kw}_snippets"] = snippets

            logger.info(f"Scanned PDF: {pdf_path} | Keywords found: {results['secondary_keywords_present']}")

        except Exception as e:
            msg = f"Failed to scan {pdf_path}: {e}"
            print(msg)
            logger.exception(msg)

        return results                      


class PdfProcessor:
    def __init__(self, download_dir="./downloads"):
        self.pdf_handler = PDFHandler(download_dir=download_dir)

    def process(self, papers):
        """
        Downloads PDFs and scans them for secondary keywords derived from the query.
        Updates each paper dict with:
        - pdf_status
        - pdf_path
        - secondary_keywords_present
        - secondary_keyword_counts
        - snippet columns per keyword
        - primary_keywords (from query)
        """
        papers = self.pdf_handler.batch_download(papers)

        return papers
