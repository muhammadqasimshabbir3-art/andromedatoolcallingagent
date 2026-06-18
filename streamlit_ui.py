"""Streamlit UI for the Andromeda Agent.

A web interface to interact with the multi-tool ChatGroq-powered agent.
Run with: streamlit run streamlit_ui.py
"""

import asyncio
import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from agent import graph, GRAPH_RUN_CONFIG

load_dotenv()


def init_session_state():
    """Initialize Streamlit session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "query_count" not in st.session_state:
        st.session_state.query_count = 0
    if "web_search_enabled" not in st.session_state:
        st.session_state.web_search_enabled = False
    if "current_query" not in st.session_state:
        st.session_state.current_query = ""


def format_message(message) -> str:
    """Format a message for display."""
    if hasattr(message, "tool_calls") and message.tool_calls:
        tool_info = "🔧 **Tools Used:**\n"
        for tool_call in message.tool_calls:
            tool_name = tool_call.get("name", "Unknown")
            args = tool_call.get("args", {})
            tool_info += f"- **{tool_name}**: {args}\n"
        return tool_info
    elif hasattr(message, "content"):
        return message.content
    else:
        return str(message)


def display_sidebar():
    """Display the sidebar with information."""
    with st.sidebar:
        st.title("⚙️ Configuration")

        # Show API status
        st.subheader("API Status")
        col1, col2 = st.columns(2)

        with col1:
            if os.getenv("GROQ_API_KEY"):
                st.success("✓ Groq API")
            else:
                st.error("✗ Groq API")

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

        # Agent capabilities
        st.subheader("Agent Capabilities")
        capabilities = [
            "🧮 Scientific Calculator (Casio-style)",
            "🔍 Web Search (toggle in input bar, no API key)",
            "🗂️ File Search",
            "📄 PDF Generation",
            "📧 Email Reports (Gmail SMTP)",
            "💬 Natural Conversation",
        ]

        for cap in capabilities:
            st.write(f"- {cap}")

        st.divider()

        # Example queries
        st.subheader("Example Queries")

        example_queries = [
            "What is log(1000) + sin(30)?",
            "Generate a PDF report about AI and email it to me",
            "Search the web for Python best practices",
            "Find all CSV files in current directory",
            "Email me a summary of today's findings as a report",
        ]

        for query in example_queries:
            if st.button(f"📌 {query[:40]}...", use_container_width=True):
                st.session_state.current_query = query
                if "search" in query.lower():
                    st.session_state.web_search_enabled = True

        st.divider()

        # Statistics
        st.subheader("Statistics")
        st.metric("Queries Processed", st.session_state.query_count)


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Andromeda Agent",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize session state
    init_session_state()

    # Display header
    col1, col2 = st.columns([1, 4])
    with col1:
        st.image(
            "https://via.placeholder.com/100?text=🤖",
            width=100,
        )
    with col2:
        st.title("🤖 Andromeda Agent")
        st.markdown("Multi-tool Chatbot with Calculator, Email, Web Search & More")
        st.caption("Workflow: see AgentWorkflow.md | Start: ./start.sh ui")

    st.divider()

    # Display sidebar
    display_sidebar()

    # Main chat interface
    st.subheader("💬 Chat Interface")

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for i, msg in enumerate(st.session_state.messages):
            if msg.get("role") == "user":
                with st.chat_message("user", avatar="👤"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(msg["content"])

    st.divider()

    # Input area: search toggle + required text input + send
    st.caption("User input is required. Enable 🔍 to allow web search when the agent decides it is needed.")

    col_search, col_input, col_send = st.columns([1, 6, 1])

    with col_search:
        st.session_state.web_search_enabled = st.toggle(
            "🔍",
            value=st.session_state.web_search_enabled,
            help="Enable web search (DuckDuckGo). The decision agent searches only when your query needs live information.",
        )

    default_query = st.session_state.pop("current_query", "")

    with col_input:
        user_input = st.text_input(
            "Your question *",
            value=default_query,
            placeholder="Ask me anything — math, PDF reports, email, file search...",
            key="user_input",
            label_visibility="collapsed",
        )

    with col_send:
        send_button = st.button("Send", use_container_width=True, type="primary")

    if send_button:
        if not user_input or not user_input.strip():
            st.error("Please enter your question before sending.")
        else:
            user_input = user_input.strip()
            st.session_state.messages.append(
                {
                    "role": "user",
                    "content": user_input,
                    "timestamp": datetime.now().isoformat(),
                }
            )

            st.session_state.query_count += 1

            with st.spinner("🔍 Processing your request..."):
                try:
                    messages = []
                    for msg in st.session_state.messages[:-1]:
                        if msg.get("role") == "user":
                            messages.append(HumanMessage(content=msg["content"]))
                        elif msg.get("role") == "assistant":
                            messages.append(AIMessage(content=msg["content"]))
                    messages.append(HumanMessage(content=user_input))

                    inputs = {
                        "messages": messages,
                        "user_input": user_input,
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

                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": response_text,
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": error_msg,
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            st.rerun()

    # Display environment check
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
            st.error("⚠️ GROQ_API_KEY is not set. Please configure it.")


if __name__ == "__main__":
    main()

