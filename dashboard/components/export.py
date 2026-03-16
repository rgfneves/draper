from __future__ import annotations


def download_csv_button(df, filename: str, label: str = "Export CSV") -> None:
    """Renders a Streamlit download button for a DataFrame as CSV."""
    import streamlit as st

    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=label,
        data=csv_data,
        file_name=filename,
        mime="text/csv",
    )
