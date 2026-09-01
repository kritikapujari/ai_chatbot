"""
app.py

Streamlit chatbot supporting:

- Ollama
- Gemini
- OpenRouter
- ScrapeGraphAI website scraping

Features:
- Choose Ollama, Gemini, or OpenRouter.
- Select a model for the selected backend.
- Adjust temperature.
- Edit the system prompt.
- Show AI Analysis / Reasoning Summary.
- Show Final Answer.
- Maintain conversation history.
- Clear conversation.
- Detect URLs in user messages.
- Scrape websites with ScrapeGraphAI.
- Reuse previously scraped data for follow-up questions.
- Use the same scraped data with Ollama, Gemini, or OpenRouter.
"""

import streamlit as st
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

from ollama_client import (
    chat as ollama_chat,
    build_external_data_block as ollama_build_external_data_block,
    get_base_url as get_ollama_base_url,
    list_models as list_ollama_models,
    OllamaError,
)

# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

from gemini_client import (
    chat as gemini_chat,
    build_external_data_block as gemini_build_external_data_block,
    list_models as list_gemini_models,
    GeminiError,
)

# ---------------------------------------------------------------------------
# OpenRouter backend
# ---------------------------------------------------------------------------

from openrouter_client import (
    chat as openrouter_chat,
    build_external_data_block as openrouter_build_external_data_block,
    OpenRouterError,
)

# ---------------------------------------------------------------------------
# Website scraper
# ---------------------------------------------------------------------------

from web_scraper import (
    find_first_url,
    strip_url,
    scrape_website,
    ScraperError,
    MAX_SCRAPED_CONTENT_CHARS,
)

load_dotenv()


# ===========================================================================
# Configuration
# ===========================================================================

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. "
    "Give clear and concise answers."
)

DEFAULT_BACKEND = "Ollama"

BACKENDS = [
    "Ollama",
    "Gemini",
    "OpenRouter",
]


# ===========================================================================
# Page configuration
# ===========================================================================

st.set_page_config(
    page_title="AI Chatbot",
    page_icon="🤖",
    layout="wide",
)


# ===========================================================================
# Session state
# ===========================================================================

if "history" not in st.session_state:
    # Each turn contains:
    #
    # {
    #     "user": str,
    #     "analysis": str,
    #     "answer": str,
    #     "backend": str,
    #     "model": str,
    #     "temperature": float,
    #     "source_url": str | None,
    #     "scraped_data": str | None,
    #     "truncated": bool,
    # }
    #
    st.session_state.history = []


if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT


if "backend" not in st.session_state:
    st.session_state.backend = DEFAULT_BACKEND


# ===========================================================================
# Sidebar
# ===========================================================================

st.sidebar.title("⚙️ Settings")


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------

current_backend_index = (
    BACKENDS.index(st.session_state.backend)
    if st.session_state.backend in BACKENDS
    else 0
)

backend = st.sidebar.radio(
    "🤖 AI Backend",
    BACKENDS,
    index=current_backend_index,
)

st.session_state.backend = backend


# ===========================================================================
# Backend-specific configuration
# ===========================================================================

selected_model = None

ollama_base_url = None

connection_error = None


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

if backend == "Ollama":

    ollama_base_url = get_ollama_base_url()

    st.sidebar.caption(
        f"Ollama server: `{ollama_base_url}`"
    )

    try:
        available_models = list_ollama_models(
            ollama_base_url
        )

    except OllamaError as exc:
        available_models = []
        connection_error = str(exc)

    if connection_error:
        st.sidebar.error(connection_error)

    if available_models:

        selected_model = st.sidebar.selectbox(
            "Ollama Model",
            available_models,
            index=0,
        )

    else:

        st.sidebar.warning(
            "No Ollama models were found automatically. "
            "Make sure Ollama is running and you have "
            "pulled at least one model."
        )

        selected_model = st.sidebar.text_input(
            "Ollama model name",
            value="llama3",
        )


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

elif backend == "Gemini":

    st.sidebar.caption(
        "Using Google Gemini API"
    )

    try:
        available_models = list_gemini_models()

    except GeminiError as exc:
        available_models = []
        connection_error = str(exc)

    if connection_error:
        st.sidebar.error(connection_error)

    if available_models:

        preferred_models = [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3-flash-preview",
            "gemini-flash-latest",
        ]

        default_index = 0

        for preferred in preferred_models:

            if preferred in available_models:
                default_index = available_models.index(
                    preferred
                )
                break

        selected_model = st.sidebar.selectbox(
            "Gemini Model",
            available_models,
            index=default_index,
        )

    else:

        st.sidebar.warning(
            "Could not retrieve Gemini models."
        )

        selected_model = st.sidebar.text_input(
            "Gemini model name",
            value="gemini-3.6-flash",
        )


