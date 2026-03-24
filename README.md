# AI Bootcamp — Ollama Model Training Studio

A desktop app for building, training, and testing custom Ollama models. Write your Modelfile, train it with one click, and chat-test it with full conversation history — all in one window.

Built with Python and tkinter. Designed for local LLM development on consumer hardware (Mac Mini, laptops, etc).

---

## What It Does

AI Bootcamp is a training and testing workbench for Ollama models. The workflow is simple: write a Modelfile in the editor, hit Train to build it, then chat-test it in the right panel. Every response is timed and logged so you can see exactly how your model performs.

The chat panel uses Ollama's REST API with full conversation history, so your model remembers everything said in the current session — just like a real deployment.

### Built For

This was built to develop **Ringo**, an AI scheduling assistant for local service businesses (HVAC, plumbing, electrical, junk removal, landscaping, etc). Ringo handles missed calls via SMS, collects what the customer needs, where they are, and when they need it, then hands off a qualified lead to the business owner.

The app itself is model-agnostic — you can use it to build and test any Ollama model.

---

## Requirements

- **Python 3.8+**
- **Ollama** installed and running — [ollama.com](https://ollama.com)
- A base model pulled (e.g. `ollama pull qwen3:8b` or `ollama pull llama3.2:3b`)

### Optional

- **psutil** — enables live CPU/RAM gauges during inference (`pip install psutil`)
- **pynvml** — enables GPU monitoring for NVIDIA cards (`pip install pynvml`)

---

## Quick Start

```bash
# Pull a base model
ollama pull qwen3:8b

# Run the app
python app.py
```

1. Set your model name in the top toolbar (e.g. `ringo`)
2. Write or paste your Modelfile in the editor
3. Click **Train** — watch the Build Log for progress
4. Switch to the Chat panel and start testing

---

## App Layout

```
┌─────────────────────────────────────────────────────┐
│  Toolbar — Model name, Train button, Run button     │
├──────────┬──────────────────┬───────────────────────┤
│          │                  │                       │
│ Sidebar  │  Modelfile       │  Chat Panel           │
│          │  Editor          │                       │
│ • Open   │                  │  Messages + metrics   │
│ • Save   │  (syntax         │  per response         │
│ • List   │   highlighted)   │                       │
│ • Delete │                  │  ┌─────────────────┐  │
│          │  Build Log tab   │  │ CPU ▓▓▓░░  RAM  │  │
│ Installed│                  │  └─────────────────┘  │
│ models   │                  │  [  input + send  ]   │
│          │                  │                       │
├──────────┴──────────────────┴───────────────────────┤
│  Status bar                                         │
└─────────────────────────────────────────────────────┘
```

---

## Features

### Modelfile Editor
Syntax highlighting for `FROM`, `SYSTEM`, `PARAMETER`, `TEMPLATE`, strings, numbers, and comments. Includes line numbers and autosave.

### One-Click Training
Runs `ollama create <name> -f Modelfile` and streams output to the Build Log tab in real time.

### Chat Testing
Full multi-turn conversation support via Ollama's `/api/chat` endpoint. Every response shows elapsed time, word count, and tokens per second.

### Live System Monitor
Real-time CPU, RAM, and GPU gauges (when psutil/pynvml are installed) that animate during inference so you can see how hard your hardware is working.

### Chat Export
Export your full test session to JSON with timestamps, response text, performance metrics, and peak resource usage per message. Useful for comparing Modelfile iterations.

---

## Sidebar Reference

| Action | What it does |
|---|---|
| Open | Load a Modelfile from disk |
| Save As | Save the current editor contents |
| List Models | Show all installed Ollama models |
| Delete Model | Remove the currently named model |
| Export Chat Log | Save all responses to a JSON file |
| Response Stats | Show averages for time, words, speed, and peak CPU/RAM/GPU |
| Clear Chat | Reset conversation history and start fresh |

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Shift+Enter` | New line in chat input |

---

## Ringo — Example Use Case

Ringo is an AI dispatcher for local service businesses. It texts with customers who called while the business was busy, collects what they need (the job), where they are (address), and when they need it (timing/urgency), then outputs a structured `QUALIFIED` payload for handoff to the business owner or an automation pipeline like n8n.

A sample Modelfile for Ringo using Qwen3:8b is included separately. Key details:

- Uses a custom `TEMPLATE` block to disable Qwen3's thinking mode (appends `/no_think` to every user message and pre-fills empty `<think></think>` tags)
- System prompt is kept short — 8B models follow fewer, clearer rules more reliably than long detailed instructions
- Outputs `QUALIFIED:` or `ESCALATE:` signals that downstream automation can parse

---

## Tips

- **Keep system prompts short for small models.** An 8B model with 16GB RAM works best with a focused prompt. Cut examples and rules to the minimum that gets the behavior you want.
- **Test edge cases.** Send messages that give multiple pieces of info at once, ask off-topic questions, or say very little — that's where models break.
- **Export and compare.** After each Modelfile change, export the chat log. Compare response quality and speed across iterations.
- **Clear chat between tests.** Conversation history accumulates and affects responses. Start fresh when testing a new prompt strategy.
- **Watch the gauges.** If RAM stays pinned above 95% during inference, your model may be too large for your hardware. Drop `num_ctx` or try a smaller model.

---

## License

MIT