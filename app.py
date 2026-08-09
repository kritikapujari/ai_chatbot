"""
app.py

Simple, generic Ollama chatbot built with Streamlit.

Features:
- Select any locally installed Ollama model from the UI.
- Adjust temperature (0.0 - 2.0) from the UI.
- Edit the system prompt from the UI.
- See an "AI Analysis / Reasoning Summary" and a "Final Answer" for every
  response, in that order.
- Maintain chat history for the current session.
- Clear the conversation.

Run with:
    streamlit run app.py
"""

import streamlit as st
from dotenv import load_dotenv

from ollama_client import chat, get_base_url, list_models, OllamaError

load_dotenv()

DEFAULT_SYSTEM_PROMPT = "You are a helpful AI assistant. Give clear and concise answers."

st.set_page_config(page_title="AI Chatbot", page_icon="🤖", layout="wide")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "history" not in st.session_state:
    # Each item: {"user": str, "analysis": str, "answer": str,
    #             "model": str, "temperature": float}
    st.session_state.history = []

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT

base_url = get_base_url()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("⚙️ Settings")
st.sidebar.caption(f"Ollama server: `{base_url}`")

try:
    available_models = list_models(base_url)
    connection_error = None
except OllamaError as exc:
    available_models = []
    connection_error = str(exc)

if connection_error:
    st.sidebar.error(connection_error)

if available_models:
    selected_model = st.sidebar.selectbox("Model", available_models, index=0)
else:
    st.sidebar.warning(
        "No models were found automatically. Make sure Ollama is running "
        "and you have pulled at least one model."
    )
    selected_model = st.sidebar.text_input("Model name (manual entry)", value="llama3")

temperature = st.sidebar.slider(
    "Temperature",
    min_value=0.0,
    max_value=2.0,
    value=0.7,
    step=0.1,
    help="Lower = more focused and deterministic. Higher = more creative and varied.",
)

st.sidebar.subheader("System Prompt")
st.session_state.system_prompt = st.sidebar.text_area(
    "Defines how the AI should behave. Influences both the analysis and the final answer.",
    value=st.session_state.system_prompt,
    height=150,
)

if st.sidebar.button("🗑️ Clear Conversation", use_container_width=True):
    st.session_state.history = []
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Manage models from a terminal:")
st.sidebar.code("ollama list\nollama pull <model-name>", language="bash")

# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------
st.title("🤖AI Chatbot")
st.caption("Simple local chatbot with an AI analysis/reasoning summary, powered by Ollama.")

# Render existing conversation
for turn in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        with st.expander("🔎 AI Analysis / Reasoning", expanded=False):
            st.markdown(turn["analysis"])
        st.markdown(turn["answer"])
        st.caption(f"Model: `{turn['model']}` · Temperature: `{turn['temperature']}`")

# New message input
user_input = st.chat_input("Type your message...")

if user_input:
    if not selected_model:
        st.error("Please select or enter a model name in the sidebar first.")
    else:
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    analysis, answer = chat(
                        model=selected_model,
                        system_prompt=st.session_state.system_prompt,
                        history=st.session_state.history,
                        user_message=user_input,
                        temperature=temperature,
                        base_url=base_url,
                    )
                except OllamaError as exc:
                    analysis = ""
                    answer = f"⚠️ Error: {exc}"

            if analysis:
                with st.expander("🔎 AI Analysis / Reasoning", expanded=False):
                    st.markdown(analysis)
            st.markdown(answer)
            st.caption(f"Model: `{selected_model}` · Temperature: `{temperature}`")

        st.session_state.history.append(
            {
                "user": user_input,
                "analysis": analysis,
                "answer": answer,
                "model": selected_model,
                "temperature": temperature,
            }
        )
