# Session Notes — 2026-10-22

Checked the user's VPS security email against the official PHP advisory:
https://www.php.net/archive/2026.php#2026-10-21-5 . The advisory covers
CVE-2026-109618 and CVE-2026-109619, with fixes in PHP 8.5.12, 8.4.27, 8.3.36,
and 8.2.35. Success criteria were to verify whether the gym website or its live
hosting environment serves PHP, and confirm the website remains available.

The repository uses Python/FastAPI/Uvicorn and a Python Docker image. No PHP
source, dependency, or PHP deployment references were found in the checked app,
dependency metadata, deployment configuration, CI, or public setup documentation.

Read-only SSH checks found no installed PHP packages, PHP commands, PHP services,
or standard PHP/CloudPanel configuration directories on the Ubuntu VPS. Inspected
all nine running containers through their process-root filesystems: no standard
PHP runtime paths or installed PHP packages were found in available dpkg/apk
databases. Two containers had neither package database. Docker process listing
with the requested columns failed; a direct scan of all 171 host/container
process names and executable paths succeeded and found no PHP or Apache runtime.
Nginx Proxy Manager's active configuration passed validation and contained no PHP
handlers. The live gym container reported Python 3.12.15, FastAPI 0.141.1, and
Uvicorn 0.51.0. Public HTTPS health and login requests both returned 200.

The PHP advisory does not apply to the observed running setup. No packages were
upgraded, services restarted, or application/runtime settings changed. Stopped
containers were inventoried but not started or inspected internally. This was a
targeted PHP applicability check; application tests were unnecessary because no
application code changed. Updated project memory with the dated findings.
