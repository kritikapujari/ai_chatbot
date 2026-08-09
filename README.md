# Ollama Chatbot (v1) — Simple Chat with AI Analysis/Reasoning

A simple, beginner-friendly local chatbot built with **Python + Streamlit + Ollama**.

For every question you ask, the app shows:

```
USER QUESTION
      ↓
AI ANALYSIS / REASONING SUMMARY   (collapsible)
      ↓
FINAL ANSWER
```

You can change the **model**, **temperature**, and **system prompt** live from the UI,
and the app keeps chat history for the current session.

This is intentionally simple — no LangChain, no RAG, no vector databases, no agents.
Those are planned for later phases (see [Future Development](#future-development)).

---

## 1. Project Structure

```
ollama-chatbot/
│
├── app.py              # Streamlit UI
├── ollama_client.py    # Talks to the local Ollama API, parses analysis/answer
├── requirements.txt    # Python dependencies
├── .env.example        # Example environment configuration
├── .gitignore
└── README.md
```

---

## 2. Prerequisites

- **Python 3.9+**
- **VS Code** (recommended, optional)
- **Ollama** installed locally — https://ollama.com/download

Check Python is installed:

```bash
python --version
```

(On macOS/Linux you may need `python3 --version` instead.)

---

## 3. Set Up the Project in VS Code

1. Open VS Code.
2. `File → Open Folder...` → select the `ollama-chatbot` folder.
3. Open a terminal in VS Code: `Terminal → New Terminal`.

---

## 4. Create a Virtual Environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` at the start of your terminal prompt once activated.

In VS Code, you can also select this environment as your Python interpreter:
`Ctrl+Shift+P` (or `Cmd+Shift+P`) → "Python: Select Interpreter" → choose the one inside `venv`.

---

## 5. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 6. Set Up Environment Variables

Copy the example file:

**Windows (cmd):**
```bash
copy .env.example .env
```

**macOS/Linux:**
```bash
cp .env.example .env
```

The default value is already correct for a local install:

```
OLLAMA_BASE_URL=http://localhost:11434
```

Change this only if your Ollama server runs on a different host/port.

---

## 7. Install and Start Ollama

If you haven't installed Ollama yet, download it from https://ollama.com/download
and follow the installer for your OS.

Start the Ollama server (leave this running in its own terminal):

```bash
ollama serve
```

> On macOS/Windows, the Ollama desktop app usually starts this for you automatically.
> If `ollama serve` says the address is already in use, Ollama is likely already running — that's fine.

### Check installed models

```bash
ollama list
```

### Download a model

Pick any model you like. A commonly used general-purpose model is `llama3`:

```bash
ollama pull llama3
```

Other examples you can try later (the app is not tied to any single model):

```bash
ollama pull mistral
ollama pull gemma2
ollama pull qwen2.5
```

The app automatically detects and lists whatever models you've pulled.

---

## 8. Run the Chatbot

With your virtual environment activated and Ollama running:

```bash
streamlit run app.py
```

Streamlit will print a local URL, typically:

```
Local URL: http://localhost:8501
```

Open that URL in your browser (it usually opens automatically).

---

## 9. Using the App

**Sidebar:**
- **Model** — dropdown of models currently installed in Ollama.
- **Temperature** — slider from 0.0 to 2.0.
- **System Prompt** — editable text area that shapes both the analysis and the answer.
- **Clear Conversation** — wipes the current session's chat history.

**Main area:**
- Your messages and the AI's replies appear as a chat.
- Each AI reply has a collapsible **"🔎 AI Analysis / Reasoning"** section, followed by
  the **Final Answer**, and a caption showing which model/temperature produced it.

---

## 10. How It Works (Architecture)

```
        USER
          ↓
   app.py (Streamlit UI)
          ↓
 ollama_client.chat()
          ↓
 Ollama local REST API  →  POST /api/chat
   (http://localhost:11434)
          ↓
      LLM MODEL
          ↓
 raw text response (JSON: {"analysis": "...", "answer": "..."})
          ↓
 ollama_client.parse_response()
          ↓
   analysis + answer
          ↓
   displayed in Streamlit UI
```

### 10.1 How the user's message reaches Ollama

`app.py` collects the message from `st.chat_input()` and passes it, along with the
current model, temperature, and system prompt, to `ollama_client.chat()`. That function
builds a `messages` list (system + prior turns + new message) and sends it to Ollama's
`POST /api/chat` endpoint.

### 10.2 How the system prompt is used

Your system prompt (from the sidebar) is combined with a fixed set of "reasoning
instructions" and sent as the `system` role message. This means your custom instructions
and the reasoning format instructions are both respected on every request.

### 10.3 How the analysis and final answer are generated

The model is instructed (via the system message) to reply with a single JSON object:

```json
{"analysis": "...", "answer": "..."}
```

The request is sent with Ollama's `format: "json"` option, which asks Ollama to
constrain the output to syntactically valid JSON. This is a **single model call** — the
same generation produces both the analysis and the answer together, kept simple on
purpose for v1.

### 10.4 How the analysis is displayed separately

`ollama_client.parse_response()` parses that JSON and splits it into `analysis` and
`answer`. `app.py` renders `analysis` inside a collapsible `st.expander`, and `answer`
directly below it, always visible.

### 10.5 Fallback if the model doesn't return valid JSON

Not every model reliably follows JSON formatting instructions. If JSON parsing fails,
`ollama_client.parse_response()` falls back to looking for `Analysis:` / `Answer:`-style
markers in the raw text. If that also fails, the entire raw response is shown as the
Final Answer, and the analysis section notes that no structured analysis was returned.
This means the app keeps working even with models that don't follow the format well —
you'll just get a plainer response for those models.

### 10.6 How temperature affects generation

The `temperature` value from the slider is passed directly as `options.temperature` in
the Ollama API request. Lower values (near 0.0) make output more deterministic and
focused; higher values (above 1.0) make output more random and creative. This affects
**both** the analysis and the final answer, since they come from the same generation.

### 10.7 How chat history is maintained

`st.session_state.history` stores every turn (`user`, `analysis`, `answer`, `model`,
`temperature`) for the current browser session. On each new message,
`ollama_client.build_messages()` replays prior `user`/`answer` pairs as conversation
context so follow-up questions ("What is it used for?" after "What is Python?") have
the right context. History is **not** persisted to disk — refreshing the Streamlit app
state or restarting it clears it. Long-term memory is intentionally out of scope for v1.

---

## 11. AI Analysis vs. Hidden Chain-of-Thought

It's worth being explicit about what the "AI Analysis" section is — and isn't:

- **AI Analysis / Reasoning Summary (what this app shows):** a short, high-level
  summary of how the model approached your question — what it understood, the approach
  chosen, key concepts considered, and any assumptions/limitations. It's meant to be
  genuinely useful for understanding *how* the model approached the problem.
- **Hidden chain-of-thought (what this app does NOT show):** private, low-level,
  step-by-step internal deliberation some models can produce. This app never asks for
  or exposes that. The prompt explicitly instructs the model to produce a concise
  summary, not a raw internal reasoning trace.

The quality/specificity of the analysis depends on the model you choose — larger,
instruction-tuned models generally produce more useful analyses than smaller ones.

---

## 12. Temperature Experimentation

Try asking the same question at different temperatures and compare the Analysis and
Final Answer each time:

- `0.0` — Most deterministic. Good baseline for comparison.
- `0.3` — Slightly varied, still focused.
- `0.7` — Balanced (a common default).
- `1.0` — Noticeably more varied phrasing/ideas.
- `1.5` – `2.0` — Highly creative, sometimes less coherent or consistent.

What to observe:
- Does the **analysis** structure change, or just the wording?
- Does the **final answer** become more creative, more verbose, or less consistent?
- At high temperatures, does the JSON formatting ever break (triggering the fallback)?

---

## 13. Test Prompts

Try these to explore how the app behaves across different question types:

**General knowledge**
```
What is artificial intelligence?
```
Observe: Analysis should identify this as a definitional question and note it will
cover core AI concepts at a general level.

**Reasoning / problem solving**
```
If a train travels 60 km in 1 hour, how far will it travel in 3 hours?
```
Observe: Analysis should mention the approach (e.g., using speed × time / proportional
reasoning) before the Final Answer states the numeric result.

**Coding**
```
Write a Python function to reverse a string.
```
Observe: Analysis should mention the language, the approach (e.g., slicing vs. loop),
and any assumptions (e.g., no external libraries). Final Answer should contain runnable
code.

**Creative**
```
Give me five creative ideas for an AI project.
```
Observe: At low temperature, ideas may feel more conventional/common; at high
temperature, ideas should feel more varied and unusual.

**Ambiguous**
```
What is the best model?
```
Observe: A good analysis should note the ambiguity (best for what task/goal?) and state
the assumption it's making before answering.

**Multi-turn (test chat history)**
```
1) What is Python?
2) What is it used for?
```
Observe: The second answer should correctly resolve "it" to Python, using the earlier
turn as context.

---

## 14. Troubleshooting

**Ollama is not running**
- Symptom: sidebar shows a connection error, model list is empty.
- Fix: start it with `ollama serve` in a terminal (or open the Ollama desktop app),
  then refresh the Streamlit page.

**Model not found / "model not found" error**
- Check what's installed:
  ```bash
  ollama list
  ```
- Pull the model you want to use:
  ```bash
  ollama pull <model-name>
  ```

**Connection error to Ollama**
- Verify Ollama is running and reachable:
  ```bash
  curl http://localhost:11434/api/tags
  ```
  (On Windows, you can open `http://localhost:11434/api/tags` in a browser instead.)
- Confirm `OLLAMA_BASE_URL` in your `.env` matches where Ollama is actually running.

**Python dependency errors**
- Recreate the virtual environment and reinstall:
  ```bash
  deactivate
  rm -rf venv        # Windows: rmdir /s /q venv
  python -m venv venv
  # activate venv again (see Section 4)
  pip install -r requirements.txt
  ```

**Streamlit doesn't start**
- Confirm the virtual environment is activated (`(venv)` visible in terminal).
- Confirm Streamlit is installed: `pip show streamlit`.
- Try running with the module form: `python -m streamlit run app.py`.
- Make sure you're in the `ollama-chatbot` folder when running the command.

**Model gives malformed / non-JSON output**
- This is expected occasionally with smaller models. The app automatically falls back
  to a plain-text parser, and if that also fails, it simply shows the whole raw
  response as the Final Answer (with a note that no structured analysis was returned).
  No crash — just a less structured display for that one response.

---

## 15. Future Development (Not Implemented Yet)

This version is intentionally minimal. Planned for later phases:

- **Phase 2:** Multiple Ollama models working together (e.g., Model A → Planner,
  Model B → Reasoner, Model C → Final Answer).
- **Phase 3:** Side-by-side model comparison (e.g., Llama vs. Mistral vs. Qwen).
- **Phase 4:** External APIs / tool use.
- **Phase 5:** Retrieval-Augmented Generation (RAG).
- **Phase 6:** More advanced agentic workflows.

The current code is deliberately structured (UI in `app.py`, API logic isolated in
`ollama_client.py`) so these can be layered in later without a rewrite.
