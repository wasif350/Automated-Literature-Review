import os
import requests
from urllib.parse import urlparse

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
            paper["pdf_status"] = "downloaded"
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
            elif resp.status_code in [403, 418]:
                paper["pdf_status"] = "restricted"
                print(f"Blocked ({resp.status_code}) for {paper.get('title')} -> {pdf_url}")
            else:
                paper["pdf_status"] = "unavailable"
                print(f"Cannot download ({resp.status_code}, {content_type}) -> {pdf_url}")

        except Exception as e:
            print(f"Failed to download PDF for {paper.get('title')}: {e}")
            paper["pdf_status"] = "unavailable"

        return paper

    def batch_download(self, papers):
        """
        Download PDFs for a list of papers.
        """
        for i, paper in enumerate(papers):
            print(f"Downloading PDF for paper {i+1}/{len(papers)}: {paper.get('title')}")
            papers[i] = self.download_pdf(paper)
        return papers
