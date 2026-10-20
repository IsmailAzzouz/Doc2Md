# Security policy

## Supported versions

Security fixes are currently targeted at the latest release only (`0.x`).
Older releases are not guaranteed to receive backports.

## Reporting a vulnerability

Please **do not** post exploitable details in a public issue. Use the
[GitHub private vulnerability reporting interface](https://github.com/IsmailAzzouz/Doc2Md/security/advisories/new)
if enabled for this repository. If it is unavailable, open a public issue
**without exploit details**, asking the maintainers for a private reporting
channel. Maintainers will coordinate disclosure and remediation.

DOCX files are ZIP/XML documents, and legacy formats can invoke LibreOffice or
Microsoft Word. Until input limits and security reviews are completed, process
untrusted files only in isolated environments with CPU, memory, file size and
time limits. Do not run with elevated privileges.
