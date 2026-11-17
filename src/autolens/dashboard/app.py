from __future__ import annotations

import httpx
import streamlit as st

from autolens.common.config import get_settings

PAGES = [
    "Market",
    "Brands",
    "Price check",
    "Time on market",
    "Suspicious listings",
    "Pipeline health",
]

LIMITATIONS = (
    "Asking prices, not transaction prices. Delisting is a proxy for sale, not proof of one."
)


def price_check(api_base: str, api_key: str) -> None:
    st.subheader("Price check")
    with st.form("estimate"):
        c1, c2 = st.columns(2)
        make = c1.text_input("Make", "Toyota")
        model = c2.text_input("Model", "Corolla")
        year = c1.number_input("Year", 1980, 2027, 2018)
        mileage = c2.number_input("Mileage (km)", 0, 2_000_000, 90_000, step=1000)
        submitted = st.form_submit_button("Estimate")
    if not submitted:
        return
    try:
        r = httpx.post(
            f"{api_base}/price/estimate",
            json={"make": make, "model": model, "year": int(year), "mileage_km": int(mileage)},
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        r.raise_for_status()
    except httpx.HTTPError as exc:
        st.error(f"API error: {exc}")
        return
    data = r.json()
    st.metric("Typical asking range (EGP)", f"{data['lo']:,.0f} - {data['hi']:,.0f}")
    st.caption(f"Median {data['median']:,.0f} | {data['model_version']} | {data['disclaimer']}")
    for w in data.get("warnings", []):
        st.warning(w)


def main() -> None:
    settings = get_settings()
    st.set_page_config(page_title="AutoLens Egypt", layout="wide")
    page = st.sidebar.radio("Page", PAGES)
    if page == "Price check":
        price_check(settings.api_base_url, settings.api_key)
    else:
        st.subheader(page)
        st.info("Page not implemented yet.")
    st.caption(LIMITATIONS)


main()
