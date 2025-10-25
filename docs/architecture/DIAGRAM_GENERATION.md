# Architecture Diagram Generation Guide

**Last Updated**: 2025-10-25

## Overview

This project uses **PlantUML** for architecture diagrams following the **C4 Model** approach. All diagrams are defined as code (.puml files) and can be regenerated at any time.

## Quick Start

### Option 1: Online Viewer (Fastest)

1. Open [PlantUML Online Server](https://www.plantuml.com/plantuml/uml/)
2. Copy content from any .puml file (e.g., `01-c4-context-diagram.puml`)
3. Paste into editor
4. View/download PNG or SVG

### Option 2: Local Generation (Recommended for CI/CD)

#### Prerequisites

```bash
# Install Java (required for PlantUML)
java -version  # Should show Java 8 or higher

# Install PlantUML globally
npm install -g node-plantuml

# Or use plantuml.jar directly
curl -L https://github.com/plantuml/plantuml/releases/download/v1.2024.8/plantuml-1.2024.8.jar -o ~/plantuml.jar
```

#### Generate All Diagrams

```bash
# Navigate to project root
cd "C:\HOME\1. Scripts\008. GNS3 MCP"

# Generate all diagrams as PNG
plantuml docs/architecture/*.puml

# Generate as SVG (vector graphics)
plantuml -tsvg docs/architecture/*.puml

# Using plantuml.jar directly
java -jar ~/plantuml.jar docs/architecture/*.puml
```

**Output**: PNG files created alongside .puml files (e.g., `01-c4-context-diagram.png`)

#### Generate Single Diagram

```bash
# Just the context diagram
plantuml docs/architecture/01-c4-context-diagram.puml

# Or with Java
java -jar ~/plantuml.jar docs/architecture/01-c4-context-diagram.puml
```

### Option 3: VS Code Extension (Best for Development)

1. **Install Extension**:
   - Search for "PlantUML" by jebbs
   - Install extension

2. **Configure Settings** (Optional):
   ```json
   {
     "plantuml.server": "https://www.plantuml.com/plantuml",
     "plantuml.exportFormat": "png",
     "plantuml.exportOutDir": "."
   }
   ```

3. **Preview Diagram**:
   - Open .puml file in VS Code
   - Press `Alt+D` or `Ctrl+Shift+V` to preview
   - Right-click → "Export Current Diagram" to save

### Option 4: Python diagrams Library

For creating diagrams with Python (used for infrastructure diagrams):

```bash
# Install Python diagrams library
pip install diagrams

# Create diagram
python docs/architecture/create_deployment_diagram.py
```

## C4 Model Diagrams

### Current Diagrams

1. **[01-c4-context-diagram.puml](01-c4-context-diagram.puml)** - System Context
   - Shows: External users, Claude AI, GNS3 Server, Network Devices
   - Purpose: Understand system boundaries and external integrations
   - Audience: All stakeholders

2. **[02-c4-container-diagram.puml](02-c4-container-diagram.puml)** - Container Architecture
   - Shows: MCP Framework, Tool Modules, GNS3 Client, Console Manager
   - Purpose: Understand internal component breakdown
   - Audience: Developers, architects

3. **[03-c4-component-diagram.puml](03-c4-component-diagram.puml)** - Component Details
   - Shows: 6 tool category modules, integration layer, data models
   - Purpose: Deep dive into tool organization (v0.11.0 refactor)
   - Audience: Developers

4. **[04-deployment-diagram.puml](04-deployment-diagram.puml)** - Deployment View
   - Shows: Claude Desktop/Code, Python process, GNS3 host, network devices
   - Purpose: Understand deployment topology and network flows
   - Audience: DevOps, system administrators

### Regenerating After Changes

**When to regenerate**:
- After modifying .puml files
- Before documentation reviews
- Before releases
- When creating pull requests with architecture changes

**Automated Regeneration** (Git pre-commit hook):
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
if git diff --cached --name-only | grep -q "docs/architecture/.*\.puml"; then
    echo "Regenerating architecture diagrams..."
    plantuml docs/architecture/*.puml
    git add docs/architecture/*.png
fi
```

## PlantUML Syntax Guide

### C4 Model Macros

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml

' Define people
Person(user, "User", "Network engineer")

' Define systems
System(system, "GNS3 MCP Server", "MCP-based automation server")
System_Ext(external, "GNS3 Server", "External system")

' Define relationships
Rel(user, system, "Uses", "Natural language")
Rel(system, external, "Calls API", "HTTP/REST")

@enduml
```

### Container Diagram

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Container.puml

System_Boundary(boundary, "System Name") {
    Container(app, "Application", "Python", "Description")
    ContainerDb(db, "Database", "PostgreSQL", "Description")
}

Rel(app, db, "Reads/Writes", "SQL")

@enduml
```

### Component Diagram

```plantuml
@startuml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml

Component(comp1, "Component 1", "Python Module", "Description")
Component(comp2, "Component 2", "Python Module", "Description")

Rel(comp1, comp2, "Calls", "Function call")

@enduml
```

## Best Practices

### Diagram Organization

1. **One diagram per file**: Each .puml file = one diagram
2. **Descriptive names**: Use numbered prefixes (01-, 02-) for ordering
3. **Consistent styling**: Use C4 macros for consistent look
4. **Version in filename**: Add version if diagram is version-specific

### Diagram Content

1. **Focus on purpose**: Each diagram should answer specific questions
2. **Appropriate level**: Match detail level to audience
3. **Clear labels**: All arrows should have descriptive labels
4. **Legend inclusion**: Use `SHOW_LEGEND()` for clarity

### Editing Workflow

```bash
# 1. Edit .puml file
code docs/architecture/02-c4-container-diagram.puml

# 2. Preview in VS Code (Alt+D)

# 3. Generate PNG for review
plantuml docs/architecture/02-c4-container-diagram.puml

# 4. Commit both .puml and .png
git add docs/architecture/02-c4-container-diagram.*
git commit -m "docs: update container diagram for v0.12.0"
```

## Troubleshooting

### PlantUML Fails to Generate

**Issue**: `Error: Could not find or load main class net.sourceforge.plantuml.Run`

**Solution**:
```bash
# Verify Java is installed
java -version

# Re-download plantuml.jar
curl -L https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar -o ~/plantuml.jar

# Test
java -jar ~/plantuml.jar -version
```

### Diagram Too Large

**Issue**: Generated PNG is too large to view comfortably

**Solution**:
```plantuml
@startuml
' Add at top of .puml file
scale 0.7
' or
skinparam defaultTextAlignment center
skinparam maxMessageSize 100
@enduml
```

### Missing C4 Macros

**Issue**: `!include` fails to fetch C4 macros

**Solution**:
```bash
# Option 1: Use local copy
git clone https://github.com/plantuml-stdlib/C4-PlantUML.git ~/C4-PlantUML

# Update .puml files
!include ~/C4-PlantUML/C4_Context.puml

# Option 2: Use official CDN
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Generate Architecture Diagrams

on:
  push:
    paths:
      - 'docs/architecture/*.puml'

jobs:
  generate-diagrams:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Java
        uses: actions/setup-java@v3
        with:
          java-version: '11'

      - name: Download PlantUML
        run: |
          curl -L https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar -o plantuml.jar

      - name: Generate Diagrams
        run: |
          java -jar plantuml.jar docs/architecture/*.puml

      - name: Commit Generated Files
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add docs/architecture/*.png
          git commit -m "docs: regenerate architecture diagrams [skip ci]" || echo "No changes"
          git push
```

## Extending Diagrams

### Adding New Diagram

1. **Create .puml file**:
   ```bash
   code docs/architecture/08-security-architecture.puml
   ```

2. **Use appropriate template**:
   ```plantuml
   @startuml
   !include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml

   title Security Architecture for GNS3 MCP Server

   ' Add diagram content here

   SHOW_LEGEND()
   @enduml
   ```

3. **Generate and review**:
   ```bash
   plantuml docs/architecture/08-security-architecture.puml
   ```

4. **Update README**:
   ```markdown
   - **[08-security-architecture.puml](08-security-architecture.puml)** - Security layers and trust boundaries
   ```

### Custom Styling

Create `C4_custom.puml` for project-specific styles:

```plantuml
' C4_custom.puml
!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Context.puml

' Custom colors
!define TECH_COLOR #0066CC
!define DATA_COLOR #009933

' Custom macros
!unquoted procedure CustomSystem($alias, $label, $descr)
    System($alias, $label, $descr) #TECH_COLOR
!endprocedure
```

Use in diagrams:
```plantuml
!include docs/architecture/C4_custom.puml

CustomSystem(mcp, "GNS3 MCP", "Custom styled system")
```

## Resources

- **PlantUML Official**: https://plantuml.com/
- **C4 Model**: https://c4model.com/
- **C4-PlantUML**: https://github.com/plantuml-stdlib/C4-PlantUML
- **PlantUML Cheat Sheet**: https://plantuml.com/guide
- **VS Code Extension**: https://marketplace.visualstudio.com/items?itemName=jebbs.plantuml

## Questions?

- **Diagram syntax**: See PlantUML documentation
- **C4 Model questions**: See c4model.com
- **Project-specific**: File issue with `documentation` label

---

**Last Updated**: 2025-10-25
**Maintained By**: Architecture Team
