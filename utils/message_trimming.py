from langchain_core.messages import trim_messages, SystemMessage


def modify_state_messages(state, model, system_message):
    all_messages = state.get("memory", []) + state.get("messages", [])
    enable_trimming = state.get("enable_trimming", True)

    if enable_trimming:
        original_length = len(all_messages)
        trimmed_messages = trim_messages(
            [system_message] + all_messages,
            max_tokens=195000,
            strategy="last",
            token_counter=model,
            include_system=True
        )
        state["trimmed"] = len(trimmed_messages) < original_length + 1
    else:
        trimmed_messages = [system_message] + all_messages
        state["trimmed"] = False

    state["memory"] = trimmed_messages
    return trimmed_messages
