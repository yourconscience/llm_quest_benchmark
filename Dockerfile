FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Node.js and npm
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Check versions
RUN python --version && node --version && npm --version

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# Install ts-node globally
RUN npm install -g ts-node

# Clone repository with submodules
RUN git clone --recursive https://github.com/your-username/llm_quest_benchmark.git .

# Setup environment
RUN uv venv .venv
ENV PATH="/app/.venv/bin:${PATH}"

# Install Python dependencies
RUN uv pip install -e .

# Set NODE_OPTIONS for legacy OpenSSL support
ENV NODE_OPTIONS="--openssl-legacy-provider"

# Setup TypeScript bridge
WORKDIR /app/space-rangers-quest
RUN npm install --legacy-peer-deps && npm run build
WORKDIR /app

# Create quests directory
RUN mkdir -p /app/quests

# Download quests from GitLab
RUN apt-get update && apt-get install -y wget unzip && \
    wget https://gitlab.com/spacerangers/spacerangers.gitlab.io/-/archive/master/spacerangers.gitlab.io-master.zip && \
    unzip spacerangers.gitlab.io-master.zip && \
    cp -r spacerangers.gitlab.io-master/borrowed/qm/* /app/quests/ && \
    rm -rf spacerangers.gitlab.io-master* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create .env file placeholder
RUN echo "# Set your API keys here\n\
# OPENAI_API_KEY=your-api-key\n\
# ANTHROPIC_API_KEY=your-api-key" > .env

# Expose port
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["llm-quest"]
CMD ["web", "--host", "0.0.0.0"]