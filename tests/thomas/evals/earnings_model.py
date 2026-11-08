"""One authenticated, isolated model decision in the Thomas earnings tool loop."""

import json
import os
import sys

from codex_model import completion

prompt, request = json.load(sys.stdin)
model = os.environ.get("EARNINGS_EVAL_MODEL", "gpt-6.1-sol")
data = completion(
    {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
        ],
    },
    model=model,
    timeout=int(os.getenv("EARNINGS_EVAL_TIMEOUT", 110)),
    token_cap=int(os.getenv("EARNINGS_EVAL_MAX_TOKENS", 12000)),
)
answer = "".join(
    json.loads(row[6:])["choices"][0]["delta"].get("content", "")
    for row in data.decode().splitlines()
    if row.startswith("data: {")
)
print(answer)
