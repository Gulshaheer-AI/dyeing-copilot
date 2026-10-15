"""One request per matching UI evidence/question/mode signature, per session."""


def generate_once(state, signature, generate):
    stored = state.get("copilot_answer")
    if stored and stored[0] == signature:
        return stored[1], False
    if state.get("copilot_inflight"):
        raise ValueError("An explanation request is already running. Wait for its outcome.")
    state.pop("copilot_answer", None)
    state["copilot_inflight"] = signature
    try:
        answer = generate()
        state["copilot_answer"] = (signature, answer)
        return answer, True
    finally:
        state.pop("copilot_inflight", None)
