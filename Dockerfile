FROM node:20-slim

# Install basic development utilities
RUN apt-get update && apt-get install -y \
    git \
    curl \
    ca-certificates \
    python3 \
    python3-pip \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Install Claude Code and Gemini CLI globally inside the container
RUN npm install -g @anthropic-ai/claude-code @google/gemini-cli

# Install Antigravity CLI (agy)
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash -s -- -d /usr/local/bin

ENV PATH="/root/.local/bin:/usr/local/bin:$PATH"

CMD ["bash"]

