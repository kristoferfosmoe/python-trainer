# Deploying Python Trainer on AWS

This guide puts the site on one EC2 server with HTTPS, and sets up
**continuous deployment**: every merge to `main` is tested, built and
deployed by itself. Setting it up takes about 45 minutes the first time.

## What you get

```
merge to main ──▶ GitHub Actions: all tests pass
                   ──▶ build the images, push them to Amazon ECR (tagged with the commit)
                   ──▶ tell the server to deploy that commit (AWS Systems Manager)
                          server: back up the database, pull the images, restart,
                                  wait for /api/health to report the new commit
                                  ✖ didn't start? go back to the previous version
                   ──▶ check https://your-site/api/health answers with the new commit
```

- **One server** runs three containers with Docker Compose: `caddy` (HTTPS,
  certificates renew by themselves), `web` (Django) and `db` (PostgreSQL).
  Student code runs in the students' browsers, so a small server is plenty.
- **Safe deploys**: a database backup before every deploy, a health check,
  and an automatic rollback if the new version doesn't come up.
- **Nightly backups** to a private S3 bucket (kept 90 days).
- **No keys or passwords in GitHub.** GitHub signs in to AWS with OIDC, and
  may only push images and run the deploy on this one server. The server
  has no SSH port: you get a shell in the browser with Session Manager.

Everything on the AWS side comes from one CloudFormation template,
[`deploy/aws/python-trainer.yml`](../deploy/aws/python-trainer.yml).

**You need:** an AWS account you can create IAM roles in, and admin access
to the GitHub repository. A domain name you can add a DNS record to (like
`trainer.yourteam.org`) gives you HTTPS; without one, see
[No domain yet?](#no-domain-yet-use-the-servers-ip).

---

## 1. Create the AWS stack

The easiest way is **AWS CloudShell**, a terminal in the AWS console that
already has the AWS CLI and git.

1. Sign in to the AWS console. At the top right, pick the **region** closest
   to your students (for example *US West (Oregon)*).
2. Open **CloudShell** (the `>_` icon in the top bar) and run, with your
   domain instead of `trainer.yourteam.org`:

   ```bash
   git clone https://github.com/kristoferfosmoe/python-trainer.git
   cd python-trainer

   # The current Ubuntu 24.04 image for this region
   AMI=$(aws ssm get-parameter \
     --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
     --query Parameter.Value --output text)

   aws cloudformation deploy \
     --stack-name python-trainer \
     --template-file deploy/aws/python-trainer.yml \
     --capabilities CAPABILITY_IAM \
     --parameter-overrides DomainName=trainer.yourteam.org UbuntuAmi=$AMI
   ```

   It takes about 3 minutes. Then show what it made:

   ```bash
   aws cloudformation describe-stacks --stack-name python-trainer \
     --query 'Stacks[0].Outputs' --output table
   ```

   Keep this table open: the next steps use its values.

**Optional parameters**, added after `UbuntuAmi=$AMI`:

| Parameter | Default | What it does |
|---|---|---|
| `InstanceType=t3.micro` | `t3.small` | `t3.small` (2 GB, about $15/month) is plenty for a few teams. `t3.micro` (1 GB, about $8) works for a handful of students. |
| `HostedZoneId=Z0123…` | none | If your domain's DNS is in Route 53, the stack adds the DNS record for you (skip step 2). |
| `GitHubOidcProviderArn=arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com` | none | Only if the stack fails with *"Provider with url https://token.actions.githubusercontent.com already exists"*: your account already trusts GitHub, so reuse that. |
| `GitHubRepository=you/python-trainer` | `kristoferfosmoe/python-trainer` | If you deploy from a fork. |

The server sets itself up in the background for about 5 more minutes:
Docker, the AWS CLI, a settings file with new random secrets, and nightly
backups. It doesn't start the site yet; the first deploy does.

## 2. Point your domain at the server

(No domain? Skip this step.)

At your domain's DNS provider, add an **A record** for your domain (for
example `trainer` in the `yourteam.org` zone) with the **ServerIp** from the
table. Wait until `nslookup trainer.yourteam.org` shows that IP. (If you
passed `HostedZoneId`, the stack already did this.)

