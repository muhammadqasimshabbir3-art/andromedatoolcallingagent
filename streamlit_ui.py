"""Streamlit UI for the Andromeda Agent.

Chat interface with required input, web-search toggle, and multi-turn memory.
Run with: streamlit run streamlit_ui.py
"""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from agent import GRAPH_RUN_CONFIG, graph
from agent.custom_tools.location_tools import wants_location

load_dotenv()


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    defaults = {
        "messages": [],
        "query_count": 0,
        "web_search_enabled": False,
        "auto_send_query": None,
        "pending_location_query": None,
        "user_latitude": 0.0,
        "user_longitude": 0.0,
        "location_permission_denied": False,
        "pdf_data_base64": "",
        "pdf_filename": "",
        "pdf_file_signature": "",
        "pdf_analysis_enabled": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _query_param_value(name: str) -> str:
    """Read a query param value across Streamlit versions."""
    if hasattr(st, "query_params"):
        params = st.query_params
    else:
        params = st.experimental_get_query_params()

    value = params.get(name, "")
    if isinstance(value, list):
        return value[0] if value else ""
    return str(value)


def sync_browser_location_from_query_params() -> None:
    """Copy browser geolocation callback values into session state."""
    status = _query_param_value("andromeda_location_status")
    if status == "denied":
        st.session_state.location_permission_denied = True
        return

    lat_raw = _query_param_value("andromeda_lat")
    lng_raw = _query_param_value("andromeda_lng")
    if not lat_raw or not lng_raw:
        return

    try:
        st.session_state.user_latitude = float(lat_raw)
        st.session_state.user_longitude = float(lng_raw)
        st.session_state.location_permission_denied = False
    except ValueError:
        return


def has_browser_location() -> bool:
    """Return True when Streamlit has real browser coordinates."""
    return bool(st.session_state.user_latitude or st.session_state.user_longitude)


def request_browser_location() -> None:
    """Ask the browser for location permission and round-trip via query params."""
    components.html(
        """
        <script>
        const params = new URLSearchParams(window.parent.location.search);
        let completed = false;

        function updateLocationParams(values) {
          if (completed) return;
          completed = true;
          Object.entries(values).forEach(([key, value]) => params.set(key, value));
          window.parent.location.search = params.toString();
        }

        if (!navigator.geolocation) {
          updateLocationParams({ andromeda_location_status: "denied" });
        } else {
          window.setTimeout(() => {
            updateLocationParams({ andromeda_location_status: "timeout" });
          }, 12000);

          navigator.geolocation.getCurrentPosition(
            (pos) => updateLocationParams({
              andromeda_location_status: "granted",
              andromeda_lat: String(pos.coords.latitude),
              andromeda_lng: String(pos.coords.longitude),
              andromeda_location_ts: String(Date.now()),
            }),
            () => updateLocationParams({ andromeda_location_status: "denied" }),
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
          );
        }
        </script>
        """,
        height=0,
    )


def render_manual_location_form(pending_query: str) -> None:
    """Render a fallback coordinate form for Streamlit geolocation failures."""
    st.warning(
        "Browser location did not reach Streamlit. Enter coordinates below, "
        "or use the React frontend for automatic browser geolocation."
    )

    with st.form("manual_location_form"):
        col_lat, col_lng = st.columns(2)
        with col_lat:
            latitude = st.number_input(
                "Latitude",
                value=float(st.session_state.user_latitude or 0.0),
                format="%.8f",
            )
        with col_lng:
            longitude = st.number_input(
                "Longitude",
                value=float(st.session_state.user_longitude or 0.0),
                format="%.8f",
            )

        submitted = st.form_submit_button("Continue with these coordinates")

    if submitted:
        st.session_state.user_latitude = float(latitude)
        st.session_state.user_longitude = float(longitude)
        st.session_state.location_permission_denied = False
        st.session_state.pending_location_query = None
        process_user_message(pending_query)
        st.rerun()


def build_langchain_messages(history: list[dict]) -> list:
    """Convert UI chat history to LangChain messages for graph memory."""
    lc_messages = []
    for msg in history:
        if msg.get("role") == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg.get("role") == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
    return lc_messages


def format_message(message) -> str:
    """Format an agent message for display."""
    if hasattr(message, "tool_calls") and message.tool_calls:
        tool_info = "🔧 **Tools Used:**\n"
        for tool_call in message.tool_calls:
            tool_name = tool_call.get("name", "Unknown")
            args = tool_call.get("args", {})
            tool_info += f"- **{tool_name}**: {args}\n"
        return tool_info
    if hasattr(message, "content"):
        return str(message.content)
    return str(message)


def process_user_message(user_text: str, pdf_summarize_only: bool = False) -> None:
    """Send user message to the agent and append the response to history."""
    user_text = user_text.strip()
    if not user_text:
        st.error("User input is required. Please type a message before sending.")
        return

    if wants_location(user_text) and not has_browser_location():
        if not st.session_state.location_permission_denied:
            st.session_state.pending_location_query = user_text
            st.info("Please allow location access in your browser to continue.")
            return

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_text,
            "timestamp": datetime.now().isoformat(),
        }
    )
    st.session_state.query_count += 1

    with st.spinner("Andromeda is thinking..."):
        try:
            lc_messages = build_langchain_messages(st.session_state.messages)
            inputs = {
                "messages": lc_messages,
                "user_input": user_text,
                "web_search_enabled": st.session_state.web_search_enabled,
                "user_latitude": st.session_state.user_latitude,
                "user_longitude": st.session_state.user_longitude,
            }
            if st.session_state.pdf_analysis_enabled and st.session_state.pdf_data_base64:
                inputs.update(
                    {
                        "pdf_data_base64": st.session_state.pdf_data_base64,
                        "pdf_filename": st.session_state.pdf_filename or "uploaded.pdf",
                        "pdf_summarize_only": pdf_summarize_only,
                    }
                )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                graph.ainvoke(inputs, config=GRAPH_RUN_CONFIG)
            )

            if result and result.get("messages"):
                agent_response = result["messages"][-1]
                response_text = format_message(agent_response)
            else:
                response_text = "I could not generate a response. Please try again."

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        except Exception as exc:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": f"❌ Error: {exc}",
                    "timestamp": datetime.now().isoformat(),
                }
            )


