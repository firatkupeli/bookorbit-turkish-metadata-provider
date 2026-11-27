# Security

Do not post secrets, real .env files, private network details or full access logs
in public issues. If a token has already been exposed, rotate it before reporting.

Before opening this repository to the public, the maintainer should enable
GitHub's Private Vulnerability Reporting in the repository Security settings.
If enabled, report vulnerabilities through Security → Report a vulnerability.
No private reporting address is advertised until that channel exists.
Public issues should contain only non-sensitive reproduction information.

This beta does not promise a supported-version window or response SLA.
Use the latest reviewed release and dependency updates.
The included workflow pins action commits; Dependabot checks them monthly.

The service makes outbound requests to the configured source implementation,
not to arbitrary user-supplied URLs. Keep source pacing and response limits.
For local BookOrbit deployments, use a shared Docker network. Authentication
is optional; set AUTH_TOKEN when clients outside a trusted network can reach it.
There is no need to publish a host port or put this service on the public internet
for the documented shared-network setup.

The release tool checks a limited set of credential and private-address patterns.
This is a packaging aid, not a comprehensive security audit.
