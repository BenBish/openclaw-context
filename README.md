# Openclaw Context

Context and setup plans for Openclaw multi-agent deployment on the Strix Halo box.

- **Hardware**: Fedora Strix Halo box, 128GB RAM, AMD GPU
- **Agents**: Tom (Helen's executive assistant) and Freddy (Ben's executive assistant) are implemented. Bernie (Polymarket) and Archie (coding) are planned migrations.
- **Models**: Local Llama.cpp only — currently Qwen3.6 27B UD-Q4_K_XL primary and Gemma 4 26B A4B UD-Q4_K_XL fallback via llama-swap; previous configs include GPT-OSS 120B and Qwen3-Coder.

See [setup plan](docs/research/2026-05-08-STRIX-HALO-SETUP.md).

Model runbooks:

- [GPT-OSS 120B on Strix Halo](docs/research/2026-05-17-gpt-oss-120b-strix-halo.md)
- [Local llama-server model configurations](docs/research/2026-05-17-local-llama-model-configs.md)
- [Remote OpenClaw Control UI access](docs/research/2026-05-18-openclaw-remote-control-ui.md)

Agent runbooks:

- [Tom migration notes](docs/research/2026-05-10-tom-agent-migration.md)
- [Freddy migration notes](docs/research/2026-05-10-freddy-agent-migration.md)

Cron validation:

```bash
scripts/cron-validate.py          # quick, non-invasive checks
scripts/cron-validate.py --deps   # also probes local scripts, auth, and external URLs
scripts/cron-validate.py --run <job-id-or-name>
```

`--run` triggers the selected production cron job and may deliver Telegram messages. Use it only when you intentionally want an end-to-end smoke test.