# ---------------------------------------------------------------------------
# OpenRouter
# ---------------------------------------------------------------------------

else:

    st.sidebar.caption(
        "Using OpenRouter API"
    )

    st.sidebar.info(
        "OpenRouter provides access to multiple hosted "
        "models through one API."
    )

    selected_model = st.sidebar.text_input(
    "OpenRouter Model",
    value="dots-studio/dots-3-note-preview:free",
    help="Using Thinking Machines: Inkling Small (free).",
    )
    


# ===========================================================================
# Temperature
# ===========================================================================

temperature = st.sidebar.slider(
    "Temperature",
    min_value=0.0,
    max_value=2.0,
    value=0.7,
    step=0.1,
    help=(
        "Lower = more focused and deterministic. "
        "Higher = more creative and varied."
    ),
)


# ===========================================================================
# System prompt
# ===========================================================================

st.sidebar.subheader("System Prompt")

st.session_state.system_prompt = st.sidebar.text_area(
    "Defines how the AI should behave.",
    value=st.session_state.system_prompt,
    height=150,
)


# ===========================================================================
# Clear conversation
# ===========================================================================

if st.sidebar.button(
    "🗑️ Clear Conversation",
    use_container_width=True,
):

    st.session_state.history = []

    st.rerun()


# ===========================================================================
# Backend information
# ===========================================================================

st.sidebar.markdown("---")

if backend == "Ollama":

    st.sidebar.caption(
        "Ollama runs locally on your computer."
    )

    st.sidebar.code(
        "ollama list\n"
        "ollama pull <model-name>",
        language="bash",
    )

elif backend == "Gemini":

    st.sidebar.caption(
        "Gemini uses GEMINI_API_KEY from your .env file."
    )

else:

    st.sidebar.caption(
        "OpenRouter uses OPENROUTER_API_KEY from your .env file."
    )


# ===========================================================================
# Website scraping information
# ===========================================================================

st.sidebar.markdown("---")

st.sidebar.subheader("🌐 Website Scraping")

st.sidebar.caption(
    "Paste a URL anywhere in your message and ask "
    "a question about it. ScrapeGraphAI will extract "
    "information from the page."
)

st.sidebar.caption(
    'Example: "Summarize https://example.com"'
)

st.sidebar.caption(
    f"Scraped content is capped at "
    f"{MAX_SCRAPED_CONTENT_CHARS:,} characters."
)

st.sidebar.info(
    "ScrapeGraphAI currently uses the Ollama configuration "
    "from web_scraper.py for the scraping/extraction step. "
    "The resulting website data can then be sent to "
    "Ollama, Gemini, or OpenRouter for the final answer."
)


# ===========================================================================
# Main area
# ===========================================================================

st.title("🤖 AI Chatbot")

st.caption(
    "Ollama + Gemini + OpenRouter with "
    "AI analysis, conversation history, "
    "and ScrapeGraphAI website scraping."
)


# ===========================================================================
# Helper: Render assistant turn
# ===========================================================================

def render_assistant_turn(turn: dict):
    """
    Render one assistant response.
    """

    analysis = turn.get(
        "analysis",
        "",
    )

    answer = turn.get(
        "answer",
        "",
    )

    # -----------------------------------------------------------------------
    # Analysis
    # -----------------------------------------------------------------------

    if analysis:

        with st.expander(
            "🔎 AI Analysis / Reasoning",
            expanded=False,
        ):

            st.markdown(analysis)

    # -----------------------------------------------------------------------
    # Website source
    # -----------------------------------------------------------------------

    if turn.get("source_url"):

        st.caption(
            f"🌐 Source: {turn['source_url']}"
        )

        if turn.get("scraped_data"):

            label = "📄 Scraped Data"

            if turn.get("truncated"):

                label += (
                    " (truncated to fit the context window)"
                )

            with st.expander(
                label,
                expanded=False,
            ):

                st.code(
                    turn["scraped_data"],
                    language="text",
                )

    # -----------------------------------------------------------------------
    # Final answer
    # -----------------------------------------------------------------------

    st.markdown(answer)

    st.caption(
        f"{turn.get('backend', '')} · "
        f"Model: `{turn.get('model', '')}` · "
        f"Temperature: `{turn.get('temperature', '')}`"
    )


# ===========================================================================
# Helper: Generate response
# ===========================================================================

