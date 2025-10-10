Literature Review Pipeline

This project is a pipeline that helps fetch, process, and scan research papers from multiple scholarly sources.
It searches papers by keywords, tries to download PDFs, scans them for other secondary keywords, and saves everything into a CSV report.

🚀 How it works

Frontend (Streamlit app)

frontend/app.py

    - Simple UI to enter keywords, secondary keywords, choose sources, and run searches.

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

    - IEEE Xplore (API/via CrossRef)

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

        pdf_url

        secondary_keywords_present

        secondary_keyword_counts

        paper_type

        last_updated
How to Run

    The entire application can started with a  Docker command.
    
        Build and start the application
        - docker-compose up --build

        This command will:
        - Build the Docker images for both the backend (FastAPI) and frontend (Streamlit)
        - Start both containers and link them together automatically

Access the app

    Once the containers are running:
    - Frontend (Streamlit UI): http://localhost:8501
    - Backend (FastAPI API): http://localhost:8000
    Then open the Streamlit UI in your browser, enter keywords, and fetch papers

Stop the application

    When finished, stop and remove all containers:
    - docker-compose down