def display_sidebar() -> None:
    """Display sidebar configuration and conversation controls."""
    import os

    with st.sidebar:
        st.title("⚙️ Configuration")

        st.subheader("API Status")
        col1, col2 = st.columns(2)
        with col1:
            st.success("✓ Groq API") if os.getenv("GROQ_API_KEY") else st.error("✗ Groq API")
        with col2:
            if os.getenv("LANGSMITH_API_KEY"):
                st.success("✓ LangSmith")
            else:
                st.warning("✗ LangSmith")

        if os.getenv("GMAIL_SMTP_USER") and os.getenv("GMAIL_APP_PASSWORD"):
            st.success("✓ Gmail SMTP")
        else:
            st.warning("✗ Gmail SMTP")

        st.divider()

        st.subheader("Conversation")
        turn_count = len(st.session_state.messages)
        st.metric("Messages in memory", turn_count)
        st.caption(
            "The agent receives the full conversation on every turn, "
            "so follow-ups like *email those results* or *explain that* work."
        )

        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.query_count = 0
            st.session_state.pending_location_query = None
            st.session_state.location_permission_denied = False
            st.rerun()

        if st.session_state.pdf_filename:
            st.divider()
            st.subheader("PDF Analysis")
            st.caption(f"Loaded: {st.session_state.pdf_filename}")
            st.session_state.pdf_analysis_enabled = st.toggle(
                "Ask uploaded PDF",
                value=st.session_state.pdf_analysis_enabled,
                help="When enabled, messages are answered only from the uploaded PDF.",
            )
            if st.button("Clear uploaded PDF", use_container_width=True):
                st.session_state.pdf_data_base64 = ""
                st.session_state.pdf_filename = ""
                st.session_state.pdf_file_signature = ""
                st.session_state.pdf_analysis_enabled = False
                st.rerun()

        st.divider()

        st.subheader("Agent Capabilities")
        for cap in (
            "🧮 Scientific Calculator (Casio-style)",
            "🔍 Web Search (toggle below input bar)",
            "🗂️ File Search",
            "📄 PDF Generation",
            "📑 PDF Analysis with RAG",
            "📧 Email Reports (Gmail SMTP)",
            "💬 Multi-turn conversation memory",
        ):
            st.write(f"- {cap}")

        st.divider()

        st.subheader("Example Queries")
        examples = [
            "What is log(1000) + sin(30)?",
            "Generate a PDF report about AI and email it to me",
            "Search the web for Python best practices",
            "Find all CSV files in current directory",
            "Email me a summary of today's findings",
        ]
        for query in examples:
            if st.button(f"📌 {query[:38]}...", use_container_width=True, key=f"ex_{query[:20]}"):
                st.session_state.auto_send_query = query
                if "search" in query.lower():
                    st.session_state.web_search_enabled = True
                st.rerun()

        st.divider()
        st.metric("Queries processed", st.session_state.query_count)


