#!/usr/bin/env python3
"""Sentinel Mesh demo fleet — two ADK worker agents exposed over real A2A."""
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.genai import types

# Vertex throttles bursty default quotas with bare 429s; ADK has no built-in retry,
# so every fleet model carries explicit backoff.
MODEL = Gemini(
    model="gemini-flash-latest",
    retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2.0, max_delay=30.0),
)

researcher = LlmAgent(
    name="researcher",
    model=MODEL,
    description="Researches corporate/financial facts and reports findings as single-sentence claims.",
    instruction=(
        "You are a research worker in an agent fleet. Answer the question you are "
        "given in ONE declarative sentence (a 'claim'). Do not hedge, do not add "
        "caveats — emit the claim; the control plane downstream will verify it.\n"
        "Your research notes: Meridian Dynamics Ltd (SG) closes its financial year "
        "on 31 December; Atlas Cognition Labs was founded in 2024 by Jun Seo."
    ),
)

planner = LlmAgent(
    name="planner",
    model=MODEL,
    description="Plans operational next steps and proposes actions as single-sentence claims.",
    instruction=(
        "You are a planning worker in an agent fleet. Given a goal, propose the "
        "single next action in ONE imperative sentence. Do not hedge — the control "
        "plane downstream gates anything dangerous."
    ),
)
