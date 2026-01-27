# System Design Companion

A collaborative agentic workspace for co-creating system designs. Unlike a simple chat bot, the System Design Companion maintains a structured understanding of your problem and evolves solution candidates alongside you.

![App Screenshot](https://placeholder-for-screenshot)

## 🌟 Vision

System design is a complex, iterative process. This tool acts as a **Companion**, not just an assistant. It listens to your ideas, maintains the state of the design (Invariants, Goals, Problems), triggers deep reasoning loops to draft and critique solutions, and persists versioned snapshots of your work.

## 🚀 Key Features

### 1. **Structured Data Model**
The system doesn't just manage a chat history. It maintains a strict **Problem Space** and **Solution Space**:
-   **Problem Space**: Tracks `Invariants` (constraints that must hold), `Goal` (what we are building), `Problem` (current friction), and `Variants` (options being considered).
-   **Solution Space**: Manages multiple `Candidates` (Hypotheses/Models) and their comparative analysis.

### 2. **WIRL Workflow Engine**
Powered by a custom Workflow Intermediate Representation Language (WIRL), the agent follows a rigorous cognitive process:
1.  **Extract**: Parses your natural language into structured invariants and goals.
2.  **Draft**: Generates candidate solutions based on the problem definition.
3.  **Critique**: internal "Red Teaming" to find flaws in the candidates.
4.  **Refine**: Iteratively improves the solution before showing it to you.

### 3. **Workspace & Versioning**
-   **Split UI**: Left panel for the structured Workspace state, Right panel for Chat.
-   **Versioning**: Every coherent change is strictly versioned (e.g., `v1`, `v2`, ...). You can roll back or branch off previous designs.
-   **Persistence**: All workspaces are saved as human-readable Markdown files in `workspaces/`.

## 🛠️ Setup

1.  **Prerequisites**:
    -   Python 3.10+
    -   [Ollama](https://ollama.com/) running locally (Recommended model: `gemma3:27b` or `gpt-oss:20b`).

2.  **Install**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run**:
    ```bash
    streamlit run app/streamlit_app.py
    ```

4.  **Usage**:
    -   Open `http://localhost:8501`.
    -   Click "New Workspace".
    -   Type a design problem (e.g., "Design a dedicated notification service for a ride-sharing app").
    -   Watch the agent populate the Problem Space and generate Candidate Solutions.

## 🏗️ Architecture

-   `app/`: Streamlit frontend and Workspace persistence logic.
-   `workflow_definitions/`: WIRL files and Python backend functions for the agent nodes.
-   `workspaces/`: Local storage for user designs.

## 📄 License

MIT License.
