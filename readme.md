Literature Review Pipeline

This project is a pipeline + app that helps fetch, process, and review research papers from multiple scholarly sources.
It searches papers by keywords, tries to download PDFs, scans them for other keywords, and saves everything into a CSV report.

🚀 How it works

Frontend (Streamlit app)

frontend/app.py

    - Simple UI to enter keywords, choose sources, and run searches.

    - Calls the backend API and shows results in a table.

    - Saves results into data/master.csv.

    - Backend (FastAPI service)

backend/main.py

   - Handles paper fetching, deduplication, PDF downloading, and scanning.

   - Exposes /papers endpoint for the frontend.

Paper fetching logic

backend/api/papers.py

    - Connects to:

    - arXiv (API)

    - Semantic Scholar (API)

    - IEEE Xplore (API)

    - ACM Digital Library (via CrossRef)

    - Google Scholar (via PyPaperBot)

    - Normalizes results into a standard format.

PDF handling & keyword scanning

backend/utils/pdf_utils.py

    - Downloads PDFs (if open access).

    - Scans PDFs for secondary keywords from your query.

    - Records keyword counts + small text snippets.

Logging

backend/logs/logging_config.py

    - Logs app events into files for debugging.

Configuration

    - .env file stores API keys and secrets.

    - config.py loads environment settings.

📊 CSV Output

    - Each paper is saved as one row in data/master.csv, with these fields:

        paper_id

        title

        authors

        venue

        year

        doi

        source

        abstract

        abstract_hit

        primary_keywords

        pdf_status (downloaded | manual | unavailable)

        secondary_keywords_present

        secondary_keyword_counts

        paper_type

        last_updated

How to run
    Backend
        - cd backend
        - uvicorn main:app --reload

    Frontend
        - cd frontend
        - streamlit run app.py


Then open the Streamlit UI in your browser, enter keywords, and fetch papers 🚀