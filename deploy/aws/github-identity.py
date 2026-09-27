"""Print who GitHub Actions says this job is, as AWS sees it (the OIDC token's
claims, never the token). AWS lets the deploy role be used only when `sub`
matches its trust policy, so this is the first thing to check when AWS says
"Not authorized to perform sts:AssumeRoleWithWebIdentity".

Runs in a GitHub Actions job with `permissions: id-token: write`.
"""

import base64
import json
import os
import sys
import urllib.request

url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
if not url:
    sys.exit("No OIDC token available: the job needs `permissions: id-token: write`.")
request = urllib.request.Request(
    f"{url}&audience=sts.amazonaws.com",
    headers={"Authorization": f"bearer {os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']}"},
)
token = json.load(urllib.request.urlopen(request, timeout=10))["value"]
payload = token.split(".")[1]
claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
for key in ("sub", "aud", "iss", "repository", "ref", "environment", "event_name"):
    print(f"{key:12} {claims.get(key)}")
