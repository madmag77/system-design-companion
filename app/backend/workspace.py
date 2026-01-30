import os
import re
import uuid
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from pathlib import Path

# --- Data Models ---

class Invariant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str
    is_active: bool = True

class Variant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    text: str

class ProblemSpace(BaseModel):
    context: str = Field(default="", description="One sentence system description")
    invariants: List[str] = Field(default_factory=list, description="Hard constraints")
    goal: str = Field(default="", description="Single sentence objective")
    problem: str = Field(default="", description="Conflict description")
    variants: List[str] = Field(default_factory=list, description="Degrees of freedom")

class SolutionCandidate(BaseModel):
    id: int
    hypothesis: str = Field(description="Changes in Variants/Invariants")
    model: str = Field(description="Description of the solution")
    reasoning: str = Field(description="Why this is a solution", default="")

class Comparison(BaseModel):
    analysis: str = Field(description="comparative analysis")
    recommendation: str = Field(description="Recommended choice")

class SolutionSpace(BaseModel):
    candidates: List[SolutionCandidate] = Field(default_factory=list)
    comparison: Optional[Comparison] = None
    simplification_feedback: Optional[str] = None

class Workspace(BaseModel):
    id: str
    version: str
    problem_space: ProblemSpace
    solution_space: Optional[SolutionSpace] = None

# --- Persistence Manager ---

class WorkspaceManager:
    def __init__(self, root_dir: str = "workspaces"):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _get_workspace_dir(self, workspace_id: str) -> Path:
        path = self.root_dir / workspace_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_version_path(self, workspace_id: str, version_id: str) -> Path:
        return self._get_workspace_dir(workspace_id) / f"{version_id}.json"

    def list_workspaces(self) -> List[str]:
        return [d.name for d in self.root_dir.iterdir() if d.is_dir()]

    def list_versions(self, workspace_id: str) -> List[str]:
        ws_dir = self._get_workspace_dir(workspace_id)
        # return sorted version IDs by modification time
        files = list(ws_dir.glob("*.json"))
        files.sort(key=lambda f: f.stat().st_mtime)
        return [f.stem for f in files]

    def save_workspace(self, workspace: Workspace) -> str:
        """Saves workspace to markdown file. Returns file path."""
        path = self._get_version_path(workspace.id, workspace.version)
        content = self._to_json(workspace)
        with open(path, "w") as f:
            f.write(content)
        return str(path)

    def load_workspace(self, workspace_id: str, version_id: str) -> Workspace:
        path = self._get_version_path(workspace_id, version_id)
        if not path.exists():
            raise FileNotFoundError(f"Workspace version not found: {path}")
        
        with open(path, "r") as f:
            content = f.read()
            
        return self._from_json(workspace_id, version_id, content)

    # --- JSON Serialization ---

    def _to_json(self, ws: Workspace) -> str:
        return ws.model_dump_json(indent=2)

    def _from_json(self, ws_id: str, ver: str, content: str) -> Workspace:
        return Workspace.model_validate_json(content)
