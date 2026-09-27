# Deploying Python Trainer on AWS EC2

This guide puts the site on one EC2 server with HTTPS, a PostgreSQL database
and nightly backups to S3. It takes about an hour the first time. You need:

- an AWS account,
- a domain name you can add DNS records to (for example `trainer.yourteam.org`),
- a computer with SSH.

Everything runs in Docker on the server, in three containers:

| Container | What it does |
|---|---|
| `caddy` | HTTPS (it gets and renews the certificate by itself), serves the web app, forwards `/api` and `/admin` to Django |
| `web` | Django: accounts, lessons, progress, the admin. On every start it updates the database and re-imports the lessons from `content/` |
| `db` | PostgreSQL. Its data lives in a Docker volume that survives restarts and rebuilds |

Student code never runs on the server. It runs in each student's browser, so
a small server is enough.

## 1. Launch the server

In the AWS console → **EC2** → **Launch instance**:

| Setting | Value |
|---|---|
| Name | `python-trainer` |
| Image | **Ubuntu Server 24.04 LTS** |
| Instance type | **t3.small** (2 vCPU, 2 GB). **t4g.small** (ARM) also works and costs less. |
| Key pair | Create one, or use your own, for SSH |
| Storage | 20 GB gp3 |
| Security group | Allow **SSH (22) from My IP**, **HTTP (80)** and **HTTPS (443)** from anywhere. Optionally allow **UDP 443** from anywhere, for HTTP/3. |

Then:

1. **Elastic IP**: EC2 → Elastic IPs → Allocate, then Associate it with the instance.
   The address stays the same when the server restarts.
2. **DNS**: at your domain provider, add an **A record** for your domain (say
   `trainer.yourteam.org`) pointing to the Elastic IP. Wait until
   `ping trainer.yourteam.org` shows that IP.

## 2. Install Docker

```bash
ssh ubuntu@trainer.yourteam.org

sudo apt update && sudo apt -y upgrade
sudo apt -y install unattended-upgrades git   # automatic security updates
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit      # log out and back in so the docker group applies
```

## 3. Configure and start the site

```bash
ssh ubuntu@trainer.yourteam.org
git clone https://github.com/kristoferfosmoe/python-trainer.git
cd python-trainer/deploy
cp .env.example .env
nano .env
```

In `.env`, set:

- **`DOMAIN`**: your domain, like `trainer.yourteam.org`.
- **`DJANGO_ALLOWED_HOSTS`**: the same domain.
- **`DJANGO_CSRF_TRUSTED_ORIGINS`**: `https://` + the domain.
- **`DJANGO_SECRET_KEY`** and **`POSTGRES_PASSWORD`**: long random values. Make
  them with:

  ```bash
  python3 -c "import secrets; print(secrets.token_urlsafe(50))"
  ```

Keep `.env` private. It's ignored by git and must never be committed.

Start everything (the first build takes a few minutes):

```bash
docker compose up -d --build
docker compose logs -f web      # Ctrl+C to stop watching
```

You should see the database migrations run, then
`Imported ... worlds, ... playground challenges, 1 course(s) and 28 lessons`.
Open `https://trainer.yourteam.org`. Caddy gets the HTTPS certificate on the
first visit, which can take a few seconds.

Health check: `https://trainer.yourteam.org/api/health` answers `{"ok": true}`.

## 4. Create your admin account and a team

```bash
docker compose exec web python manage.py createsuperuser
```

Pick a username and a strong password (at least 10 characters). Then go to
`https://trainer.yourteam.org/admin/`:

- **Teams → Add team**: give it a name. A **join code** (like `K7Q2MX`) is made
  automatically. Students type it when they sign up, or on their account page.
- **Coaches** (other adults): **Users → Add user**. Set *Kind* to "Adult",
  give them a strong password, then add them to the team as **Coach** under
  **Memberships**. Coaches and mentors can see challenge solutions.
- **A student forgot their PIN**: tick them in **Users**, then choose the
  action "Give selected students a new PIN". The new PIN appears at the top of
  the page.
