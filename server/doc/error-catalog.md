# Known Server errors and Chinese hints

The Server error classifier is intentionally conservative. It never replaces
the raw exception or traceback, only adds an explanation for known signatures.
Plugin-side fallback rules mirror the same codes.

- PDF_UNREADABLE_TEXT: no extractable PDF text / unreadable CID data.
- BITSTRING_INCOMPATIBLE: the actual BitStream import failure from issue #366.
  Use the read-only manage_packages.py doctor command; the expected bitstring
  range is >=4.3.0,<5.
- API_RATE_LIMIT: HTTP 429 or rate_limit_exceeded. Check quota and concurrency.
- API_AUTH_FAILED: explicit invalid_api_key / 401 Unauthorized.

Unknown errors remain unknown. Add new rules only with reproducible log
signatures, paired Python / TypeScript tests, and preservation of the raw error.
