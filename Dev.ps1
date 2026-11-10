$env:MEDSCOPE_DEV_SETUP_TOKEN = (python -c "import secrets; print(secrets.token_urlsafe(32))")
$env:MEDSCOPE_DEV_SETUP_TOKEN
python -m streamlit run "DCMS V1.py" --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false