- **Lessons**: under **Curriculum → Lessons**. Saving a lesson runs all of its
  code first, and refuses the save if something is wrong. Lessons that come
  from files in `content/` are replaced on every deploy. To keep your own
  version, give it a new slug, or edit the file in the repository instead.

## 5. Nightly backups to S3

1. **S3 → Create bucket**, e.g. `yourteam-trainer-backups`. Keep "Block all
   public access" on. Optionally add a lifecycle rule to delete backups after 90
   days.
2. **IAM → Roles → Create role** → *AWS service* → *EC2*. Add an inline policy
   (put your bucket name in):

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": ["s3:PutObject"],
       "Resource": "arn:aws:s3:::yourteam-trainer-backups/*"
     }]
   }
   ```

3. **EC2 → your instance → Actions → Security → Modify IAM role**: choose that
   role.
4. On the server:

   ```bash
   sudo snap install aws-cli --classic
   # In deploy/.env: BACKUP_S3_URI=s3://yourteam-trainer-backups/python-trainer
   sudo mkdir -p /var/backups/python-trainer && sudo chown ubuntu /var/backups/python-trainer
   ./backup.sh          # test it once
   crontab -e           # add this line to run it every night at 03:15 UTC:
   15 3 * * * /home/ubuntu/python-trainer/deploy/backup.sh >> /home/ubuntu/backup.log 2>&1
   ```

**Restoring** a backup (this replaces the current data):

```bash
cd ~/python-trainer/deploy
aws s3 cp s3://yourteam-trainer-backups/python-trainer/trainer-<date>.sql.gz .
gunzip -c trainer-<date>.sql.gz | docker compose exec -T db psql -q -U trainer trainer
docker compose restart web
```

## 6. Updating the site

```bash
cd ~/python-trainer
git pull
cd deploy && docker compose up -d --build
```

The web container runs any database changes and re-imports the lessons when it
starts. If a lesson file has a problem, the import is skipped, the site keeps
the lessons it had, and the log says what's wrong.

**One-click deploys (optional)**: the **Deploy** workflow in GitHub Actions does
the same over SSH. It needs four repository secrets:

| Secret | Value |
|---|---|
| `EC2_HOST` | your domain |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | the private key of a key pair used only for deploys. Add its public key to `~/.ssh/authorized_keys` on the server. |
| `EC2_KNOWN_HOSTS` | the output of `ssh-keyscan -H trainer.yourteam.org` |

You'll also need to allow SSH from GitHub's addresses, or run the steps above
by hand.

## Everyday commands

```bash
cd ~/python-trainer/deploy
docker compose ps                    # what's running
docker compose logs -f web           # Django's log
docker compose logs -f caddy         # HTTPS and web server log
docker compose restart web           # restart Django
docker compose exec web python manage.py import_content   # reload lessons now
```

## Costs (rough, 2026 on-demand prices)

- t3.small: about $15 a month (t4g.small: about $12).
- Elastic IP, 20 GB disk and S3 backups: a few dollars a month.

## Troubleshooting

| Problem | Try |
|---|---|
| The browser says the certificate is invalid | DNS must point at the Elastic IP *before* Caddy starts: `docker compose logs caddy`, then `docker compose restart caddy` |
| "502 Bad Gateway" | Django isn't up yet or crashed: `docker compose logs web` |
| "Bad Request (400)" | `DJANGO_ALLOWED_HOSTS` doesn't match the domain |
| Sign-in fails with "session expired" | `DJANGO_CSRF_TRUSTED_ORIGINS` must be `https://` + your domain |
| A student is locked out | Wait 5 minutes, or use "Unlock selected accounts" on Users in the admin |
| Python never starts in the browser | School networks sometimes block WebAssembly. Try another network, and check the browser console. |

## Security notes

- Keep port 22 open to your own IP only, or use AWS Systems Manager Session
  Manager instead of SSH.
- `unattended-upgrades` installs Ubuntu security updates automatically.
  Rebuild the containers now and then (`docker compose build --pull`) to get
  updated base images.
- Students have no email or real name on file. Tell them not to use their
  real name as a username.
- Sign-in protection: an account locks for 5 minutes after 5 wrong PINs, and
  a computer is blocked for 15 minutes after 30 failed sign-ins.
