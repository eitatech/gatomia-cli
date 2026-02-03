<h1 align="center">GatomIA CLI: Evaluating AI's Ability to Generate Holistic Documentation for Large-Scale Codebases</h1>

<p align="center">
  <strong>AI-Powered Repository Documentation Generation</strong> • <strong>Multi-Language Support</strong> • <strong>Architecture-Aware Analysis</strong>
</p>

<p align="center">
  Generate holistic, structured documentation for large-scale codebases • Cross-module interactions • Visual artifacts and diagrams
</p>

<p align="center">
  <a href="https://python.org/"><img alt="Python version" src="https://img.shields.io/badge/python-3.12+-blue?style=flat-square" /></a>
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" /></a>
  <a href="https://github.com/eitatech/ç/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/eitatech/gatomia-cli?style=flat-square" /></a>

</p>

<p align="center">
  <a href="#quick-start"><strong>Quick Start</strong></a> •
  <a href="#cli-commands"><strong>CLI Commands</strong></a> •
  <a href="#documentation-output"><strong>Output Structure</strong></a>
</p>

---

## Quick Start

### 1. Install GatomIA CLI

```bash
# Install from source
pip install git+https://github.com/eitatech/gatomia-cli.git

# Using UV
uv tool install gatomia --from git+https://github.com/eitatech/gatomia-cli.git

# Verify installation
mia --version
```

### 2. Configure Your Environment

GatomIA supports multiple models via an OpenAI-compatible SDK layer.

```bash
mia config set \
  --api-key YOUR_API_KEY \
  --base-url https://api.anthropic.com \
  --main-model claude-sonnet-4.5 \
  --cluster-model claude-sonnet-4.5 \
  --fallback-model claude-haiku-4.5 
```

### 3. Generate Documentation

```bash
# Navigate to your project
cd /path/to/your/project

# Generate documentation
mia generate

# Generate with HTML viewer for GitHub Pages
mia generate --github-pages --create-branch
```

**That's it!** Your documentation will be generated in `./docs/` with comprehensive repository-level analysis.

### Usage Example

![CLI Usage Example](https://github.com/eitatech/gatomia-cli/releases/download/assets/cli-usage-example.gif)

---

## What is GatomIA CLI?

GatomIA CLI is an open-source framework for **automated repository-level documentation** across seven programming languages. It generates holistic, architecture-aware documentation that captures not only individual functions but also their cross-file, cross-module, and system-level interactions.

### Key Innovations

| Innovation | Description | Impact |
|------------|-------------|--------|
| **Hierarchical Decomposition** | Dynamic programming-inspired strategy that preserves architectural context | Handles codebases of arbitrary size (86K-1.4M LOC tested) |
| **Recursive Agentic System** | Adaptive multi-agent processing with dynamic delegation capabilities | Maintains quality while scaling to repository-level scope |
| **Multi-Modal Synthesis** | Generates textual documentation, architecture diagrams, data flows, and sequence diagrams | Comprehensive understanding from multiple perspectives |

### Supported Languages

**🐍 Python** • **☕ Java** • **🟨 JavaScript** • **🔷 TypeScript** • **⚙️ C** • **🔧 C++** • **🪟 C#**

---

## CLI Commands

### Configuration Management

```bash
# Set up your API configuration
mia config set \
  --api-key <your-api-key> \
  --base-url <provider-url> \
  --main-model <model-name> \
  --cluster-model <model-name> \
  --fallback-model <model-name>

# Configure max token settings
mia config set --max-tokens 32768 --max-token-per-module 36369 --max-token-per-leaf-module 16000

# Configure max depth for hierarchical decomposition
mia config set --max-depth 3

# Show current configuration
mia config show

# Validate your configuration
mia config validate
```

### Documentation Generation

```bash
# Basic generation
mia generate

# Custom output directory
mia generate --output ./documentation

# Create git branch for documentation
mia generate --create-branch

# Generate HTML viewer for GitHub Pages
mia generate --github-pages

# Enable verbose logging
mia generate --verbose

# Full-featured generation
mia generate --create-branch --github-pages --verbose
```

### Customization Options

GatomIA supports customization for language-specific projects and documentation styles:

```bash
# C# project: only analyze .cs files, exclude test directories
mia generate --include "*.cs" --exclude "Tests,Specs,*.test.cs"

# Focus on specific modules with architecture-style docs
mia generate --focus "src/core,src/api" --doc-type architecture

# Add custom instructions for the AI agent
mia generate --instructions "Focus on public APIs and include usage examples"
```

#### Pattern Behavior (Important!)

- **`--include`**: When specified, **ONLY** these patterns are used (replaces defaults completely)
  - Example: `--include "*.cs"` will analyze ONLY `.cs` files
  - If omitted, all supported file types are analyzed
  - Supports glob patterns: `*.py`, `src/**/*.ts`, `*.{js,jsx}`
  
- **`--exclude`**: When specified, patterns are **MERGED** with default ignore patterns
  - Example: `--exclude "Tests,Specs"` will exclude these directories AND still exclude `.git`, `__pycache__`, `node_modules`, etc.
  - Default patterns include: `.git`, `node_modules`, `__pycache__`, `*.pyc`, `bin/`, `dist/`, and many more
  - Supports multiple formats:
    - Exact names: `Tests`, `.env`, `config.local`
    - Glob patterns: `*.test.js`, `*_test.py`, `*.min.*`
    - Directory patterns: `build/`, `dist/`, `coverage/`

#### Setting Persistent Defaults

Save your preferred settings as defaults:

```bash
# Set include patterns for C# projects
mia config agent --include "*.cs"

# Exclude test projects by default (merged with default excludes)
mia config agent --exclude "Tests,Specs,*.test.cs"

# Set focus modules
mia config agent --focus "src/core,src/api"

# Set default documentation type
mia config agent --doc-type architecture

# View current agent settings
mia config agent

# Clear all agent settings
mia config agent --clear
```

| Option | Description | Behavior | Example |
|--------|-------------|----------|---------|
| `--include` | File patterns to include | **Replaces** defaults | `*.cs`, `*.py`, `src/**/*.ts` |
| `--exclude` | Patterns to exclude | **Merges** with defaults | `Tests,Specs`, `*.test.js`, `build/` |
| `--focus` | Modules to document in detail | Standalone option | `src/core,src/api` |
| `--doc-type` | Documentation style | Standalone option | `api`, `architecture`, `user-guide`, `developer` |
| `--instructions` | Custom agent instructions | Standalone option | Free-form text |

### Token Settings

GatomIA allows you to configure maximum token limits for LLM calls. This is useful for:
- Adapting to different model context windows
- Controlling costs by limiting response sizes
- Optimizing for faster response times

```bash
# Set max tokens for LLM responses (default: 32768)
mia config set --max-tokens 16384

# Set max tokens for module clustering (default: 36369)
mia config set --max-token-per-module 40000

# Set max tokens for leaf modules (default: 16000)
mia config set --max-token-per-leaf-module 20000

# Set max depth for hierarchical decomposition (default: 2)
mia config set --max-depth 3

# Override at runtime for a single generation
mia generate --max-tokens 16384 --max-token-per-module 40000 --max-depth 3
```

| Option | Description | Default |
|--------|-------------|---------|
| `--max-tokens` | Maximum output tokens for LLM response | 32768 |
| `--max-token-per-module` | Input tokens threshold for module clustering | 36369 |
| `--max-token-per-leaf-module` | Input tokens threshold for leaf modules | 16000 |
| `--max-depth` | Maximum depth for hierarchical decomposition | 2 |

### Configuration Storage

- **API keys**: Securely stored in system keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service)
- **Settings & Agent Instructions**: `~/.gatomia/config.json`

