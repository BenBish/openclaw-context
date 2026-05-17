# Openclaw Context

Context and setup plans for Openclaw multi-agent deployment on the Strix Halo box.

- **Hardware**: Fedora Strix Halo box, 128GB RAM, AMD GPU
- **Agents**: Tom (Helen's executive assistant) and Freddy (Ben's executive assistant) are implemented. Bernie (Polymarket) and Archie (coding) are planned migrations.
- **Models**: Local Llama.cpp only — currently GPT-OSS 120B UD-Q4_K_XL via llama-swap; previous configs include Qwen3-Coder, Qwen3.6, and Gemma 4.

See [setup plan](docs/research/2026-05-08-STRIX-HALO-SETUP.md).

Model runbooks:

- [GPT-OSS 120B on Strix Halo](docs/research/2026-05-17-gpt-oss-120b-strix-halo.md)
- [Local llama-server model configurations](docs/research/2026-05-17-local-llama-model-configs.md)

Agent runbooks:

- [Tom migration notes](docs/research/2026-05-10-tom-agent-migration.md)
- [Freddy migration notes](docs/research/2026-05-10-freddy-agent-migration.md)
