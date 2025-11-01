# Publishing Guide

Guide for publishing GNS3 MCP Server to PyPI and GitHub Releases.

## Prerequisites

### 1. PyPI Account Setup

1. **Create PyPI account:**
   - Register at https://pypi.org/account/register/
   - Verify email address

2. **Generate API token:**
   - Go to https://pypi.org/manage/account/#api-tokens
   - Click "Add API token"
   - Name: `gns3-mcp-github-actions`
   - Scope: **Entire account** (or project-specific after first upload)
   - Copy the token (starts with `pypi-`)
   - **Save it securely** - you cannot view it again!

### 2. GitHub Secret Setup

1. Go to repository settings: https://github.com/ChistokhinSV/gns3-mcp/settings/secrets/actions
2. Click "New repository secret"
3. Name: `PYPI_API_TOKEN`
4. Value: Paste the PyPI API token from step 1
5. Click "Add secret"

## Release Workflow

### Automated Publishing (Recommended)

When you push a version tag, GitHub Actions will automatically:
1. Build desktop extension (.mcpb)
2. Build PyPI distributions (.tar.gz and .whl)
3. Publish to PyPI
4. Create GitHub release with all artifacts

**Steps:**

1. **Update version** in all required files:
   ```bash
   # Update these 3 files to match:
   - gns3_mcp/__init__.py:      __version__ = "0.42.0"
   - pyproject.toml:            version = "0.42.0"
   - mcp-server/manifest.json:  "version": "0.42.0"
   ```

2. **Update CHANGELOG.md** with release notes

3. **Commit changes:**
   ```bash
   git add .
   git commit -m "chore: bump version to 0.42.0"
   ```

4. **Create and push tag:**
   ```bash
   git tag v0.42.0
   git push origin master --tags
   ```

5. **Monitor workflow:**
   - Go to https://github.com/ChistokhinSV/gns3-mcp/actions
   - Watch "Build and Publish MCP Server" workflow
   - Verify all steps pass:
     - ✅ Build .mcpb extension
     - ✅ Build PyPI distributions
     - ✅ Publish to PyPI
     - ✅ Create GitHub release

6. **Verify publication:**
   ```bash
   # Check PyPI (may take a few minutes)
   pip install --upgrade gns3-mcp
   gns3-mcp --version

   # Check GitHub release
   # https://github.com/ChistokhinSV/gns3-mcp/releases/latest
   ```

### Manual Publishing (Fallback)

If automated workflow fails or for testing:

**TestPyPI first:**
```bash
# Build distributions
python -m build

# Upload to TestPyPI
python -m twine upload --repository testpypi dist/*
# Username: __token__
# Password: pypi-... (your TestPyPI token)

# Test installation
pip install --index-url https://test.pypi.org/simple/ --no-deps gns3-mcp
pip install gns3-mcp  # Get dependencies from main PyPI
```

**Production PyPI:**
```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info

# Build fresh
python -m build

# Upload to PyPI
python -m twine upload dist/*
# Username: __token__
# Password: pypi-... (your PyPI token)
```

**Desktop extension:**
```bash
cd mcp-server
npx @anthropic-ai/mcpb pack
# Creates mcp-server.mcpb
```

## Version Numbering

Follow Semantic Versioning (SemVer):

- **Major** (1.0.0): Breaking changes, incompatible API changes
- **Minor** (0.1.0): New features, backward compatible
- **Patch** (0.0.1): Bug fixes, backward compatible

**Examples:**
- `0.41.0` → `0.41.1`: Bug fix (patch)
- `0.41.0` → `0.42.0`: New feature (minor)
- `0.41.0` → `1.0.0`: Breaking change (major)

## Pre-commit Hooks

Hooks automatically rebuild .mcpb extension when you modify:
- `gns3_mcp/server/**/*.py`
- `mcp-server/manifest.json`
- `requirements.txt`

If pre-commit hook fails:
```bash
# Manually rebuild
cd mcp-server
npx @anthropic-ai/mcpb pack

# Add to commit
git add mcp-server.mcpb
git commit --amend --no-edit
```

## GitHub Actions Triggers

The workflow runs on:
- **Tags**: `v*` (e.g., v0.42.0) - **Publishes to PyPI + creates release**
- **Push to master/main** - Builds artifacts only (no publish/release)
- **Manual trigger** - Via GitHub Actions UI (workflow_dispatch)

## Troubleshooting

### PyPI Upload Fails

**"File already exists":**
- Cannot re-upload same version
- Increment version number and rebuild

**"Invalid credentials":**
- Check `PYPI_API_TOKEN` secret in GitHub
- Regenerate token if expired

**"Package name taken":**
- Package name `gns3-mcp` is reserved for this project
- Contact PyPI support if needed

### Build Fails

**"Module not found":**
- Verify all dependencies in `pyproject.toml`
- Check `gns3_mcp/server/__init__.py` imports

**"License deprecation warning":**
- Current warning is non-fatal (builds succeed)
- Can be suppressed in future versions

### Pre-commit Hook Fails

**".mcpb not created":**
- Check Node.js installed: `node --version`
- Verify mcpb package: `npm list -g @anthropic-ai/mcpb`
- Install if missing: `npm install -g @anthropic-ai/mcpb`

**"Cannot find module":**
- Rebuild lib dependencies: `pip install --target=mcp-server/lib ...`

## Post-Release Checklist

After successful release:

- [ ] Verify PyPI package: https://pypi.org/project/gns3-mcp/
- [ ] Test pip installation: `pip install --upgrade gns3-mcp`
- [ ] Verify GitHub release: https://github.com/ChistokhinSV/gns3-mcp/releases
- [ ] Test .mcpb download and installation in Claude Desktop
- [ ] Update documentation if needed
- [ ] Close related GitHub issues
- [ ] Update YouTrack issues
- [ ] Announce on social media/forums (optional)

## Security Notes

**Never commit:**
- PyPI API tokens
- GitHub tokens
- Passwords or credentials

**Token rotation:**
- Rotate PyPI token every 6-12 months
- Immediately rotate if compromised
- Update GitHub secret after rotation

## Support

For issues:
- GitHub Issues: https://github.com/ChistokhinSV/gns3-mcp/issues
- PyPI support: https://pypi.org/help/
