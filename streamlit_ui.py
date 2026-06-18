"""Streamlit UI for the Andromeda Agent.

Chat interface with required input, web-search toggle, and multi-turn memory.
Run with: streamlit run streamlit_ui.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from agent import GRAPH_RUN_CONFIG, graph

load_dotenv()


def init_session_state() -> None:
    """Initialize Streamlit session state."""
    defaults = {
        "messages": [],
        "query_count": 0,
        "web_search_enabled": False,
        "auto_send_query": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


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


def process_user_message(user_text: str) -> None:
    """Send user message to the agent and append the response to history."""
    user_text = user_text.strip()
    if not user_text:
        st.error("User input is required. Please type a message before sending.")
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
            }

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
        user_turns = sum(1 for m in st.session_state.messages if m.get("role") == "user")
        st.metric("Messages in memory", turn_count)
        st.caption(
            "The agent receives the full conversation on every turn, "
            "so follow-ups like *email those results* or *explain that* work."
        )

        if st.button("🗑️ Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.query_count = 0
            st.rerun()

        st.divider()

        st.subheader("Agent Capabilities")
        for cap in (
            "🧮 Scientific Calculator (Casio-style)",
            "🔍 Web Search (toggle below input bar)",
            "🗂️ File Search",
            "📄 PDF Generation",
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
    """Main Streamlit app."""
    import os

    st.set_page_config(
        page_title="Andromeda Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()
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
