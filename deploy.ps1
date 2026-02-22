# deploy.ps1 — build with Windows Ruby, deploy via WSL rsync

# ─── Local secrets (not committed) ────────────────────────────────────────────
. "$PSScriptRoot\deploy.env.ps1"
# ──────────────────────────────────────────────────────────────────────────────

Write-Host "==> Building Jekyll site (production)..."
$env:JEKYLL_ENV = "production"
bundle exec jekyll build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Deploying to $RemoteHost via SFTP..."
wsl lftp -e "set sftp:connect-program 'ssh -a -x'; \
set net:connection-limit 10; \
set net:limit-max 10; \
set net:persist-retries 2; \
open -u ${RemoteUser}, sftp://${RemoteHost}; \
mirror -R --delete --verbose --parallel=10 -x '\.jpg$' _site/ ${RemotePath}/; \
quit"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Done! Site live at https://paws.fretter.eu"
