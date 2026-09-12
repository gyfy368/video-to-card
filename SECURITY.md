# Security Policy

## Reporting

If you discover a security issue in this repository (e.g. accidental secret exposure in docs or scripts), open a private report to the maintainer or file a GitHub Security Advisory if available. Do not post live cookies or session tokens in public issues.

## Cookies & credentials

- Cookie file path: `scripts/jar.txt` (gitignored). Copy from `scripts/jar.txt.example`.
- Prefer **anonymous** mode (buvid-only) when it works; use a **secondary** account if login cookies are required.
- Never commit:
  - `scripts/jar.txt`
  - `SESSDATA` / `bili_jct` / CSRF tokens
  - `.env`, `config.yaml` with personal vault paths you do not want public
- On Unix-like systems, restrict cookie file permissions: `chmod 600 scripts/jar.txt`.

## Accidental commit of secrets

If cookies or tokens were committed:

1. Rotate the session immediately (log out everywhere / change password / clear sessions on the platform).
2. Remove from the index (keep local file if needed):

   ```bash
   git rm --cached scripts/jar.txt
   # or: git rm --cached path/to/secret
   ```

3. Ensure `.gitignore` lists the path, then commit the removal.
4. If the secret was pushed, treat history as compromised: rotate credentials; optionally rewrite history (`git filter-repo` / BFG) and force-push only if you understand the impact on collaborators.

## Generated content

- Drafts (`*_文献卡草案.md`), transcripts, and comment dumps may contain copyrighted text — keep them out of public repos (patterns are gitignored).
- Do not paste production cookies into CI logs or chat transcripts.
