import requests
import xml.etree.ElementTree as ET
import subprocess , bibtexparser
import json
import sys , os , time


class PapersFetcher:
    def __init__(self, semantic_api_key=None, ieee_api_key=None):
        self.semantic_api_key = semantic_api_key
        self.ieee_api_key = ieee_api_key

    # -----------------------------
    # Normalized paper template
    # -----------------------------
    @staticmethod
    def normalize_paper(paper_id, title, authors, venue, year, doi, pdf_url, pdf_status, source, abstract="", abstract_hit=False , last_updated=""):
        # Convert authors to string if it's a list
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
        base_url = "http://export.arxiv.org/api/query"
        params = {"search_query": query, "start": 0, "max_results": max_results}
        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            return []

        root = ET.fromstring(response.text)
        ns = {'arxiv': 'http://www.w3.org/2005/Atom'}
        papers = []
       
        for entry in root.findall('arxiv:entry', ns):
            # Extract paper_id safely
            paper_id = entry.find('arxiv:id', ns).text if entry.find('arxiv:id', ns) is not None else None

            # Build PDF URL only if paper_id exists
            pdf_url = f"{paper_id}.pdf" if paper_id else None
            pdf_status = "downloaded" if pdf_url else "unavailable"

            # Extract authors as comma-separated string
            authors = ", ".join([a.find('arxiv:name', ns).text for a in entry.findall('arxiv:author', ns)])
             # Last updated
            last_updated_elem = entry.find('arxiv:updated', ns)
            last_updated = last_updated_elem.text if last_updated_elem is not None else None
            # Append normalized paper
            papers.append(self.normalize_paper(
                paper_id=paper_id,
                title=entry.find('arxiv:title', ns).text,
                authors=authors,
                venue="arXiv",
                year=entry.find('arxiv:published', ns).text[:4],
                doi=entry.find('arxiv:doi', ns).text if entry.find('arxiv:doi', ns) is not None else None,
                pdf_url=pdf_url,
                pdf_status=pdf_status,
                source="arXiv",
                abstract=entry.find('arxiv:summary', ns).text,
                abstract_hit=query.lower() in (entry.find('arxiv:summary', ns).text.lower()),
                last_updated=last_updated
            ))

        return papers

    # -----------------------------
    # Semantic Scholar
    # -----------------------------
    def fetch_semantic_scholar(self, query, max_results=100, year="2023-"):
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
                print('abcpaper',paper)
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
            
            # Extract PDF URL from 'link' field if available
            pdf_url = ""
            if "link" in item:
                for link in item["link"]:
                    if link.get("content-type") == "application/pdf":
                        pdf_url = link.get("URL")
                        break  # take first PDF link
             # Extract year
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
        url = "https://api.crossref.org/works"
        params = {"query": query, "rows": max_results, "filter": "member:320"}  # ACM member

        papers = []
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            items = response.json()["message"]["items"]

            for item in items:  # items is the Crossref API response list
                print("itemabc", item)

                # Extract title safely
                title = item.get("title", [""])[0]

                # Extract authors as a single string
                authors = ", ".join([f"{a.get('given', '')} {a.get('family', '')}".strip() 
                                    for a in item.get("author", [])])

                # Extract year
                last_updated = None
                if "issued" in item and "date-parts" in item["issued"]:
                    year = item["issued"]["date-parts"][0]
                    last_updated = "-".join(str(x) for x in year)

                # Extract DOI
                doi = item.get("DOI")

                # Extract PDF URL (if any)
                pdf_url = None
                if "link" in item:
                    for link in item["link"]:
                        if "pdf" in link.get("URL", ""):  # look for ACM pdf link
                            pdf_url = link["URL"]
                            break

                pdf_status = "downloaded" if pdf_url else "unavailable"

                # Append normalized result
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
                    abstract=None,  # Crossref doesn’t provide abstract
                    abstract_hit=query.lower() in title.lower(),
                    last_updated=last_updated
                ))

        except Exception as e:
            print(f"ACM member search fetch error: {e}")

        return papers

    def fetch_google_scholar(self, query: str, scholar_pages: int = 1, max_results: int = 10, timeout: int = 120):
        """
        Fetch papers from Google Scholar using PyPaperBot subprocess.
        Downloads PDFs, reads results.csv, enriches metadata via DOI, 
        and normalizes papers with PDF paths.
        """
        import csv
        papers = []

        try:
            # Ensure downloads directory exists
            dwn_dir = os.path.abspath("./downloads")
            os.makedirs(dwn_dir, exist_ok=True)

            # Run PyPaperBot subprocess
            cmd = [
                sys.executable, "-m", "PyPaperBot",
                f"--query={query.strip()}",
                f"--scholar-pages={scholar_pages}",
                f"--scholar-results={max_results}",
                "--restrict=0",
                f"--dwn-dir={dwn_dir}"
            ]
            print("Running PyPaperBot...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            print("PyPaperBot output:\n", result.stdout)
            if result.returncode != 0:
                print("PyPaperBot error:\n", result.stderr)
                return []

            # Wait for results.csv
            csv_file = os.path.join(dwn_dir, "result.csv")
            start_time = time.time()
            while time.time() - start_time < timeout:
                if os.path.exists(csv_file) and os.path.getsize(csv_file) > 0:
                    break
                time.sleep(1)
            else:
                print("results.csv not found or empty.")
                return []
            print('before csv open')
            # Parse CSV and normalize papers
            with open(csv_file, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    doi = row.get("doi") or row.get("DOI")
                    print('doi',doi)
                    # pdf_path = row.get("pdf_path") or row.get("PDF Path") or ""
                    paper = None

                    # Enrich metadata via DOI
                    if doi:
                        enriched = self.enrich_acm_with_doi(doi, query)
                        print(enriched)
                        if enriched:
                            paper = enriched

                    # Fallback to CSV data if enrichment fails
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

        print(f"Total papers fetched: {len(papers)}")
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

