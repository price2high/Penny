# Quick Git Authentication Setup

## Step 1: Create GitHub Personal Access Token

1. Go to: https://github.com/settings/tokens
2. Click **"Generate new token"** → **"Generate new token (classic)"**
3. Name: `CLI Access`
4. Expiration: Choose your preference (90 days recommended)
5. Check ✅ **repo** (this gives full repository access)
6. Click **"Generate token"**
7. **COPY THE TOKEN** (you won't see it again!)

## Step 2: Test Push (It Will Prompt for Credentials)

Run this command:
```bash
git push origin main
```

When prompted:
- **Username**: Your GitHub username
- **Password**: Paste the token (not your GitHub password!)

The credentials will be saved automatically for future use.

---

## Alternative: SSH Keys (One-time setup, no passwords)

If you prefer SSH (no password prompts after setup):

```bash
# 1. Generate SSH key
ssh-keygen -t ed25519 -C "ptiprice011@gmail.com"
# Press Enter for default location, Enter for no passphrase (or set one)

# 2. Copy public key
cat ~/.ssh/id_ed25519.pub
# Copy the entire output

# 3. Add to GitHub: https://github.com/settings/keys
# Click "New SSH key", paste the key, save

# 4. Change remote to SSH
git remote set-url origin git@github.com:Cyber-Shawties-LLC/Penny.git

# 5. Test
ssh -T git@github.com
git push origin main
```

---

**I've already configured credential storage for you. Just create the token and push!**

