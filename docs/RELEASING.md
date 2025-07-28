# Release Process

This document describes how to create a new release of Strot.

## Prerequisites

1. **GitHub Repository Access**: You need write access to create tags and releases
2. **PyPI Token**: Set up `PYPI_API_TOKEN` in GitHub repository secrets
3. **Clean Working Directory**: Ensure all changes are committed and pushed

## Release Steps

### 1. Prepare the Release

1. **No Manual Version Updates Required**:

   - Version is automatically determined from git tags
   - Uses `uv-dynamic-versioning` with hatchling build backend
   - Both main package and API package get version from the same git tag

2. **Update CHANGELOG.md** (Optional - will be auto-generated):
   ```bash
   # Add release notes to CHANGELOG.md under [Unreleased] section
   # Move items from [Unreleased] to new version section if needed
   ```

### 2. Create and Push Tag

```bash
# Create annotated tag
git tag -a v1.2.3 -m "Release version 1.2.3"

# Push tag to trigger release workflow
git push origin v1.2.3
```

### 3. Monitor Release Process

1. **GitHub Actions**: Watch the release workflow at `https://github.com/vertexcover-io/strot/actions`
2. **Verify Steps**:
   - ✅ Package builds successfully
   - ✅ Changelog generates
   - ✅ GitHub release created
   - ✅ PyPI package published

### 4. Post-Release Verification

1. **Check GitHub Release**: Visit `https://github.com/vertexcover-io/strot/releases`
2. **Verify PyPI**: Check `https://pypi.org/project/strot/`
3. **Test Installation**:
   ```bash
   pip install strot==1.2.3
   python -c "from importlib.metadata import version; print(version('strot'))"
   ```

## Automated Workflow Details

The GitHub Action (`release.yml`) automatically:

1. **Triggers on**: Tag push matching `v*.*.*` pattern
2. **Dynamic Versioning**: Automatically sets version from git tag using uv-dynamic-versioning
3. **Builds Package**: Uses `uv build` with hatchling backend to create distribution files
4. **Generates Changelog**: Auto-generates from PR titles and labels
5. **Creates GitHub Release**: With changelog and distribution files
6. **Publishes to PyPI**: Using `uv publish`

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (`1.0.0`): Breaking changes
- **MINOR** (`0.1.0`): New features (backward compatible)
- **PATCH** (`0.0.1`): Bug fixes (backward compatible)

## Troubleshooting

### Release Workflow Fails

2. **Build Fails**: Check `pyproject.toml` configuration
3. **PyPI Upload Fails**:
   - Verify `PYPI_API_TOKEN` secret is set
   - Check if version already exists on PyPI
   - Ensure package name is available

### Tag Already Exists

```bash
# Delete local tag
git tag -d v1.2.3

# Delete remote tag
git push --delete origin v1.2.3

# Recreate with new commit
git tag -a v1.2.3 -m "Release version 1.2.3"
git push origin v1.2.3
```

## Emergency Rollback

If a release has critical issues:

1. **Yank from PyPI** (if published):

   ```bash
   uv pip install twine
   twine upload --repository pypi --skip-existing dist/*
   ```

2. **Mark GitHub Release as Pre-release**:

   - Go to GitHub Releases
   - Edit the problematic release
   - Check "This is a pre-release"

3. **Create Hotfix Release**:
   - Fix the issue
   - Follow normal release process with patch version

## Changelog Labels

The automated changelog groups PRs by labels:

- `feature`, `enhancement`, `feat` → 🚀 Features
- `bug`, `fix`, `bugfix` → 🐛 Bug Fixes
- `documentation`, `docs` → 📚 Documentation
- `maintenance`, `refactor`, `chore` → 🔧 Maintenance
- `security` → 🔒 Security
- `performance`, `perf` → ⚡ Performance
- `test`, `testing` → 🧪 Testing
- `dependencies`, `deps` → 📦 Dependencies

Use these labels on PRs for better changelog organization.
