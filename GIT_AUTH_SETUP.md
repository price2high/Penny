# Git Authentication Setup Guide

## Option 1: Personal Access Token (PAT) - Recommended for Quick Setup

### Step 1: Create a Personal Access Token on GitHub

1. Go to GitHub.com and sign in
2. Click your profile picture → **Settings**
3. Scroll down to **Developer settings** (bottom left)
4. Click **Personal access tokens** → **Tokens (classic)**
5. Click **Generate new token** → **Generate new token (classic)**
6. Give it a name: `Penny Project Access`
7. Select expiration: **90 days** (or your preference)
8. Select scopes (permissions):
   - ✅ **repo** (Full control of private repositories)
   - ✅ **workflow** (if you use GitHub Actions)
9. Click **Generate token**
10. **COPY THE TOKEN IMMEDIATELY** - you won't see it again!

### Step 2: Configure Git to Use the Token

**Method A: Store in Git Credential Manager (Recommended)**
```bash
# This will prompt you for username and password (use token as password)
git push origin main
# Username: your-github-username
# Password: paste-your-token-here
```

**Method B: Store in Git Config (Less Secure)**
```bash
# Store credentials in git config (not recommended for shared machines)
git config --global credential.helper store
git push origin main
# Enter username and token when prompted
```

**Method C: Use Token in URL (One-time)**
```bash
# Replace YOUR_TOKEN with your actual token
git remote set-url origin https://YOUR_TOKEN@github.com/Cyber-Shawties-LLC/Penny.git
git push origin main
# Then change it back:
git remote set-url origin https://github.com/Cyber-Shawties-LLC/Penny.git
```

---

## Option 2: SSH Keys - More Secure (Recommended for Long-term)

### Step 1: Generate SSH Key

```bash
# Generate a new SSH key (replace with your GitHub email)
ssh-keygen -t ed25519 -C "ptiprice011@gmail.com"

# When prompted:
# - Press Enter to accept default file location (~/.ssh/id_ed25519)
# - Enter a passphrase (optional but recommended) or press Enter for no passphrase
```

### Step 2: Add SSH Key to SSH Agent

```bash
# Start the ssh-agent
eval "$(ssh-agent -s)"

# Add your SSH key to the ssh-agent
ssh-add ~/.ssh/id_ed25519
```

### Step 3: Add SSH Key to GitHub

```bash
# Copy your public key to clipboard
cat ~/.ssh/id_ed25519.pub
# Select and copy the entire output
```

Then on GitHub:
1. Go to **Settings** → **SSH and GPG keys**
2. Click **New SSH key**
3. Title: `Penny Project - [Your Computer Name]`
4. Key: Paste your public key
5. Click **Add SSH key**

### Step 4: Change Remote URL to SSH

```bash
# Change remote from HTTPS to SSH
git remote set-url origin git@github.com:Cyber-Shawties-LLC/Penny.git

# Test the connection
ssh -T git@github.com
# You should see: "Hi [username]! You've successfully authenticated..."

# Now push
git push origin main
```

---

## Quick Test

After setting up either method, test it:

```bash
git push origin main
```

If successful, you'll see:
```
Enumerating objects: X, done.
Counting objects: 100% (X/X), done.
Writing objects: 100% (X/X), done.
To https://github.com/Cyber-Shawties-LLC/Penny.git
   [branch] -> [branch]
```

---

## Troubleshooting

### PAT Issues
- **"Authentication failed"**: Token might be expired or wrong
- **"Permission denied"**: Check token has `repo` scope
- **"Token not found"**: Make sure you copied the entire token

### SSH Issues
- **"Permission denied (publickey)"**: SSH key not added to GitHub
- **"Host key verification failed"**: Run `ssh-keyscan github.com >> ~/.ssh/known_hosts`
- **"Could not resolve hostname"**: Check internet connection

### General
- **"Remote origin already exists"**: That's fine, just update the URL
- **"Not a git repository"**: Make sure you're in the project directory

---

## Security Notes

1. **Never commit tokens or keys to Git**
2. **PAT tokens expire** - set a reminder to renew
3. **SSH keys don't expire** - but rotate them periodically
4. **Use different tokens/keys for different projects** (optional but recommended)