def generate_chat_response(
    backend_name,
    model,
    system_prompt,
    history,
    user_message,
    temperature_value,
    external_context=None,
):
    """
    Send a request to the selected backend.

    Returns:
        (analysis, answer)
    """

    # -----------------------------------------------------------------------
    # Gemini
    # -----------------------------------------------------------------------

    if backend_name == "Gemini":

        return gemini_chat(
            model=model,
            system_prompt=system_prompt,
            history=history,
            user_message=user_message,
            temperature=temperature_value,
            external_context=external_context,
        )

    # -----------------------------------------------------------------------
    # OpenRouter
    # -----------------------------------------------------------------------

    if backend_name == "OpenRouter":

        return openrouter_chat(
            model=model,
            system_prompt=system_prompt,
            history=history,
            user_message=user_message,
            temperature=temperature_value,
            external_context=external_context,
        )

    # -----------------------------------------------------------------------
    # Ollama
    # -----------------------------------------------------------------------

    return ollama_chat(
        model=model,
        system_prompt=system_prompt,
        history=history,
        user_message=user_message,
        temperature=temperature_value,
        base_url=ollama_base_url,
        external_context=external_context,
    )


# ===========================================================================
# Helper: Build external data context
# ===========================================================================

def build_external_context(
    backend_name,
    source_url,
    scraped_data,
):
    """
    Build the untrusted external-data block using
    the selected final-answer backend.
    """

    if backend_name == "Gemini":

        return gemini_build_external_data_block(
            source_url,
            scraped_data,
        )

    if backend_name == "OpenRouter":

        return openrouter_build_external_data_block(
            source_url,
            scraped_data,
        )

    return ollama_build_external_data_block(
        source_url,
        scraped_data,
    )


# ===========================================================================
# Render existing conversation
# ===========================================================================

for turn in st.session_state.history:

    with st.chat_message("user"):

        st.markdown(
            turn["user"]
        )

    with st.chat_message("assistant"):

        render_assistant_turn(turn)


# ===========================================================================
# New message
# ===========================================================================

user_input = st.chat_input(
    "Type your message, or paste a URL to ask about a website..."
)


