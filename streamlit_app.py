import os
import requests
import streamlit as st

API_BASE_DEFAULT = os.getenv("API_BASE", "http://localhost:8001")
PUBLIC_API_BASE_DEFAULT = os.getenv("PUBLIC_API_BASE", API_BASE_DEFAULT)

# Streamlit expects page_title instead of title
st.set_page_config(page_title="URL Shortener", layout="centered")

st.title("URL Shortener")
st.caption("Enter a URL to shorten it via the FastAPI backend.")

with st.expander("Settings", expanded=False):
    api_base = st.text_input(
        "API base URL",
        value=API_BASE_DEFAULT,
        help="Backend base URL (internal). In docker-compose this is typically http://api:8001",
    )
    public_api_base = st.text_input(
        "Public API base URL",
        value=PUBLIC_API_BASE_DEFAULT,
        help="Base URL used to display clickable short links (e.g. http://192.168.1.50:8001)",
    )

long_url = st.text_input("Long URL", placeholder="https://example.com/very/long/path")
custom_alias = st.text_input(
    "Custom alias (optional)",
    placeholder="e.g. nas or wifi",
    help="3-32 chars: letters, numbers, _ or -",
)
expire_days = st.number_input("Expire in days", min_value=1, max_value=365, value=7)

if st.button("Shorten", type="primary"):
    if not long_url.strip():
        st.error("Please provide a URL to shorten.")
    else:
        try:
            response = requests.post(
                f"{api_base.rstrip('/')}/url/create",
                json={
                    "original_url": long_url.strip(),
                    "expire_in_days": int(expire_days),
                    **(
                        {"custom_alias": custom_alias.strip()}
                        if custom_alias.strip()
                        else {}
                    ),
                },
                timeout=10,
            )
            if response.ok:
                data = response.json()
                short_code = data.get("short_code")
                if short_code:
                    short_url = f"{public_api_base.rstrip('/')}/r/{short_code}"
                    st.success("Short URL created")
                    st.code(short_url)
                    st.markdown(f"[Open shortened link]({short_url})")
                else:
                    st.error("Backend did not return a short code.")
            else:
                try:
                    err = response.json().get("detail")
                except Exception:
                    err = response.text
                st.error(f"Backend error ({response.status_code}): {err}")
        except requests.RequestException as exc:
            st.error(f"Request failed: {exc}")
