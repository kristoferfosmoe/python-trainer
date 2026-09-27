#!/usr/bin/env bash
# Set the address the site is served at, then restart it if it's running.
#
#   sudo deploy/set-address.sh trainer.yourteam.org   # a domain: HTTPS (Caddy gets the certificate)
#   sudo deploy/set-address.sh                        # no domain: plain HTTP on the server's IP
#
# Without a domain there's no HTTPS, so PINs and passwords cross the network
# unencrypted. Fine for trying things out; use a domain before real students do.
# Then update the GitHub variable SITE_URL to match (the script prints it).

set -euo pipefail
export PATH="$PATH:/usr/local/bin:/snap/bin"

domain=${1:-}
cd "$(dirname "${BASH_SOURCE[0]}")"
[[ -f .env ]] || { echo "deploy/.env is missing." >&2; exit 1; }
if [[ -n $domain && ! $domain =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$ ]]; then
    echo "'$domain' isn't a domain name like trainer.yourteam.org (lowercase, no https://)." >&2
    exit 1
fi

# Replace KEY=... in .env, or add it.
put() {
    if grep -q "^$1=" .env; then
        sed -i "s|^$1=.*|$1=$2|" .env
    else
        printf '%s=%s\n' "$1" "$2" >> .env
    fi
}

if [[ -n $domain ]]; then
    put DOMAIN "$domain"
    put DJANGO_ALLOWED_HOSTS "$domain"
    put DJANGO_CSRF_TRUSTED_ORIGINS "https://$domain"
    put DJANGO_SECURE_COOKIES true
    url="https://$domain"
else
    # Caddy serves plain HTTP for any address (docker-compose.yml), and
    # Django accepts the IP and sends cookies without HTTPS.
    put DOMAIN ""
    put DJANGO_ALLOWED_HOSTS "*"
    put DJANGO_CSRF_TRUSTED_ORIGINS ""
    put DJANGO_SECURE_COOKIES false
    # The server's public IP, from EC2's instance metadata (IMDSv2).
    imds() { curl -sf --noproxy '*' --max-time 2 "$@"; }
    token=$(imds -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60" || true)
    ip=$(imds -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/public-ipv4 || true)
    [[ $ip =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || ip="SERVER-IP"
    url="http://$ip"
fi

if [[ -n $(docker compose ps -q web 2> /dev/null) ]]; then
    docker compose up -d --no-build
fi
echo "The site's address is now $url"
echo "Set the GitHub variable SITE_URL to $url"
