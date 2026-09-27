#!/usr/bin/env bash
# Deploy a version on the server through AWS Systems Manager, and wait for it.
# Used by .github/workflows/deploy.yml, which provides AWS credentials:
#
#   INSTANCE_ID=i-0123... VERSION=<git commit> deploy/aws/ssm-deploy.sh
#
# On the server this checks out the commit (for its deploy files) and runs
# deploy/deploy.sh, which rolls back by itself if the new version doesn't start.

set -euo pipefail
: "${INSTANCE_ID:?set INSTANCE_ID}" "${VERSION:?set VERSION}"
[[ $VERSION =~ ^[0-9a-f]{40}$ ]] || { echo "VERSION must be a full commit SHA" >&2; exit 1; }

online=$(aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2> /dev/null || true)
if [[ $online != Online ]]; then
    echo "::error::The server ($INSTANCE_ID) isn't connected to Systems Manager (status: ${online:-unknown})." \
        "Is it running? A new server takes a few minutes." >&2
    exit 1
fi

# The document runs these with sh (dash on Ubuntu), so no bash-only features.
commands=$(jq -nc --arg v "$VERSION" '[
  "set -eu",
  "export HOME=/root",
  "for i in $(seq 60); do [ -f /var/lib/python-trainer/bootstrapped ] && break; echo Waiting for the server to finish setting up; sleep 10; done",
  "[ -f /var/lib/python-trainer/bootstrapped ] || { echo The server never finished setting up: see /var/log/python-trainer-bootstrap.log; exit 1; }",
  "cd /opt/python-trainer",
  "git fetch --quiet origin",
  ("git checkout --quiet --force --detach " + $v),
  ("deploy/deploy.sh " + $v)
]')

command_id=$(aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --comment "Deploy ${VERSION:0:12}" \
    --timeout-seconds 600 \
    --parameters "{\"commands\": $commands, \"executionTimeout\": [\"1200\"]}" \
    --query Command.CommandId --output text)
echo "Deploying ${VERSION:0:12} on $INSTANCE_ID (Systems Manager command $command_id)"

status=Pending
deadline=$((SECONDS + 1500))
while ((SECONDS < deadline)); do
    sleep 5
    status=$(aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
        --query Status --output text 2> /dev/null || echo Pending)
    case $status in
        Pending | InProgress | Delayed) ;;
        *) break ;;
    esac
done

echo "----- Output from the server -----"
aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
    --query StandardOutputContent --output text || true
errors=$(aws ssm get-command-invocation --command-id "$command_id" --instance-id "$INSTANCE_ID" \
    --query StandardErrorContent --output text 2> /dev/null || true)
if [[ -n $errors && $errors != None ]]; then
    echo "----- Errors -----"
    echo "$errors"
fi
echo "----------------------------------"

if [[ $status != Success ]]; then
    echo "::error::The deploy ended with status $status. The server keeps running the previous version if it could." >&2
    exit 1
fi
