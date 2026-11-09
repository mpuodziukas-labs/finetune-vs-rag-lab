# Security policy

This repository is a public research and portfolio lab: a controlled fine-tune versus retrieval comparison on a laptop CPU with sha256-pinned downloads. It is maintained by one person. Reports are welcome and are handled on a best-effort basis described below.

## Reporting a vulnerability (coordinated disclosure)

1. Do not open a public issue for a security problem.
2. Use the private "Report a vulnerability" button on the Security tab of this repository (private vulnerability reporting, enabled by the owner at publish). No email address is published; the button is the only channel.
3. Include: the affected file or command, the steps to reproduce, the version or commit sha, and the impact you believe it has.
4. Expected handling: acknowledgement within 7 days, a first assessment within 14 days, and a fix or a written decision within 30 days. These are targets from one maintainer, not a service level.
5. Please allow 90 days from the first report before public disclosure. If a fix ships sooner, disclosure can follow the fix. Reporters are credited in CHANGELOG.md unless they ask not to be.

## Supported versions

| Version | Supported |
|---|---|
| `main` at the latest commit | yes |
| tagged releases (`v*`) | yes, fixes land on `main` and in the next tag |
| anything older | no |

## Scope

In scope:
- Code in this repository (`src/ftlab/`) and the scripts under `scripts/`.
- The CI workflows under `.github/workflows/`, including any way to make them run untrusted input with write access.
- Secret handling: any path where a key, token or credential could be written to a log, receipt, cassette, fixture or commit.
- Supply chain files: requirements and lock files, `SBOM.cdx.json`, dependabot and scorecard configuration.

## Out of scope

- Findings that need a modified fork, a leaked key you supply yourself, a local attacker with shell access to the reporter's own machine, or physical access.
- Vulnerabilities in third-party dependencies that are already tracked upstream (report them upstream; a pinned-version bump request here is welcome as a normal issue).
- Social engineering of the maintainer, denial of service by volume against a free GitHub service, and automated scanner output with no demonstrated impact.
- Anything in the fixtures that is intentionally unsafe on purpose (a planted key or a planted defect used to prove a gate goes RED). Each such fixture is marked `PLANTED` in its name or header.
- Live calls to a paid provider; this repository makes none in its tests.

## Safe harbor

Good-faith research that stays inside this scope, avoids harm to other people's data, and follows the disclosure steps above will not be met with legal action from the maintainer.

## What this policy does not promise

There is no bug bounty, no paid support, and no guarantee of response time. See `THREAT-MODEL.md` for what the lab does and does not defend against.
