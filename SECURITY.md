# Security

This is a research benchmark: a scenario corpus, a Python harness that calls
model APIs with keys you supply, and a Node bridge. It runs locally, holds no
user data, and has no deployed surface.

If you find a vulnerability (for example, a way for scenario or result files
to execute code, or a credential leak in the harness), please report it
privately through GitHub's private vulnerability reporting:

https://github.com/AndyFooBlah/agent-time-bench/security/advisories/new

Please do not open a public issue for security reports. You should get an
acknowledgement within a week.

API keys are read from the environment or a local `.env` (gitignored) and are
never logged or written into `results/`.
