import requests
import xml.etree.ElementTree as ET
import subprocess, bibtexparser
import json
import sys, os, time


class PapersFetcher:
    def __init__(self, semantic_api_key=None, ieee_api_key=None):
        self.semantic_api_key = semantic_api_key
        self.ieee_api_key = ieee_api_key

    # -----------------------------
    # Normalized paper template
    # -----------------------------
    @staticmethod
    def normalize_paper(paper_id, title, authors, venue, year, doi, pdf_url, pdf_status, source, abstract="", abstract_hit=False , last_updated=""):
        """
        Normalize paper metadata into a consistent dictionary format.
        Ensures uniform fields (ID, title, authors, venue, year, DOI, abstract, PDF info, etc.)
        across different data sources.
        """

        if isinstance(authors, list):
            authors_str = ", ".join(authors)
        else:
            authors_str = authors or ""

        return {
            "paper_id": paper_id,
            "title": title,
            "authors": authors_str,
            "venue": venue,
            "year": year,
            "doi": doi,
            "source": source,
            "abstract": abstract,
            "abstract_hit": abstract_hit,
            "primary_keywords": [],
            "pdf_status": pdf_status,
            "pdf_url": pdf_url,
            "pdf_path": '',
            "secondary_keywords_present": {},
            "secondary_keyword_counts": {},
            "paper_type": "Other",
            "last_updated": last_updated
        }

    # -----------------------------
    # arXiv
    # -----------------------------
    def fetch_arxiv(self, query, max_results=5):
        """
        Fetch papers from arXiv using its API.
        Parses XML feed, extracts metadata (title, authors, summary, dates, DOI, PDF link),
        and normalizes results into a standard paper format.
        """

        base_url = "http://export.arxiv.org/api/query"
        params = {"search_query": query, "start": 0, "max_results": max_results}
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.text)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom"
        }
        papers = []

        for entry in root.findall("atom:entry", ns):
            paper_id = entry.find("atom:id", ns).text if entry.find("atom:id", ns) is not None else None
            title = entry.find("atom:title", ns).text.strip() if entry.find("atom:title", ns) is not None else None
            summary = entry.find("atom:summary", ns).text.strip() if entry.find("atom:summary", ns) is not None else None
            published = entry.find("atom:published", ns).text if entry.find("atom:published", ns) is not None else None
            updated = entry.find("atom:updated", ns).text if entry.find("atom:updated", ns) is not None else None

            authors = ", ".join(
                [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            )

            doi_elem = entry.find("arxiv:doi", ns)
            if doi_elem is not None:
                doi = doi_elem.text
            elif paper_id:
                base_arxiv_id = paper_id.split("/")[-1].split("v")[0]
                doi = f"10.48550/arXiv.{base_arxiv_id}"
            else:
                doi = None

            pdf_url = None
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("type") == "application/pdf":
                    pdf_url = link.attrib.get("href")
                    break

            pdf_status = "downloaded" if pdf_url else "unavailable"

            papers.append(self.normalize_paper(
                paper_id=paper_id,
                title=title,
                authors=authors,
                venue="arXiv",
                year=published[:4] if published else None,
                doi=doi,
                pdf_url=pdf_url,
                pdf_status=pdf_status,
                source="arXiv",
                abstract=summary,
                abstract_hit=query.lower() in summary.lower() if summary else False,
                last_updated=updated
            ))

        return papers

    # -----------------------------
    # Semantic Scholar
    # -----------------------------
    def fetch_semantic_scholar(self, query, max_results=100, year="2023-"):
        """
        Fetch papers from Semantic Scholar API.
        Retrieves metadata (title, authors, venue, year, abstract, PDF info) 
        and normalizes results into a standard format.
        """
        
        url = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
        headers = {"x-api-key": self.semantic_api_key}
        fields = "title,url,authors,abstract,year,venue,openAccessPdf,publicationTypes"

        papers, token = [], None
        while True:
            params = {"query": f'"{query}"', "fields": fields, "year": year}
            if token:
                params["token"] = token

            response = requests.get(url, params=params, headers=headers)
            if response.status_code != 200:
                print(f"Semantic Scholar fetch error: {response.status_code} {response.text}")
                break

            data = response.json()
            batch = data.get("data", [])
            for paper in batch:
                open_access = paper.get("openAccessPdf", {})
                pdf_url = open_access.get("url") if open_access and open_access.get("url") else None
                pdf_status = "downloaded" if pdf_url else "unavailable"
                papers.append(self.normalize_paper(
                    paper_id=paper.get("paperId"),
                    title=paper.get("title"),
                    authors=[a["name"] for a in paper.get("authors", [])],
                    venue=paper.get("venue"),
                    year=paper.get("year"),
                    doi=None,
                    pdf_url = pdf_url,
                    pdf_status = pdf_status,
                    source="Semantic Scholar",
                    abstract=paper.get("abstract"),
                    abstract_hit=query.lower() in (paper.get("abstract") or "").lower(),
                    last_updated=paper.get("year")
                ))

            token = data.get("token")
            if not token:
                break

        return papers

    # -----------------------------
    # IEEE
    # -----------------------------
    def fetch_ieee(self, query, max_results=5):
        """
        Fetch papers from IEEE Xplore API.
        Extracts metadata (title, authors, venue, year, DOI, abstract, PDF info) 
        and normalizes results into a standard format.
        """

        url = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
        params = {
            "apikey": self.ieee_api_key,
            "querytext": query,
            "max_records": max_results,
            "format": "json"
        }

        papers = []
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            for article in data.get("articles", []):
                authors = [a.get("full_name") for a in article.get("authors", [])] if article.get("authors") else []
                pdf_status = "downloaded" if article.get("pdf_url") else "unavailable"
                papers.append(self.normalize_paper(
                    paper_id=article.get("article_number") or article.get("doi"),
                    title=article.get("title"),
                    authors=authors,
                    venue=article.get("publication_title"),
                    year=article.get("publication_year"),
                    doi=article.get("doi"),
                    source="IEEE Xplore",
                    abstract=article.get("abstract"),
                    abstract_hit=query.lower() in (article.get("abstract") or "").lower()
                ))
        except Exception as e:
            print(f"IEEE fetch error: {e}")
        return papers

    # -----------------------------
    # ACM via CrossRef member ID
    # -----------------------------
    def enrich_acm_with_doi(self, doi, query):
        """
        Enrich ACM papers via CrossRef using DOI.
        Retrieves metadata (title, authors, venue, year, abstract, PDF link) 
        and normalizes it into a standard format.
        """

        url = f"https://api.crossref.org/works/{doi}"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            item = resp.json()["message"]

            authors = []
            if "author" in item:
                for a in item["author"]:
                    full_name = " ".join(filter(None, [a.get("given"), a.get("family")]))
                    authors.append(full_name)
            
            pdf_url = ""
            if "link" in item:
                for link in item["link"]:
                    if link.get("content-type") == "application/pdf":
                        pdf_url = link.get("URL")
                        break

            last_updated = None
            if "issued" in item and "date-parts" in item["issued"]:
                year = item["issued"]["date-parts"][0]
                last_updated = "-".join(str(x) for x in year)
            return self.normalize_paper(
                paper_id=item.get("DOI"),
                title=item.get("title", [None])[0],
                authors=", ".join(authors),
                venue=item.get("container-title", [None])[0],
                year=item.get("issued", {}).get("date-parts", [[None]])[0][0],
                doi=item.get("DOI"),
                pdf_url = pdf_url,
                pdf_status = '',
                source="Google Scholar",
                abstract=item.get("abstract") or "",
                abstract_hit=query.lower() in (item.get("title", [""])[0].lower()),
                last_updated=last_updated
            )
        except Exception as e:
            print(f"CrossRef enrichment failed for DOI {doi}: {e}")
            return None

    def fetch_acm_by_member(self, query, max_results=20):
        """
        Fetch papers from ACM Digital Library via CrossRef member ID.
        Extracts metadata (title, authors, venue, year, DOI, PDF link) 
        and normalizes results into a standard format.
        """

        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": max_results, "filter": "member:320"}

        papers = []
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            items = response.json()["message"]["items"]

            for item in items:

                title = item.get("title", [""])[0]
                authors = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() 
                                    for a in item.get("author", [])])

                last_updated = None
                if "issued" in item and "date-parts" in item["issued"]:
                    year = item["issued"]["date-parts"][0]
                    last_updated = "-".join(str(x) for x in year)

                doi = item.get("DOI")

                pdf_url = None
                if "link" in item:
                    for link in item["link"]:
                        if "pdf" in link.get("URL", ""):
                            pdf_url = link["URL"]
                            break

                pdf_status = "downloaded" if pdf_url else "unavailable"

                papers.append(self.normalize_paper(
                    paper_id=doi,
                    title=title,
                    authors=authors,
                    venue=item.get("container-title", ["ACM Digital Library"])[0],
                    year=year,
                    doi=doi,
                    pdf_url=pdf_url,
                    pdf_status=pdf_status,
                    source="ACM Digital Library",
                    abstract=None,
                    abstract_hit=query.lower() in title.lower(),
                    last_updated=last_updated
                ))

        except Exception as e:
            print(f"ACM member search fetch error: {e}")

        return papers

    # -----------------------------
    # Google Scholar
    # -----------------------------
    def fetch_google_scholar(self, query: str, scholar_pages: int = 1, max_results: int = 10, timeout: int = 120):
        """
        Fetch papers from Google Scholar using PyPaperBot subprocess.
        Downloads PDFs, reads results.csv, enriches metadata via DOI, 
        and normalizes papers with PDF paths.
        """
        import csv
        papers = []

        try:
            dwn_dir = os.path.abspath("./downloads")
            os.makedirs(dwn_dir, exist_ok=True)

            cmd = [
                sys.executable, "-m", "PyPaperBot",
                f"--query={query.strip()}",
                f"--scholar-pages={scholar_pages}",
                f"--scholar-results={max_results}",
                "--restrict=0",
                f"--dwn-dir={dwn_dir}"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return []

            csv_file = os.path.join(dwn_dir, "result.csv")
            start_time = time.time()
            while time.time() - start_time < timeout:
                if os.path.exists(csv_file) and os.path.getsize(csv_file) > 0:
                    break
                time.sleep(1)
            else:
                print("results.csv not found or empty.")
                return []

            with open(csv_file, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    doi = row.get("doi") or row.get("DOI")
                    # pdf_path = row.get("pdf_path") or row.get("PDF Path") or ""
                    paper = None

                    if doi:
                        enriched = self.enrich_acm_with_doi(doi, query)
                        if enriched:
                            paper = enriched

                    if not paper:
                        paper = self.normalize_paper(
                            paper_id=doi or row.get("ID"),
                            title=row.get("title"),
                            authors=[a.strip() for a in row.get("author", "").split(";")],
                            venue=row.get("journal") or "Google Scholar",
                            year=row.get("year"),
                            doi=doi,
                            pdf_url=row.get("pdf_url") or "",
                            pdf_status="",
                            source="Google Scholar (CSV)",
                            abstract=row.get("abstract") or "",
                            abstract_hit=query.lower() in (row.get("abstract") or "").lower(),
                            last_updated=row.get("year")
                        )

                    papers.append(paper)

        except Exception as e:
            print(f"Google Scholar fetch error: {e}")

        return papers

class PaperProcessor:

    def deduplicate(self, all_papers):
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
            else:
                duplicates.append(paper)

        return unique_papers

