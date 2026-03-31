# Security Framework

Security layers for V1.5:
- JWT validation for P2P tasks
- File extension allowlist for deliveries
- Optional provenance signatures (JWT/HMAC)

See:
- `client_sdk/security/file_whitelist.py`
- `client_sdk/security/provenance.py`
- `client_sdk/webhook/server.py`
