# Security Policy

The project processes resumes and job descriptions, which may contain highly sensitive personal
information. Responsible disclosure and data minimization are required.

## Supported versions

Security fixes are provided for the latest release line and the default branch.

| Version | Supported |
| --- | --- |
| `0.1.x` | Yes |
| Earlier or unreleased forks | No |

Until the project reaches `1.0`, security fixes may include breaking changes when necessary to
protect users.

## Reporting a vulnerability

Use [GitHub Private Vulnerability Reporting](https://github.com/Miguesh/AI-Resume-Job-Match-Agent/security/advisories/new)
to report a suspected vulnerability. Do not open a public issue, discussion, or pull request.

Include, when available:

- the affected version or commit;
- the vulnerable component and deployment assumptions;
- reproducible steps or a minimal proof of concept;
- realistic impact and required attacker capabilities;
- a suggested mitigation, if known.

Do not include real resumes, personal information, production API keys, access tokens, or data
obtained from anyone other than yourself. Replace sensitive values with synthetic examples.

The maintainer aims to acknowledge reports within three business days, provide an initial
assessment within seven business days, and share progress at least every fourteen days while a
confirmed issue is being remediated. Resolution timing depends on severity and complexity.

## Scope

Reports are especially valuable when they concern:

- document-upload validation or parser isolation;
- authentication, authorization, rate limiting, or data isolation;
- unintended disclosure through logs, exports, storage, or API responses;
- prompt injection that crosses a trust boundary or exposes protected data;
- unsafe file paths, archive handling, database access, or dependency vulnerabilities;
- bypasses of factual-consistency controls that create materially deceptive output.

Reports about intentionally insecure development defaults are considered only when those defaults
can reasonably reach a production deployment despite the documented production safeguards.
Automated scanner output without a demonstrated impact may receive lower priority.

## Safe-harbor expectations

Good-faith research should:

- use accounts, documents, and infrastructure you own or are authorized to test;
- avoid privacy violations, service disruption, destructive actions, and persistence;
- access only the minimum data needed to demonstrate the issue;
- stop testing and report immediately if you encounter another person's data;
- allow reasonable time for remediation before coordinated public disclosure.

The project will not pursue action against research that follows these expectations and applicable
law. This statement does not authorize testing against third-party services such as OpenAI or
GitHub; their policies continue to apply.

## Disclosure and fixes

Confirmed vulnerabilities are handled through a private advisory until a fix and release plan are
ready. Credit is offered to reporters who want it, unless legal or privacy constraints prevent it.
Please coordinate publication timing with the maintainer so users have a reasonable opportunity to
upgrade.
