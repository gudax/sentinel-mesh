#!/usr/bin/env python3
"""Serve one demo worker over the A2A protocol: `serve_worker.py researcher 8001`."""
import sys

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a

import workers

if __name__ == "__main__":
    name, port = sys.argv[1], int(sys.argv[2])
    agent = getattr(workers, name)
    app = to_a2a(agent, port=port)  # serves /.well-known/agent-card.json
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
