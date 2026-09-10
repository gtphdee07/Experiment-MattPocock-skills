"""main() changes only - copy these edits into apps/streamlit/streamlit_app.py.
Everything else in the file (the five _step_* functions, _goto/_start_over,
the imports) is unchanged from the current version.
"""

# --- add near the top, alongside the other towing_streamlit import ---
# (results.py already exports check_box_html / grid_checks - no new import needed)

OPTIONAL_CSS = """
<style>
/* OPTIONAL: sticky Back / Start-over footer on the results screen so the
   reset action is always reachable without scrolling back up on a phone. */
div[data-testid="stHorizontalBlock"]:has(button:contains("Start over")) {
  position: sticky;
  bottom: 0;
  background: var(--background-color, #f6efe4);
  padding: 0.75rem 0 0.5rem;
  border-top: 1px solid #ddd3c0;
}

/* OPTIONAL: subtle staggered entrance for the 6 result boxes. */
@keyframes twlc-rise {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
div[data-testid="column"] > div:has(> div[style*="border-radius:1rem"]) {
  animation: twlc-rise 260ms ease-out both;
}
div[data-testid="column"]:nth-child(2) > div { animation-delay: 40ms; }
div[data-testid="column"]:nth-child(3) > div { animation-delay: 80ms; }
</style>
"""


def main() -> None:
    st.set_page_config(
        page_title="Towing Limit Checker",
        page_icon="assets/wtwt-favicon-mono.png",
    )
    st.logo("assets/wtwt-logo.png")
    st.markdown(OPTIONAL_CSS, unsafe_allow_html=True)  # remove this line to skip the optional polish
    st.title("Towing Limit Checker")
    st.caption(
        "Enter your rig's ratings and a CAT Scale weigh ticket to see whether the "
        "Tow Vehicle and Trailer are within every weight limit. Fully offline - "
        "nothing is saved."
    )

    if "step" not in st.session_state:
        st.session_state.step = 0

    with st.sidebar:
        st.write(f"Step {int(st.session_state.step) + 1} of {_TOTAL_STEPS}")
        if st.button("Start over", key="sidebar_start_over"):
            _start_over()

    _STEPS[int(st.session_state.step)]()