if user_input:

    # -----------------------------------------------------------------------
    # Validate model
    # -----------------------------------------------------------------------

    if not selected_model:

        st.error(
            "Please select or enter a model name first."
        )

    else:

        # -------------------------------------------------------------------
        # Display user message
        # -------------------------------------------------------------------

        with st.chat_message("user"):

            st.markdown(
                user_input
            )

        # -------------------------------------------------------------------
        # Assistant response
        # -------------------------------------------------------------------

        with st.chat_message("assistant"):

            # ===============================================================
            # Determine scraping behavior
            # ===============================================================

            url = find_first_url(
                user_input
            )

            previous_turn = (
                st.session_state.history[-1]
                if st.session_state.history
                else None
            )

            has_reusable_context = bool(
                previous_turn
                and previous_turn.get(
                    "scraped_data"
                )
            )

            # ===============================================================
            # Initialize response
            # ===============================================================

            analysis = ""
            answer = ""

            source_url = None
            scraped_data = None
            truncated = False

            # ===============================================================
            # PIPELINE 1
            #
            # New URL -> ScrapeGraphAI
            # -> selected final-answer backend
            # ===============================================================

            if url:

                status = st.status(
                    f"Detected website request for {url}",
                    expanded=False,
                )

                try:

                    # -------------------------------------------------------
                    # Scrape
                    # -------------------------------------------------------

                    status.update(
                        label="Scraping website..."
                    )

                    extraction_prompt = strip_url(
                        user_input,
                        url,
                    )

                    # IMPORTANT:
                    #
                    # Your current web_scraper.py is Ollama-specific.
                    # Therefore it receives the Ollama model/base URL
                    # for the scraping stage.
                    #
                    # The final answer is generated by whichever backend
                    # the user selected in the sidebar.

                    scraper_model = None

                    if ollama_base_url:

                        try:

                            scraper_models = (
                                list_ollama_models(
                                    ollama_base_url
                                )
                            )

                            if scraper_models:

                                scraper_model = (
                                    scraper_models[0]
                                )

                        except Exception:
                            scraper_model = None

                    if not scraper_model:

                        scraper_model = "llama3"

                    scrape_result = scrape_website(
                        url=url,
                        prompt=extraction_prompt,
                        model=scraper_model,
                        temperature=temperature,
                        base_url=(
                            ollama_base_url
                            or "http://localhost:11434"
                        ),
                    )

                    scraped_data = (
                        scrape_result["data"]
                    )

                    truncated = (
                        scrape_result["truncated"]
                    )

                    # -------------------------------------------------------
                    # Build external context
                    # -------------------------------------------------------

                    status.update(
                        label=(
                            "Processing scraped information..."
                        )
                    )

                    external_context = (
                        build_external_context(
                            backend_name=backend,
                            source_url=url,
                            scraped_data=scraped_data,
                        )
                    )

                    # -------------------------------------------------------
                    # Final answer
                    # -------------------------------------------------------

                    status.update(
                        label=(
                            f"Generating answer with "
                            f"{backend}..."
                        )
                    )

                    analysis, answer = (
                        generate_chat_response(
                            backend_name=backend,
                            model=selected_model,
                            system_prompt=(
                                st.session_state.system_prompt
                            ),
                            history=(
                                st.session_state.history
                            ),
                            user_message=user_input,
                            temperature_value=temperature,
                            external_context=(
                                external_context
                            ),
                        )
                    )

                    source_url = url

                    status.update(
                        label="Done",
                        state="complete",
                    )

                except ScraperError as exc:

                    status.update(
                        label="Scraping failed",
                        state="error",
                    )

                    answer = f"⚠️ {exc}"

                except OllamaError as exc:

                    status.update(
                        label="Ollama error",
                        state="error",
                    )

                    answer = f"⚠️ {exc}"

                except GeminiError as exc:

                    status.update(
                        label="Gemini error",
                        state="error",
                    )

                    answer = f"⚠️ {exc}"

                except OpenRouterError as exc:

                    status.update(
                        label="OpenRouter error",
                        state="error",
                    )

                    answer = f"⚠️ {exc}"

                except Exception as exc:

                    status.update(
                        label="Unexpected error",
                        state="error",
                    )

                    answer = (
                        "⚠️ An unexpected error occurred: "
                        f"{exc}"
                    )

            # ===============================================================
            # PIPELINE 2
            #
            # Follow-up -> reuse previous scraped data
            # ===============================================================

            elif has_reusable_context:

                status = st.status(
                    "Using previously scraped website data...",
                    expanded=False,
                )

                try:

                    status.update(
                        label=(
                            f"Generating answer with "
                            f"{backend}..."
                        )
                    )

                    external_context = (
                        build_external_context(
                            backend_name=backend,
                            source_url=(
                                previous_turn[
                                    "source_url"
                                ]
                            ),
                            scraped_data=(
                                previous_turn[
                                    "scraped_data"
                                ]
                            ),
                        )
                    )

                    analysis, answer = (
                        generate_chat_response(
                            backend_name=backend,
                            model=selected_model,
                            system_prompt=(
                                st.session_state.system_prompt
                            ),
                            history=(
                                st.session_state.history
                            ),
                            user_message=user_input,
                            temperature_value=temperature,
                            external_context=(
                                external_context
                            ),
                        )
                    )

                    source_url = (
                        previous_turn[
                            "source_url"
                        ]
                    )

                    scraped_data = (
                        previous_turn[
                            "scraped_data"
                        ]
                    )

                    truncated = (
                        previous_turn.get(
                            "truncated",
                            False,
                        )
                    )

                    status.update(
                        label="Done",
                        state="complete",
                    )

                except OllamaError as exc:

                    status.update(
                        label="Ollama error",
                        state="error",
                    )

                    answer = f"⚠️ {exc}"

                except GeminiError as exc:

                    status.update(
                        label="Gemini error",
                        state="error",
                    )

                    answer = f"⚠️ {exc}"

                except OpenRouterError as exc:

                    status.update(
                        label="OpenRouter error",
                        state="error",
                    )

                    answer = f"⚠️ {exc}"

                except Exception as exc:

                    status.update(
                        label="Unexpected error",
                        state="error",
                    )

                    answer = (
                        "⚠️ An unexpected error occurred: "
                        f"{exc}"
                    )

            # ===============================================================
            # PIPELINE 3
            #
            # Normal chat
            # ===============================================================

            else:

                with st.spinner(
                    f"{backend} is thinking..."
                ):

                    try:

                        analysis, answer = (
                            generate_chat_response(
                                backend_name=backend,
                                model=selected_model,
                                system_prompt=(
                                    st.session_state.system_prompt
                                ),
                                history=(
                                    st.session_state.history
                                ),
                                user_message=user_input,
                                temperature_value=temperature,
                            )
                        )

                    except OllamaError as exc:

                        answer = f"⚠️ {exc}"

                    except GeminiError as exc:

                        answer = f"⚠️ {exc}"

                    except OpenRouterError as exc:

                        answer = f"⚠️ {exc}"

                    except Exception as exc:

                        answer = (
                            "⚠️ An unexpected error occurred: "
                            f"{exc}"
                        )

            # ===============================================================
            # Save turn
            # ===============================================================

            turn = {
                "user": user_input,
                "analysis": analysis,
                "answer": answer,
                "backend": backend,
                "model": selected_model,
                "temperature": temperature,
                "source_url": source_url,
                "scraped_data": scraped_data,
                "truncated": truncated,
            }

            # ===============================================================
            # Render response
            # ===============================================================

            render_assistant_turn(
                turn
            )

        # -------------------------------------------------------------------
        # Save conversation AFTER response is complete
        # -------------------------------------------------------------------

        st.session_state.history.append(
            turn
        )