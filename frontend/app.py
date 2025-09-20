import streamlit as st
import pandas as pd
import os
import requests

st.set_page_config(page_title="Literature Review Pipeline", layout="wide")
st.title("Literature Review Pipeline")
st.write("Fetch papers from the selected source and save to a master CSV.")

# ----------------------------
# Inputs
# ----------------------------
query = st.text_input("Enter primary keywords:", "healthcare AND device AND security")
max_results = st.number_input("Max results per source:", min_value=1, max_value=50, value=5)

# Dropdown to select one or more sources
sources_selected = st.multiselect(
    "Select source(s)",
    options=["arXiv", "Semantic Scholar", "IEEE Xplore" ,"ACM Digital Library" ,"Google Scholar"],
    default=["arXiv"]
)

api_source_map = {
    "arXiv": "arxiv",
    "Semantic Scholar": "semantic",
    "IEEE Xplore": "ieee",
    "ACM Digital Library": "acm",
    "Google Scholar": "google"                                                                                                                                                
}

# Button to fetch papers
if st.button("Fetch Papers"):
    if not query.strip():
        st.warning("Please enter at least one keyword.")
    elif not sources_selected:
        st.warning("Please select at least one source.")
    else:
        with st.spinner(f"Fetching papers from {', '.join(sources_selected)} via API..."):
            try:
                selected_sources_api = ",".join([api_source_map[s] for s in sources_selected])

                # Call FastAPI endpoint
                response = requests.get(
                    "http://127.0.0.1:8000/papers",
                    params={
                        "query": query,
                        "max_results": max_results,
                        "sources": selected_sources_api
                    }
                )

                if response.status_code == 200:
                    papers_list = response.json().get("results", [])
                
                    # Restrict results shown to frontend
                    # if max_results and len(papers_list) > max_results:
                    #     papers_list = papers_list[:max_results]
                  
                    if papers_list:
                        df = pd.DataFrame(papers_list)
                        st.success(f"✅ Showing {len(df)} papers (limited by Max Results).")
                        st.dataframe(df)

                        if not os.path.exists("../data"):
                            os.makedirs("../data")

                        df.to_csv("../data/master.csv", index=False)
                        st.info("Results saved to data/master.csv")
                    else:
                        st.warning("No papers found from the selected sources.")

                else:
                    st.error(f"API error: {response.status_code} {response.text}")

            except Exception as e:
                st.error(f"Error fetching papers: {e}")
