# Future Roadmap

This document outlines potential future improvements for review-roadmap and discusses the trade-offs of different implementation orderings.

---

## Planned Improvements

### 1. PyPI Publication

**Goal:** Allow users to install via `pip install review-roadmap` without cloning the repository.

**Benefits:**
- Dramatically lowers the barrier to entry for new users
- Enables versioned releases with proper semantic versioning
- Makes dependency management cleaner for users
- Required prerequisite for GitHub Actions marketplace distribution

**Concerns:**
- Slows down the development cycle (need to publish releases for users to get updates)
- Requires maintaining version numbers and changelogs
- Need to decide on a package name (check availability on PyPI)
- Currently in a personal repo—may want to wait until migration to avoid package ownership transfer issues

**Implementation Notes:**
- The project already has a `pyproject.toml` with proper metadata
- Would need to set up GitHub Actions for automated PyPI publishing on release tags
- Consider using TestPyPI first to validate the publishing workflow

---

### 2. GitHub Actions Integration

**Goal:** Enable users to automatically generate review roadmaps when PRs are opened or updated.

**Benefits:**
- Zero-friction experience once configured—roadmaps appear automatically
- Fits naturally into existing PR review workflows
- Could significantly increase adoption and visibility
- Demonstrates the tool's value in a highly visible way

**Concerns:**
- Requires secure credential management (GitHub token with write access, LLM API keys)
- Users need to understand the cost implications (LLM API calls per PR)
- Need to handle edge cases (very large PRs, rate limiting, API failures)
- Documentation needs to be excellent—setup complexity could deter users

**Implementation Options:**

| Approach | Pros | Cons |
|----------|------|------|
| **Reusable Workflow** | Easy to adopt, users just reference it | Requires PyPI or action to install the tool |
| **Composite Action** | Self-contained, version-pinned | More complex to maintain |
| **Docker-based Action** | Fully isolated environment | Slower startup, larger footprint |
| **JavaScript Action** | Fast, native to Actions | Would require rewriting the tool |

**Recommended Approach:** Reusable workflow that installs from PyPI, with clear documentation for secrets configuration.

---

### 3. Migration to ambient-code Organization

**Goal:** Move the repository to [github.com/ambient-code](https://github.com/ambient-code) for greater visibility and credibility.

**Benefits:**
- Association with the ambient-code organization's mission around AI-assisted development
- Greater visibility and potential for community contributions
- Aligns with the "Code Shepherd" paradigm—this tool helps developers guide AI-generated code reviews
- Professional presentation for potential enterprise users

**Concerns:**
- Need to demonstrate sufficient value to the org maintainers first
- Should have a stable, well-documented release before proposing
- Package ownership on PyPI would need to be transferred (or published under org from the start)
- GitHub Actions marketplace listing would need to be under the org

**Prerequisites for Migration:**
- [ ] Stable release with proven functionality
- [ ] Comprehensive documentation
- [ ] Test coverage for core functionality
- [ ] Clean, maintainable codebase
- [ ] Evidence of value (user feedback, usage metrics, or compelling demo)

---

## Recommended Implementation Order

### Option A: PyPI → GitHub Actions → Migration (Recommended)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. PyPI        │────▶│  2. GH Actions  │────▶│  3. Migration   │
│  Publication    │     │  Integration    │     │  to ambient-code│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Rationale:**
1. **PyPI first** establishes a proper release process and makes the tool accessible
2. **GitHub Actions** becomes much easier once PyPI exists (just `pip install` in the workflow)
3. **Migration** happens last when there's demonstrated value and a polished package

**Pros:**
- Each step builds naturally on the previous
- Can start building a user base before migration
- GitHub Actions success provides strong evidence for migration pitch

**Cons:**
- May need to transfer PyPI package ownership during migration
- Users who adopt early will need to update their configs after migration

---

### Option B: Migration → PyPI → GitHub Actions

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. Migration   │────▶│  2. PyPI        │────▶│  3. GH Actions  │
│  to ambient-code│     │  Publication    │     │  Integration    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Rationale:**
- Get the repo in its "final home" before publishing anything
- All public artifacts (PyPI, Actions) are under the org from day one

**Pros:**
- Clean ownership from the start—no transfers needed
- Professional appearance from first public release
- org branding on all distribution channels

**Cons:**
- Delays everything until migration is approved
- Need to convince org maintainers with less tangible evidence
- Longer time before users can easily install the tool

---

### Option C: GitHub Actions → PyPI → Migration

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. GH Actions  │────▶│  2. PyPI        │────▶│  3. Migration   │
│  (from source)  │     │  Publication    │     │  to ambient-code│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

**Rationale:**
- GitHub Actions can clone and install from source
- Immediate visibility in the PR workflow could drive adoption

**Pros:**
- Fastest path to demonstrating value in real workflows
- Visual evidence (roadmap comments on PRs) is compelling

**Cons:**
- Installing from source in Actions is slower and less reliable
- Harder to version-pin without releases
- More complex workflow configuration

---

## Recommendation

**Go with Option A (PyPI → GitHub Actions → Migration)** for these reasons:

1. **PyPI is relatively low-risk** and can be done quickly with the existing `pyproject.toml`
2. **Development velocity concern is manageable:**
   - Use `pip install -e .` locally for development
   - Only publish releases for stable milestones
   - Users can still install from git for bleeding-edge: `pip install git+https://github.com/jwm4/review-roadmap.git`
3. **GitHub Actions will be much cleaner** with PyPI (one-liner install vs. checkout + setup)
4. **Migration pitch is stronger** with: "Here's a working PyPI package with GitHub Actions integration that's already helping developers"

### Suggested Milestones

| Milestone | Target | Key Deliverables |
|-----------|--------|------------------|
| **v0.1.0** | Soon | PyPI publication, basic documentation |
| **v0.2.0** | +2 weeks | GitHub Actions reusable workflow, setup guide |
| **v0.3.0** | +4 weeks | Refinements based on user feedback |
| **v1.0.0** | TBD | Stable release, candidate for ambient-code migration |

---

## Open Questions

1. **Package name availability:** Is `review-roadmap` available on PyPI? If not, alternatives could be `pr-roadmap`, `code-review-roadmap`, etc.

2. **GitHub Actions secrets management:** How should users configure LLM API keys? Options include:
   - Repository secrets (simple but per-repo)
   - Organization secrets (shared across repos)
   - OIDC with cloud provider vaults (most secure, most complex)

3. **Cost controls for Actions:** Should the action have built-in limits (e.g., skip PRs with >100 files, rate limiting)?

4. **ambient-code alignment:** Does this tool fit the org's current focus areas? Worth an informal conversation before investing heavily in migration prep.

