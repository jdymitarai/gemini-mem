"""
Google Gemini Synthesis Provider for gemini-mem.
Uses Google AI Studio / Gemini API (or local heuristics if offline) to synthesize memories.
Zero heavy dependencies: uses native standard library HTTP with JSON schema prompting.
"""

from __future__ import annotations
import json
import os
import re
import urllib.request
import urllib.error
from typing import Any

from gemini_mem.core.schema import Observation, SessionSummary, Entity, Relation
from gemini_mem.config import config


class GeminiObserver:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or config.api_key
        self.model = model or config.model
        self.api_base = "https://generativelanguage.googleapis.com/v1beta/models"

    def _call_gemini(self, prompt: str, system_instruction: str = "") -> str | None:
        """Call Gemini API via standard library HTTPS."""
        if not self.api_key:
            return None

        url = f"{self.api_base}/{self.model}:generateContent?key={self.api_key}"
        payload: dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json"
            }
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=20.0) as resp:
                body = resp.read().decode("utf-8")
                result = json.loads(body)
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except Exception:
            # Resilient fallback: never crash
            return None
        return None

    def synthesize_observation(
        self,
        tool_name: str,
        tool_input: str,
        tool_output: str,
        session_id: str = "",
        project: str = ""
    ) -> Observation:
        """Extract a structured observation from a tool invocation."""
        prompt = f"""
Analyze the following tool call and output, and synthesize a structured memory observation:
Tool Name: {tool_name}
Tool Input: {tool_input[:2000]}
Tool Output: {tool_output[:4000]}

Respond strictly with a JSON object with this schema:
{{
  "type": "bugfix|feature|decision|lesson|architecture|security",
  "title": "Concise 5-10 word technical title",
  "narrative": "1-3 sentences explaining what was done, root cause or outcome",
  "facts": ["Key technical fact 1", "Key technical fact 2"],
  "files_read": ["filepath1"],
  "files_modified": ["filepath2"]
}}
"""
        response_text = self._call_gemini(
            prompt,
            system_instruction="You are an expert AI agent memory synthesiser. Extract precise technical facts."
        )

        if response_text:
            try:
                data = json.loads(response_text)
                return Observation(
                    session_id=session_id,
                    project=project,
                    type=data.get("type", "general"),
                    title=data.get("title", f"{tool_name} execution"),
                    narrative=data.get("narrative", ""),
                    facts=data.get("facts", []),
                    files_read=data.get("files_read", []),
                    files_modified=data.get("files_modified", []),
                    discovery_tokens=len(tool_output) // 4
                )
            except Exception:
                pass

        # Heuristic fallback if offline or no API key
        return self._heuristic_observation(tool_name, tool_input, tool_output, session_id, project)

    def synthesize_session_summary(
        self,
        transcript_text: str,
        session_id: str = "",
        project: str = ""
    ) -> SessionSummary:
        """Synthesize a complete session into lessons, completed items, and next steps."""
        prompt = f"""
Analyze the following session dialogue and extract a high-level summary:
Session Transcript:
{transcript_text[:12000]}

Respond strictly with a JSON object:
{{
  "request": "What the user requested",
  "investigated": "What was researched, root causes analyzed",
  "learned": "Key lessons or architectural insights gained",
  "completed": "What was implemented or resolved",
  "next_steps": "Future improvements or remaining tasks"
}}
"""
        response_text = self._call_gemini(
            prompt,
            system_instruction="You are an AI engineering memory observer. Summarize software sessions accurately."
        )

        if response_text:
            try:
                data = json.loads(response_text)
                return SessionSummary(
                    session_id=session_id,
                    project=project,
                    request=data.get("request", ""),
                    investigated=data.get("investigated", ""),
                    learned=data.get("learned", ""),
                    completed=data.get("completed", ""),
                    next_steps=data.get("next_steps", "")
                )
            except Exception:
                pass

        # Heuristic fallback
        return SessionSummary(
            session_id=session_id,
            project=project,
            request="User session",
            investigated="Session actions completed",
            learned="Session context captured",
            completed="All tasks processed cleanly",
            next_steps=""
        )

    def _heuristic_observation(
        self,
        tool_name: str,
        tool_input: str,
        tool_output: str,
        session_id: str,
        project: str
    ) -> Observation:
        obs_type = "general"
        title = f"Invoked {tool_name}"

        # Detect files
        files_read = re.findall(r'[\w\-./\\]+\.[a-zA-Z0-9]+', tool_input)[:5]
        files_mod = []

        if "edit" in tool_name.lower() or "write" in tool_name.lower() or "patch" in tool_name.lower():
            obs_type = "feature"
            files_mod = files_read
            title = f"Modified files via {tool_name}"
        elif "test" in tool_input.lower() or "error" in tool_output.lower():
            obs_type = "bugfix"
            title = f"Ran diagnostics via {tool_name}"

        facts = [f"Tool {tool_name} executed with status length {len(tool_output)} chars"]
        if "error" in tool_output.lower():
            facts.append("Encountered diagnostic error in output")

        return Observation(
            session_id=session_id,
            project=project,
            type=obs_type,
            title=title,
            narrative=f"Executed {tool_name} with target input preview: {tool_input[:80]}",
            facts=facts,
            files_read=files_read,
            files_modified=files_mod,
            discovery_tokens=len(tool_output) // 4
        )
