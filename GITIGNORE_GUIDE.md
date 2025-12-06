# Git Ignore Configuration

## 🔐 Files NEVER Committed to Git

### Sensitive Data
```
✅ app_data/                    # All application data
✅ app_data/config.json         # Login credentials (Base64)
✅ app_data/token.json          # Google OAuth token
✅ app_data/zalo_accounts.json  # Zalo accounts list
✅ app_data/message_templates/  # Message templates
✅ app_data/zalo_session_*/     # Browser sessions

✅ credentials.json             # Google API credentials
✅ token.json                   # Google OAuth token (root)
✅ config.json                  # Old config (legacy)
✅ zalo_accounts.json           # Old accounts (legacy)
```

### Downloaded Files
```
✅ downloads_contracts/         # All downloaded contracts
✅ *.xlsx                       # Excel exports (may contain customer data)
✅ *.pdf                        # PDF files (usually contracts)
```

### Development Files
```
✅ __pycache__/                 # Python cache
✅ *.pyc, *.pyo, *.pyd         # Compiled Python
✅ venv/, env/, .venv/         # Virtual environments
✅ .pytest_cache/              # Test cache
✅ .idea/, .vscode/            # IDE settings
✅ .DS_Store, Thumbs.db        # OS files
```

### Build & Temporary
```
✅ *.log                        # Log files
✅ *.tmp, *.bak                # Temporary files
✅ dist/, build/               # Build outputs
✅ *.zip, *.tar.gz             # Archives
```

## ✅ Files COMMITTED to Git

### Source Code
```
✅ *.py                         # All Python source files
✅ requirements.txt             # Dependencies list
✅ README.md                    # Documentation
✅ CHANGELOG.md                 # Version history
✅ .gitignore                   # This config
```

### Configuration Templates
```
✅ config.json.example          # Example config (no real credentials)
```

### Documentation
```
✅ app_data/README.md           # Folder documentation
✅ downloads_contracts/README.md # Folder documentation
```

## 🔍 Check What's Ignored

```bash
# See all tracked files
git ls-files

# Check if a specific file is ignored
git check-ignore -v <filename>

# See ignored files
git status --ignored

# Dry-run what would be added
git add -A -n
```

## 🚨 IMPORTANT

Before committing, ALWAYS verify:

```bash
# 1. Check status
git status

# 2. Check diff
git diff

# 3. Make sure no sensitive data
git diff | grep -i "password\|token\|credential\|secret\|api_key"

# 4. Then commit
git add .
git commit -m "Your message"
git push
```

## 🔄 If Accidentally Committed Sensitive Data

```bash
# Remove from Git but keep local file
git rm --cached <filename>
git commit -m "Remove sensitive file"
git push

# Remove from Git history (DANGEROUS!)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch <filename>" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (requires force push permission)
git push origin --force --all
```

## 📝 Update .gitignore

If you need to modify ignore rules:

1. Edit `.gitignore`
2. Clear Git cache:
   ```bash
   git rm -r --cached .
   git add .
   git commit -m "Update .gitignore"
   ```

---

**Last Updated**: December 6, 2025  
**Version**: 1.3.0
