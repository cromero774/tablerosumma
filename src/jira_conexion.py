
# -*- coding: utf-8 -*-
"""
Jira Cloud connector - FINAL (fixed payload for /search/jql)
- Uses POST /rest/api/3/search/jql with the correct schema (no 'startAt').
- Paginates with 'nextPageToken'. For backward-compat, if caller passes start_at>0,
  we internally advance pages until we reach that offset.
- Detects search even if endpoint is 'search?jql=...' or params carry 'jql'.
- Auto-prefixes 'rest/api/3/' for non-prefixed endpoints.
- Manual .env loading (no deps).
"""
from __future__ import annotations

import os, json, math
from typing import Any, Dict, Optional, List, Tuple
from urllib.parse import urljoin, urlparse, parse_qs
from pathlib import Path as _Path
import requests

# --------- .env loader (no external deps) ---------
def _load_dotenv_manual() -> None:
    here = _Path(__file__).resolve()
    candidates = [
        _Path.cwd() / ".env",
        here.parent / ".env",
        here.parent.parent / ".env",
    ]
    p = _Path.cwd()
    for _ in range(3):
        p = p.parent
        candidates.append(p / ".env")
    seen = set(); ordered = []
    for c in candidates:
        try:
            s = str(c.resolve())
        except Exception:
            s = str(c)
        if s not in seen:
            seen.add(s); ordered.append(_Path(s))
    for env_path in ordered:
        try:
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip(); v = v.strip().strip("'").strip('"')
                    if k and (k not in os.environ or not os.environ[k]):
                        os.environ[k] = v
                break
        except Exception:
            pass

def _normalize_base(u: str) -> str:
    u = u.strip().rstrip("/")
    parts = u.split("/rest/api/")
    return parts[0] if len(parts) > 1 else u

def _load_creds() -> Dict[str, str]:
    _load_dotenv_manual()
    base = os.getenv("JIRA_BASE_URL") or os.getenv("JIRA_URL")
    email = os.getenv("JIRA_EMAIL") or os.getenv("ATLASSIAN_EMAIL")
    token = os.getenv("JIRA_API_TOKEN") or os.getenv("ATLASSIAN_API_TOKEN")
    if not (base and email and token):
        raise RuntimeError("Missing Jira creds (JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN).")
    return {"base_url": _normalize_base(base), "email": email, "token": token}

class JiraAPI:
    def __init__(self) -> None:
        creds = _load_creds()
        self.base = creds["base_url"]
        self.session = requests.Session()
        self.session.auth = (creds["email"], creds["token"])
        if os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY"):
            self.session.trust_env = True
        self.timeout_read = float(os.getenv("JIRA_TIMEOUT", "120"))
        print(f"[jira_conexion] Loaded from: {_Path(__file__).resolve()}")
        print(f"[jira_conexion] Base URL: {self.base}")

    # ---- HTTP helpers ----
    def _ok_json(self, label: str, path: str, resp: requests.Response) -> Any:
        if 200 <= resp.status_code < 300:
            if not resp.content:
                return {}
            try:
                return resp.json()
            except Exception:
                return json.loads(resp.text)
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text[:800]
        raise RuntimeError(f"Error Jira ({label} {path}) -> status={resp.status_code} detail={detail}")

    def _prefix(self, path: str) -> str:
        p = path.lstrip("/")
        return p if p.startswith("rest/api/") else f"rest/api/3/{p}"

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, label: Optional[str] = None) -> Any:
        label = label or "GET"
        url = urljoin(self.base + "/", self._prefix(path))
        r = self.session.get(url, params=params or {}, timeout=self.timeout_read)
        return self._ok_json(label, path, r)

    def _post(self, path: str, payload: Dict[str, Any], label: Optional[str] = None) -> Any:
        label = label or "POST"
        url = urljoin(self.base + "/", self._prefix(path))
        r = self.session.post(url, json=payload, timeout=self.timeout_read)
        return self._ok_json(label, path, r)

    def ensure_ready(self) -> None:
        self._get("myself", None, "GET /myself")

    # ---- JQL search using /search/jql (no 'startAt' in payload) ----
    def _post_search_jql(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post("search/jql", payload, "POST /search/jql")

    def search_jql(self, *, jql: str, fields: Optional[List[str]] = None,
                   start_at: int = 0, max_results: int = 50, next_page_token: Optional[str] = None) -> Dict[str, Any]:
        # Build payload respecting the new schema
        payload: Dict[str, Any] = {"jql": jql, "maxResults": max_results}
        if fields is not None:
            payload["fields"] = fields
        if next_page_token:
            payload["nextPageToken"] = next_page_token

        # Back-compat: if start_at > 0 but we don't have token, advance pages
        if start_at and start_at > 0 and not next_page_token:
            page_size = max_results if max_results else 50
            pages_to_skip = start_at // page_size
            token = None
            result = None
            for _ in range(pages_to_skip + 1):
                result = self._post_search_jql({"jql": jql, "maxResults": page_size, **({"fields": fields} if fields else {}), **({"nextPageToken": token} if token else {})})
                token = result.get("nextPageToken")
                if token is None:
                    break
            return result if result is not None else {}
        else:
            return self._post_search_jql(payload)

    # ---- Compatibility entry ----
    def _get_json(self, endpoint: str, params: Optional[Dict[str, Any]] = None, label: Optional[str] = None) -> Any:
        params = params or {}
        parsed = urlparse(endpoint)
        path = parsed.path.lstrip('/')
        qs = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
        for k, v in qs.items():
            params.setdefault(k, v)

        jql = params.get("jql") or params.get("JQL")
        start_at = int(params.get("start_at", params.get("startAt", 0)) or 0)
        max_results = int(params.get("max_results", params.get("maxResults", 50)) or 50)
        fields = params.get("fields")
        if isinstance(fields, str):
            fields = [f.strip() for f in fields.split(",") if f.strip()]

        if "search" in path and jql:
            return self.search_jql(jql=jql, fields=fields, start_at=start_at, max_results=max_results)

        return self._get(path, params, label or "GET")

jira = JiraAPI()

def get_jira() -> JiraAPI:
    return jira

def ensure_ready() -> None:
    jira.ensure_ready()














































































