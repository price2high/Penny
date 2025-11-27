# GitHub Organization Authentication Guide

## Understanding the Difference

- **Deployment Keys**: For automated systems (CI/CD, servers) - one key per repository
- **Personal Access Tokens (PAT)**: For your personal CLI use - works across all repos
- **SSH Keys**: For your personal account - works across all repos

**For regular push/pull from CLI, you DON'T need deployment keys!**

---

## Option 1: Personal Access Token (Recommended for CLI)

This works even if deployment keys are disabled because it's tied to your personal account.

### Create a PAT:

1. Go to: https://github.com/settings/tokens/new
2. Name: `Penny Project CLI`
3. Expiration: 90 days (or your preference)
4. Select scopes:
   - ✅ **repo** (Full control of private repositories)
   - ✅ **workflow** (if using GitHub Actions)
5. Click **Generate token**
6. **Copy the token**

### Use it:

```bash
# Push (will prompt for username and token)
git push origin main
# Username: your-github-username
# Password: paste-token-here
```

Credentials will be saved automatically.

---

## Option 2: SSH Key (Personal Account)

Add SSH key to your personal GitHub account (not as deployment key):

1. Generate key:
```bash
ssh-keygen -t ed25519 -C "ptiprice011@gmail.com"
# Press Enter twice
```

2. Copy public key:
```bash
cat ~/.ssh/id_ed25519.pub
```

3. Add to GitHub:
   - Go to: https://github.com/settings/keys
   - Click **"New SSH key"**
   - Paste key, save

4. Update remote:
```bash
git remote set-url origin git@github.com:Cyber-Shawties-LLC/Penny.git
```

5. Test:
```bash
ssh -T git@github.com
git push origin main
```

---

## If You Actually Need Deployment Keys Enabled

**Only organization owners/admins can do this:**

1. Go to your organization: https://github.com/organizations/Cyber-Shawties-LLC/settings
2. Navigate to: **Settings** → **Third-party access** or **Security**
3. Look for **"Deployment keys"** or **"Repository access"** settings
4. Enable if available

**Note**: Deployment keys are typically for:
- CI/CD pipelines (GitHub Actions, Jenkins, etc.)
- Automated deployments
- Server-to-GitHub communication

**NOT for personal CLI use!**

---

## Quick Solution for Your Case

Since you just want CLI push/pull, use **Personal Access Token** (Option 1 above). It works regardless of deployment key settings because it's tied to your personal account permissions, not the organization's deployment key policy.

