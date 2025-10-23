# Installing GNS3 Skill Globally in Claude Code

This guide explains how to make the GNS3 skill available globally across all Claude Code projects.

## What Are Skills?

**Agent Skills** are modular capabilities that extend Claude Code with specialized expertise and workflows. They consist of:
- Instructions (SKILL.md) - Procedural knowledge and domain expertise
- Scripts (optional) - Executable tools and automation
- Resources (optional) - Reference data, templates, examples

Skills are automatically discovered and loaded by Claude Code when relevant to the task.

## Skill Availability Scopes

### Global Skills (Recommended for GNS3)
**Location**: `~/.claude/skills/` (or `C:\Users\<username>\.claude\skills\` on Windows)

**Benefits**:
- Available in all Claude Code projects
- One-time installation
- Shared across all workspaces
- Perfect for domain expertise (GNS3, networking, etc.)

### Per-Project Skills
**Location**: `.claude/skills/` in project root

**Benefits**:
- Version controlled with project
- Team collaboration through git
- Project-specific workflows
- Can override global skills

## Installation Methods

### Method 1: Automated Installation (Windows)

Run this PowerShell script to install the GNS3 skill globally:

```powershell
# Create global skills directory
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills\gns3"

# Copy GNS3 skill
Copy-Item "C:\HOME\1. Scripts\008. GNS3 MCP\skill\SKILL.md" `
  -Destination "$env:USERPROFILE\.claude\skills\gns3\SKILL.md"

# Verify installation
Get-ChildItem "$env:USERPROFILE\.claude\skills\gns3"
```

### Method 2: Manual Installation

1. **Create the skills directory structure**:
   ```
   C:\Users\<your-username>\.claude\skills\gns3\
   ```

2. **Copy the skill file**:
   - Source: `C:\HOME\1. Scripts\008. GNS3 MCP\skill\SKILL.md`
   - Destination: `C:\Users\<your-username>\.claude\skills\gns3\SKILL.md`

3. **Verify the structure**:
   ```
   C:\Users\<your-username>\.claude\
   └── skills\
       └── gns3\
           └── SKILL.md
   ```

### Method 3: Symbolic Link (Advanced)

Create a symlink to always use the latest version from the project:

```powershell
# Create skills directory
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills"

# Create symbolic link (requires admin rights)
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\skills\gns3" `
  -Target "C:\HOME\1. Scripts\008. GNS3 MCP\skill"
```

**Advantages**:
- Always uses latest skill version
- No need to copy after updates
- Single source of truth

**Disadvantages**:
- Requires administrator privileges
- Link breaks if project moves

## Verifying Installation

### Check File Location

```bash
# Windows (PowerShell)
Get-Content "$env:USERPROFILE\.claude\skills\gns3\SKILL.md" | Select-Object -First 5

# Linux/Mac
cat ~/.claude/skills/gns3/SKILL.md | head -5
```

You should see the GNS3 skill header:
```markdown
# GNS3 Lab Management Skill
```

### Test in Claude Code

1. Open any project in Claude Code
2. Ask: "List the available GNS3 nodes in my lab"
3. Claude should use the GNS3 skill automatically
4. Or explicitly invoke: `/skill gns3` (if supported by your version)

## Skill Structure

### Minimal Skill
```
~/.claude/skills/gns3/
└── SKILL.md          # Core skill instructions
```

### Complete Skill (Optional)
```
~/.claude/skills/gns3/
├── SKILL.md          # Core instructions
├── scripts/          # Automation scripts
│   ├── backup.py
│   └── restore.py
└── examples/         # Reference examples
    └── topology.gns3
```

## Current Installation

✓ **GNS3 Skill installed globally**
- Location: `C:\Users\mail4\.claude\skills\gns3\SKILL.md`
- Size: 4.8 KB
- Scope: Global (available in all projects)

## Updating the Skill

When the skill is updated in the project:

### Manual Update
```bash
# Copy latest version
cp "C:\HOME\1. Scripts\008. GNS3 MCP\skill\SKILL.md" `
  "$env:USERPROFILE\.claude\skills\gns3\SKILL.md"
```

### Automated Update (if using symlink)
No action needed - automatically uses latest version

## Multiple Skills

Install multiple skills in the same directory:

```
C:\Users\<username>\.claude\skills\
├── gns3\
│   └── SKILL.md          # GNS3 networking expertise
├── netbox\
│   └── SKILL.md          # NetBox IPAM workflows
├── ansible\
│   └── SKILL.md          # Ansible automation
└── monitoring\
    └── SKILL.md          # Network monitoring
```

Claude Code automatically discovers and uses all installed skills.

## How Claude Code Uses Skills

### Automatic Discovery
- Claude scans `~/.claude/skills/` on startup
- Loads skill metadata (not full content initially)
- Keeps Claude fast with lazy loading

### Intelligent Loading
- Only loads skills relevant to current task
- Uses skill names and content for matching
- Combines multiple skills if needed

### Skill Priority
1. Per-project skills (`.claude/skills/`)
2. Global skills (`~/.claude/skills/`)
3. Built-in Claude Code skills

If same-named skill exists in both locations, project version takes precedence.

## Troubleshooting

### Skill Not Recognized

**Problem**: Claude doesn't use the GNS3 skill

**Solutions**:
1. Verify file location: `~/.claude/skills/gns3/SKILL.md`
2. Check file name is exactly `SKILL.md` (case-sensitive on Linux/Mac)
3. Restart Claude Code to reload skills
4. Ensure SKILL.md has valid Markdown

### Skill Not Loading

**Problem**: Skill exists but doesn't load

**Check**:
1. File permissions (should be readable)
2. No syntax errors in SKILL.md
3. File encoding is UTF-8
4. No special characters in skill directory name

### Multiple Versions Conflict

**Problem**: Unsure which skill version is being used

**Solution**:
1. Use only global OR project skills, not both
2. Check skill priority (project > global)
3. Remove unused version

## Best Practices

### Naming Conventions
- Use lowercase skill directory names: `gns3`, not `GNS3`
- Use descriptive names: `gns3-networking`, not `skill1`
- Avoid spaces: `network-automation`, not `network automation`

### Skill Organization
- One skill per directory
- Keep SKILL.md focused and concise
- Add examples for complex workflows
- Include version info in SKILL.md

### Version Control
- Track project skills in git
- Document global skill installations in project README
- Use semantic versioning for skills
- Keep changelog in SKILL.md

### Maintenance
- Regularly update skills with new workflows
- Test skills after Claude Code updates
- Remove obsolete skills
- Document skill dependencies

## Advanced: Skill Development

### Creating New Skills

1. **Create skill directory**:
   ```bash
   mkdir -p ~/.claude/skills/my-skill
   ```

2. **Write SKILL.md**:
   ```markdown
   # My Custom Skill

   ## Core Concepts
   [Domain knowledge here]

   ## Common Workflows
   [Step-by-step procedures]

   ## Examples
   [Code samples and templates]
   ```

3. **Test the skill**:
   - Open Claude Code
   - Ask question requiring the skill
   - Verify Claude uses your instructions

### Skill Content Structure

Follow progressive disclosure pattern:
1. **Core Concepts** - Essential domain knowledge
2. **Common Workflows** - Step-by-step procedures
3. **Device-Specific Details** - Detailed references
4. **Examples** - Real-world use cases

See `skill/SKILL.md` for complete example.

## Resources

- **Anthropic Skills Announcement**: https://www.anthropic.com/news/skills
- **Claude Code Skills Docs**: https://docs.claude.com/en/docs/claude-code/skills
- **GNS3 Documentation**: https://docs.gns3.com/
- **Project README**: `C:\HOME\1. Scripts\008. GNS3 MCP\README.md`

## Related Files

- **Source Skill**: `C:\HOME\1. Scripts\008. GNS3 MCP\skill\SKILL.md`
- **Installed Location**: `C:\Users\mail4\.claude\skills\gns3\SKILL.md`
- **Project Instructions**: `C:\HOME\1. Scripts\008. GNS3 MCP\CLAUDE.md`

## Summary

✓ **Installation Complete**
- GNS3 skill installed globally
- Available in all Claude Code projects
- No additional configuration needed
- Ready to use immediately

**Next Steps**:
1. Restart Claude Code (if running)
2. Test the skill with a GNS3 question
3. Update skill when workflows change
4. Consider creating more domain-specific skills

**Questions to Try**:
- "How do I start all nodes in my GNS3 lab?"
- "What's the correct way to configure a MikroTik router in GNS3?"
- "Help me backup my GNS3 project configuration"
- "Show me how to connect to a device console in GNS3"

Claude will automatically use the GNS3 skill to provide expert guidance!
