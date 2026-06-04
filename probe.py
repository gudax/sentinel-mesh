"""STEP 0 env truth gate: every load-bearing import + a live Gemini PONG."""
import pathlib
import sys

ok = True

def check(label, fn):
    global ok
    try:
        fn()
        print(f"OK   {label}")
    except Exception as e:  # noqa: BLE001
        ok = False
        print(f"FAIL {label}: {type(e).__name__}: {e}")

check("LlmAgent", lambda: __import__("google.adk.agents", fromlist=["LlmAgent"]).LlmAgent)

def _probe_before_tool_callback():
    from google.adk.agents import LlmAgent
    assert "before_tool_callback" in LlmAgent.model_fields, "no before_tool_callback field"

check("LlmAgent.before_tool_callback", _probe_before_tool_callback)
check("to_a2a", lambda: __import__("google.adk.a2a.utils.agent_to_a2a", fromlist=["to_a2a"]).to_a2a)
check("RemoteA2aAgent", lambda: __import__("google.adk.agents.remote_a2a_agent", fromlist=["RemoteA2aAgent"]).RemoteA2aAgent)

def _probe_execute_interceptor():
    try:
        from google.adk.a2a.executor.config import ExecuteInterceptor  # noqa: F401
    except ImportError:
        # location moved across ADK versions; stretch-goal only — find it anywhere
        from google.adk.a2a.executor import a2a_agent_executor  # noqa: F401
        print("     (ExecuteInterceptor not at executor.config — stretch path, non-blocking)")

check("ExecuteInterceptor (stretch)", _probe_execute_interceptor)
check("google.genai", lambda: __import__("google.genai"))

def _pong():
    from google import genai
    key = pathlib.Path.home().joinpath(".config/gemini_api_key").read_text().strip()
    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model="gemini-flash-latest",
        contents="Reply with exactly: PONG",
    )
    text = (resp.text or "").strip()
    assert "PONG" in text.upper(), f"unexpected reply: {text!r}"
    print(f"     gemini-flash-latest replied: {text!r}")

check("Gemini PONG", _pong)

print("\nGATE:", "GREEN" if ok else "RED")
sys.exit(0 if ok else 1)
