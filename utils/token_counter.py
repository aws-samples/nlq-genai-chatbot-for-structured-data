class TokenCounter:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0

    def update_tokens(self, usage):
        self.prompt_tokens = usage.get('prompt_tokens', 0)
        self.completion_tokens = usage.get('completion_tokens', 0)
        self.total_tokens = usage.get('total_tokens', 0)

    def get_token_usage_content(self):
        return f"""
    Total Input Tokens:     {self.prompt_tokens}
    Total Output Tokens:    {self.completion_tokens}
    Total Tokens Combined:  {self.total_tokens}
"""