## 3. Connect GitHub

In the GitHub repository:

1. **Settings → General → Default branch**: switch to `main`, so the
   *Run workflow* buttons use it and pull requests go there.
2. **Settings → Secrets and variables → Actions → Variables tab → New
   repository variable**. Add these six, using the values from the stack's
   outputs table (they're IDs and addresses, not secrets):

   | Name | Value |
   |---|---|
   | `AWS_REGION` | **Region**, e.g. `us-west-2` |
   | `AWS_DEPLOY_ROLE_ARN` | **DeployRoleArn** |
   | `EC2_INSTANCE_ID` | **InstanceId** |
   | `IMAGE_REPO` | **ImageRepository** |
   | `SITE_URL` | **SiteUrl**, e.g. `https://trainer.yourteam.org` (or `http://<the server's IP>` without a domain) |
   | `DEPLOY_TO_AWS` | `true` |

3. **Settings → Environments → New environment** named `production`. Under
   *Deployment branches and tags*, choose **Selected branches** and add
   `main`. Optionally add yourself as a **required reviewer**, so each deploy
   waits for your OK.

## 4. The first deploy

**Actions → CI → Run workflow**, on branch `main`. It runs every test, then
*Push images to the registry*, then *Deploy*. Open the *Deploy* job to see
the server's output. The first deploy takes a few minutes: the server
downloads everything, sets up the database and gets the HTTPS certificate.

When it's green, open your site. `https://trainer.yourteam.org/api/health`
shows `{"ok": true, "version": "<the commit>"}`.

From now on you don't need to do anything: **every merge to `main`
deploys by itself.**

## 5. Make your admin and coach accounts

Open a shell on the server: the stack output **ShellAccess** is a link
straight to it (or EC2 → Instances → *python-trainer* → **Connect** →
**Session Manager** → **Connect**). Then:

```bash
sudo /opt/python-trainer/deploy/manage.sh createsuperuser
sudo /opt/python-trainer/deploy/manage.sh create_coach coach_kim --team "Brick Builders"
```

Pick strong passwords (at least 10 characters). The admin is at
`https://trainer.yourteam.org/admin/`. Coaches sign in on the site and use
**👥 Teams** for everything else: progress, student accounts and sign-in
cards, new PINs, mentors, and the team's robot.

## No domain yet? Use the server's IP

You can start without a domain: leave out `DomainName=` in step 1, skip
step 2, and use the **SiteUrl** output, `http://<the server's IP>`, as
`SITE_URL`. Caddy then serves the site over plain HTTP.

⚠️ Without a domain there's **no HTTPS**, so PINs and passwords cross the
network unencrypted. That's fine for trying the site out, not for real
students on school Wi-Fi. (Everything else works, including running Python
and copying code for Pybricks.)

**Adding a domain later** (or switching a server that was set up with one to
the IP), in a Session Manager shell:

```bash
sudo /opt/python-trainer/deploy/set-address.sh trainer.yourteam.org   # HTTPS on a domain
sudo /opt/python-trainer/deploy/set-address.sh                        # plain HTTP on the IP
```

Point the domain's A record at the server first. The script restarts the
site and prints the new address; put it in the GitHub variable `SITE_URL`.

---

## How a deploy works

1. A merge to `main` starts **CI**. If any test fails, nothing is deployed.
2. **Push images to the registry** builds the `web` and `caddy` images and
   pushes them to ECR, tagged with the commit. The registry keeps the last
   30 versions.
3. **Deploy** asks the server, through Systems Manager, to check out the
   commit and run [`deploy/deploy.sh`](../deploy/deploy.sh), which:
   - backs up the database (to `/var/backups/python-trainer` and S3),
   - pulls the new images and restarts `web` and `caddy` (`db` keeps running),
   - on start, Django updates the database and reloads the lessons,
   - waits up to 5 minutes for `/api/health` to report the new commit,
   - if it doesn't, shows the logs, **goes back to the previous version**,
     and the job fails.
4. Finally the job checks the public site answers with the new commit.

Deploys run one at a time. The site is unavailable for a few seconds while
the containers restart. Every deploy is listed in
`/var/log/python-trainer-deploys.log` on the server.

**Going back to an older version by hand:** **Actions → Deploy → Run
workflow**, and type the commit (the short hash from the commit list is
fine). Any commit that was deployed before works, because its images are
still in the registry. Database changes aren't undone; this project's
migrations only add things, so older versions keep working.

## Everyday commands (in a Session Manager shell)

```bash
cd /opt/python-trainer/deploy
sudo docker compose ps                    # what's running
sudo docker compose logs -f web           # Django's log (Ctrl+C to stop)
sudo docker compose logs -f caddy         # HTTPS and web server log
sudo docker compose logs -f checker       # the lesson checker (admin lesson saves)
cat /var/log/python-trainer-deploys.log   # deploy history
sudo ./manage.sh import_content           # reload the lessons now
```

## Backups

- **Nightly** at 03:15 UTC, and **before every deploy**.
- Kept on the server for 14 days (`/var/backups/python-trainer`) and in the
  S3 bucket (**BackupBucket** in the outputs) for 90 days. The bucket is
  private, encrypted, and kept even if you delete the stack.

**Restoring** a backup (this replaces the current data):

```bash
cd /opt/python-trainer/deploy
aws s3 ls s3://<BackupBucket>/python-trainer/
aws s3 cp s3://<BackupBucket>/python-trainer/trainer-<date>.sql.gz .
gunzip -c trainer-<date>.sql.gz | sudo docker compose exec -T db psql -q -U trainer trainer
sudo docker compose restart web
```

## Changing the server

- **A bigger or smaller server:** in CloudShell, in the `python-trainer`
  folder:

  ```bash
  aws cloudformation deploy --stack-name python-trainer \
    --template-file deploy/aws/python-trainer.yml --capabilities CAPABILITY_IAM \
    --parameter-overrides InstanceType=t3.medium
  ```

  Settings you leave out keep their values. The server restarts, which takes
  a minute.
- ⚠️ **Don't re-run the command from step 1 later.** It looks up the newest
  Ubuntu image, and a new image (like a new disk size or SSH key) makes
  CloudFormation build a **new, empty server** and move the site to it.
  Your data stays safe on the old server, which is kept, but the site would
  start empty. To move to a new server on purpose: take a backup, update
  the stack, run the deploy, restore the backup, then delete the old server
  (turn off its termination protection first: EC2 → Instances → select it →
  Actions → Instance settings → Change termination protection).
- **Deleting everything:** turn off termination protection as above, then
  `aws cloudformation delete-stack --stack-name python-trainer`. The backup
  bucket is kept.

## Costs (rough, on-demand)

| Item | Per month |
|---|---|
| t3.small server (or t3.micro) | about $15 (or $8) |
| Its public IPv4 address | about $3.60 |
| 20 GB disk | about $1.60 |
| Image registry and backups | a few cents |

## Troubleshooting

| Problem | Try |
|---|---|
| Deploy: *"isn't connected to Systems Manager"* | A new server needs about 5 minutes. Check it's running in EC2 → Instances. |
| Deploy: *"The server never finished setting up"* | In a Session Manager shell: `sudo tail -50 /var/log/python-trainer-bootstrap.log`. Fix the problem and run `sudo /opt/python-trainer/deploy/aws/bootstrap.sh` again. |
| Deploy: *"Couldn't download the images"* | The *Push images* job didn't run for that commit (for example, `DEPLOY_TO_AWS` was set later). Run **Actions → CI → Run workflow** on `main`. |
| Deploy: *"didn't come up"* and rolled back | The job's output shows the new version's logs. The previous version is running. |
| Deploy succeeded, but *"doesn't answer with"* the new version | DNS doesn't point at the server yet, or HTTPS couldn't get a certificate: `sudo docker compose logs caddy`. |
| The *Push images* and *Deploy* jobs are skipped | `DEPLOY_TO_AWS` isn't `true`, or it wasn't a push to `main`. |
| GitHub: *"Not authorized to perform sts:AssumeRoleWithWebIdentity"* | AWS didn't accept who GitHub says the job is. The step *Show who GitHub says this job is* prints it: its `sub` must be `repo:<owner>/<repo>:ref:refs/heads/main` (or `…:environment:production` for *Deploy*; GitHub may add ID numbers, like `<owner>@123/<repo>@456`, which the stack accepts), matching the stack's `GitHubRepository` and `GitHubBranch`. Also check `AWS_DEPLOY_ROLE_ARN`. |
| "Bad Request (400)" in the browser | The domain doesn't match `DJANGO_ALLOWED_HOSTS` in `/opt/python-trainer/deploy/.env`. Fix it and run `sudo docker compose up -d`. |
| Admin: *"The lesson checker isn't running"* when saving a lesson | `sudo docker compose ps checker` and `sudo docker compose logs checker`; `sudo docker compose up -d` starts it again. |
| A student is locked out | Wait 5 minutes, or their coach unlocks them on the student's page. |
| Python never starts in the browser | Some school networks block WebAssembly. Try another network and check the browser console. |

## Security notes

- **No SSH port.** Shell access is through Session Manager, which uses your
  AWS sign-in and is logged. (For SSH anyway, set `SshKeyName` and
  `SshAllowedCidr`.)
- **GitHub holds no AWS keys.** Its role can only be used from `main` or the
  `production` environment, and can only push to these two image
  repositories and run commands on this one server.
- **Secrets are made on the server** (`/opt/python-trainer/deploy/.env`,
  readable only by root) and never leave it.
- The containers can't reach the server's AWS credentials (IMDSv2 with a
  hop limit of 1). The disk and the backups are encrypted.
- **Lesson code from the admin runs in the `checker` container**, which has
  no network, no secrets and a read-only disk. So a staff account that can
  edit lessons can't use lesson code to reach the database or the secret key.
- **The admin's sign-in** (`/admin/login/`) has the same lockouts as the
  app's, so it isn't an easier place to guess passwords.
- **Coaches and admins are signed out** after 2 hours without use and 12
  hours after signing in (students stay signed in for a month), and coaches
  type their password again before making a student a new PIN.
- Ubuntu installs security updates by itself (`unattended-upgrades`). Each
  deploy builds on the newest Python and Caddy base images, and ECR scans
  every image (see the findings in the ECR console). The PostgreSQL image is
  updated by hand: `sudo docker compose pull db && sudo docker compose up -d db`.
- Students have no email or real name on file. Tell them not to use their
  real name as a username.
- Sign-in protection: an account locks for 5 minutes after 5 wrong PINs, and
  a computer is blocked for 15 minutes after 30 failed sign-ins (typos
  followed by the right PIN don't count). New accounts and wrong team codes
  are limited per computer too. To lift a block early, delete the rows in
  the admin under Accounts → Login failures or Rate limit hits.

---

## Without the pipeline: build on any server

To run the site on a server you manage yourself (any Linux machine with
Docker), without AWS or continuous deployment:

```bash
git clone https://github.com/kristoferfosmoe/python-trainer.git
cd python-trainer/deploy
cp .env.example .env        # fill in DOMAIN, the hosts, and two long random secrets
docker compose up -d --build
docker compose exec web python manage.py createsuperuser
```

To update it: `git pull && docker compose up -d --build`. For backups, run
`deploy/backup.sh` nightly from cron. It uploads to S3 if `BACKUP_S3_URI` is
set and the AWS CLI can write there.