def main() -> None:
    """Run the main Streamlit app."""
    import os

    st.set_page_config(
        page_title="Andromeda Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()
    sync_browser_location_from_query_params()
    display_sidebar()

    col_logo, col_title = st.columns([1, 5])
    with col_logo:
        st.markdown("## 🤖")
    with col_title:
        st.title("Andromeda Agent")
        st.markdown(
            "Multi-tool assistant — calculator, web search, files, PDF, email. "
            "**Conversation memory is on.**"
        )

    st.divider()

    with st.expander("📑 Upload PDF for Analysis", expanded=not bool(st.session_state.pdf_filename)):
        uploaded_pdf = st.file_uploader(
            "Upload a PDF",
            type=["pdf"],
            accept_multiple_files=False,
            help="The agent extracts text, builds a Chroma vector index, summarizes the document, and answers follow-up questions only from the PDF.",
        )
        if uploaded_pdf is not None:
            pdf_bytes = uploaded_pdf.getvalue()
            signature = f"{uploaded_pdf.name}:{len(pdf_bytes)}"
            if signature != st.session_state.pdf_file_signature:
                st.session_state.pdf_data_base64 = base64.b64encode(pdf_bytes).decode("ascii")
                st.session_state.pdf_filename = uploaded_pdf.name
                st.session_state.pdf_file_signature = signature
                st.session_state.pdf_analysis_enabled = True
                process_user_message(
                    f"Summarize the uploaded PDF named {uploaded_pdf.name}.",
                    pdf_summarize_only=True,
                )
                st.rerun()

        if st.session_state.pdf_filename:
            st.success(f"PDF ready: {st.session_state.pdf_filename}")
            st.caption(
                "Ask follow-up questions in chat while 'Ask uploaded PDF' is enabled in the sidebar."
            )

    # --- Conversation history ---
    if not st.session_state.messages:
        st.info(
            "Start a conversation below. User input is **required**. "
            "Enable 🔍 for web search when needed."
        )

    for msg in st.session_state.messages:
        role = msg.get("role", "assistant")
        avatar = "👤" if role == "user" else "🤖"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg.get("content", ""))

    if st.session_state.pending_location_query:
        pending = st.session_state.pending_location_query
        if has_browser_location():
            st.session_state.pending_location_query = None
            process_user_message(pending)
            st.rerun()
        if st.session_state.location_permission_denied:
            render_manual_location_form(pending)
            st.stop()

        status = _query_param_value("andromeda_location_status")
        if status == "timeout":
            render_manual_location_form(pending)
            st.stop()

        st.info("Please approve the browser location request to continue.")
        with st.spinner("Waiting for browser location..."):
            request_browser_location()
        render_manual_location_form(pending)
        st.stop()

    # Auto-send from sidebar example buttons
    if st.session_state.auto_send_query:
        pending = st.session_state.auto_send_query
        st.session_state.auto_send_query = None
        process_user_message(pending)
        st.rerun()

    # --- Input bar: web search toggle + chat input ---
    st.markdown("##### Send a message")
    st.caption("User input is required · Toggle 🔍 to allow web search · Agent remembers this conversation")

    input_col, chat_col = st.columns([1, 11], vertical_alignment="bottom")

    with input_col:
        st.session_state.web_search_enabled = st.toggle(
            "🔍 Web",
            value=st.session_state.web_search_enabled,
            help="Enable web search. The decision agent uses it only when your query needs live information.",
        )

    with chat_col:
        user_prompt = st.chat_input(
            "Type your message here (required)...",
            key="chat_input",
        )

    if user_prompt is not None:
        if not user_prompt.strip():
            st.error("User input is required. Please enter a message.")
        else:
            process_user_message(user_prompt)
            st.rerun()

    st.divider()

    with st.expander("🔍 Environment Check"):
        env_check = {
            "GROQ_API_KEY": "✓" if os.getenv("GROQ_API_KEY") else "✗",
            "LANGSMITH_API_KEY": "✓" if os.getenv("LANGSMITH_API_KEY") else "⚠",
            "GMAIL_SMTP_USER": "✓" if os.getenv("GMAIL_SMTP_USER") else "⚠",
            "GMAIL_APP_PASSWORD": "✓" if os.getenv("GMAIL_APP_PASSWORD") else "⚠",
        }
        for key, status in env_check.items():
            st.write(f"{key}: {status}")
        if not os.getenv("GROQ_API_KEY"):
            st.error("GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")


if __name__ == "__main__":
    main()