---

## Documentation Output

Generated documentation includes both **textual descriptions** and **visual artifacts** for comprehensive understanding.

### Textual Documentation
- Repository overview with architecture guide
- Module-level documentation with API references
- Usage examples and implementation patterns
- Cross-module interaction analysis

### Visual Artifacts
- System architecture diagrams (Mermaid)
- Data flow visualizations
- Dependency graphs and module relationships
- Sequence diagrams for complex interactions

### Output Structure

```
./docs/
├── overview.md              # Repository overview (start here!)
├── module1.md               # Module documentation
├── module2.md               # Additional modules...
├── module_tree.json         # Hierarchical module structure
├── first_module_tree.json   # Initial clustering result
├── metadata.json            # Generation metadata
└── index.html               # Interactive viewer (with --github-pages)
```

---

## How It Works

### Architecture Overview

GatomIA employs a three-stage process for comprehensive documentation generation:

1. **Hierarchical Decomposition**: Uses dynamic programming-inspired algorithms to partition repositories into coherent modules while preserving architectural context across multiple granularity levels.

2. **Recursive Multi-Agent Processing**: Implements adaptive multi-agent processing with dynamic task delegation, allowing the system to handle complex modules at scale while maintaining quality.

3. **Multi-Modal Synthesis**: Integrates textual descriptions with visual artifacts including architecture diagrams, data-flow representations, and sequence diagrams for comprehensive understanding.

### Data Flow

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Codebase      │───▶│  Hierarchical    │───▶│  Multi-Agent    │
│   Analysis      │    │  Decomposition   │    │  Processing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Visual        │◀───│  Multi-Modal     │◀───│  Structured     │
│   Artifacts     │    │  Synthesis       │    │  Content        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

---

## Requirements

- **Python 3.12+**
- **Node.js** (for Mermaid diagram validation)
- **LLM API access** (Anthropic Claude, OpenAI, etc.)
- **Git** (for branch creation features)

---

## Additional Resources

### Documentation & Guides
- **[Docker Deployment](docker/DOCKER_README.md)** - Containerized deployment instructions
- **[Development Guide](DEVELOPMENT.md)** - Project structure, architecture, and contributing guidelines

---

## Star History

<p align="center">
  <a href="https://star-history.com/#eitatech/gatomia-cli&Date">
   <picture>
     <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=eitatech/gatomia-cli&type=Date&theme=dark" />
     <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=eitatech/gatomia-cli&type=Date" />
     <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=eitatech/gatomia-cli&type=Date" />
   </picture>
  </a>
</p>

---

## License

This project is licensed under the MIT License.
