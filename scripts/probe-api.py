"""One bounded compatibility probe. No automatic retries or response-body logging."""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--direct', action='store_true', help='Use direct HTTPS without changing system proxy settings')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "configs/model.json").read_text(encoding="utf-8"))
    env_path = root / ".env"
    local = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                local[name.strip()] = value.strip()
    key = local.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key or not re.fullmatch(r'sk-[A-Za-z0-9_-]{16,}', key):
        sys.exit("No usable key. Run scripts/configure-api.ps1 locally first.")
    report_path = root / "artifacts/api-probe.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists():
        sys.exit("Probe already attempted. Review artifacts/api-probe.json before any further call.")
    report = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "model": config["model"],
        "status": "started",
        "requests": 1,
        "max_output_tokens": config["probe_max_output_tokens"],
    }
    # Reserve this one request before network I/O: ambiguous failures must not auto-retry.
    with report_path.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": "Reply with exactly OK."}],
        "max_tokens": config["probe_max_output_tokens"],
        "stream": False,
    }
    request = urllib.request.Request(
        config["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    # Never forward the Authorization header across a provider redirect.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        handlers = [NoRedirect]
        if args.direct:
            handlers.append(urllib.request.ProxyHandler({}))
        with urllib.request.build_opener(*handlers).open(request, timeout=60) as response:
            data = json.load(response)
        choices = data.get("choices", [])
        content = choices[0].get("message", {}).get("content") if choices else None
        report["status"] = "ok" if isinstance(content, str) and content.strip() else "unexpected_response"
        report["exact_ok"] = isinstance(content, str) and content.strip() == "OK"
        usage = data.get("usage", {})
        report["usage"] = {
            k: usage[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")
            if isinstance(usage, dict) and type(usage.get(k)) is int
        }
        report["cost_cny"] = None
        report["cost_note"] = "Confirm provider billing; no cache accounting assumptions made."
    except urllib.error.HTTPError as error:
        report.update(status="http_error", http_status=error.code)
        try:
            error_body = json.loads(error.read(8192))
            detail = error_body.get('error', {})
            if isinstance(detail, dict):
                for field in ('code', 'type', 'message'):
                    value = detail.get(field)
                    if isinstance(value, (str, int)):
                        safe = str(value).replace(key, '[REDACTED]')
                        safe = re.sub(r'sk-[A-Za-z0-9_\-]+', '[REDACTED]', safe)
                        report['error_' + field] = safe[:500]
        except (ValueError, AttributeError):
            pass
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError, IndexError, TypeError):
        report["status"] = "network_or_response_error"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Probe status: {report['status']}. Safe metadata saved to artifacts/api-probe.json")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
