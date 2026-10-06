# Tearing down Python Trainer

Python Trainer moved into [Spellbound](https://github.com/kristoferfosmoe/spelling-app).
It was only used for early testing, so no accounts or progress need saving.
This is how to switch off everything it used.

The repository side is already done: CI no longer pushes images or deploys,
the *Deploy* workflow is gone, and Dependabot is off.

## 1. AWS (in CloudShell, in the region the stack is in)

```bash
STACK=python-trainer

# Note the server and the backup bucket before the stack is gone.
out() { aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text; }
INSTANCE=$(out InstanceId)
BUCKET=$(out BackupBucket)
echo "server: $INSTANCE  backups: $BUCKET"

# The server has termination protection; the stack can't delete it until it's off.
aws ec2 modify-instance-attribute --instance-id "$INSTANCE" --no-disable-api-termination

# Deletes the server, its disk, the Elastic IP, the security group, the image
# registries (with their images), the IAM roles, the deploy document, the DNS
# record (if Route 53 was used) and the GitHub OIDC provider (if the stack made it).
aws cloudformation delete-stack --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --stack-name "$STACK"

# The backup bucket is kept on purpose by the stack. Delete it and the backups too.
aws s3 rb "s3://$BUCKET" --force
```

If `wait` reports a failure, look at the stack's *Events* tab in the
CloudFormation console: it names the resource that couldn't be deleted.
Fix that and run `delete-stack` again.

Check afterwards: EC2 → Instances, Elastic IPs and Volumes, ECR, and S3 have
nothing left named `python-trainer`.

## 2. DNS

If the domain's DNS isn't in Route 53, remove the A record for the site's
domain at your DNS provider.

## 3. GitHub

- **Settings → Secrets and variables → Actions → Variables:** delete
  `DEPLOY_TO_AWS`, `AWS_REGION`, `AWS_DEPLOY_ROLE_ARN`, `EC2_INSTANCE_ID`,
  `IMAGE_REPO` and `SITE_URL`.
- **Settings → Environments:** delete `production`.
- **Settings → General → Danger Zone → Archive this repository**, so it stays
  read-only for reference.
