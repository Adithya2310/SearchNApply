FROM node:20-slim

# Install basic development utilities
RUN apt-get update && apt-get install -y \
    git \
    curl \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install Claude Code globally inside the container
RUN npm install -g @anthropic-ai/claude-code

CMD ["bash"]
