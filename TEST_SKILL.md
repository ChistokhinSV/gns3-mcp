# Testing GNS3 Global Skill

This document verifies that the GNS3 skill is properly installed and accessible.

## Installation Verification

**Skill Location**: `C:\Users\mail4\.claude\skills\gns3\SKILL.md`

**Verification Command**:
```bash
ls -lh "C:\Users\mail4\.claude\skills\gns3"
```

**Expected Output**:
```
total 4.8K
-rw-r--r-- 1 mail4 197609 4.8K Oct 23 13:30 SKILL.md
```

**Status**: ✓ INSTALLED

## Test Questions

To verify the skill is working, ask Claude Code these questions in any project:

### Test 1: Basic GNS3 Workflow
**Question**: "How do I start all nodes in my GNS3 lab?"

**Expected**: Claude should reference the skill and provide step-by-step instructions using MCP tools or GNS3 UI.

### Test 2: Device-Specific Knowledge
**Question**: "What's the correct way to configure a MikroTik router in GNS3?"

**Expected**: Claude should provide MikroTik-specific commands and configuration steps from the skill.

### Test 3: Console Access
**Question**: "Help me connect to a device console in GNS3 using the MCP server"

**Expected**: Claude should reference the MCP tools (connect_console, send_console, etc.) from the skill.

### Test 4: Troubleshooting
**Question**: "My GNS3 node won't start. What should I check?"

**Expected**: Claude should provide troubleshooting steps from the skill's best practices section.

## Skill Content Preview

The GNS3 skill includes:

1. **Core Concepts**
   - GNS3 Projects and Nodes
   - Console Types (telnet, vnc, spice)
   - Node States (started, stopped, suspended)

2. **Common Workflows**
   - Starting and stopping labs
   - Accessing device consoles
   - Configuring network devices
   - Backing up configurations

3. **Device-Specific Guides**
   - MikroTik RouterOS
   - Arista vEOS
   - Cisco IOS/IOS-XE
   - Alpine Linux

4. **MCP Integration**
   - Available tools (12 total)
   - Tool usage examples
   - Best practices

## Verification Results

Test this manually by:
1. Opening Claude Code in any project
2. Asking one of the test questions above
3. Observing if Claude uses GNS3-specific knowledge
4. Checking if responses match skill content

**Test Date**: 2025-10-23
**Status**: Awaiting manual verification

## Notes

- Skills are loaded automatically by Claude Code
- No restart needed after installation
- Skill should work in all projects globally
- Can be overridden by project-specific skills in `.claude/skills/gns3/`
