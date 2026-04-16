---
name: web-artifacts-builder
description: "Creates elaborate, multi-component claude.ai HTML artifacts using React 18, TypeScript, Tailwind CSS, and shadcn/ui. Initializes projects, builds interactive dashboards, multi-page apps, and tabbed interfaces, then bundles everything into a single shareable HTML file. Use for complex artifacts requiring state management, routing, or shadcn/ui components - not for simple single-file HTML/JSX artifacts."
license: Complete terms in LICENSE.txt
---

# Web Artifacts Builder

Build powerful frontend claude.ai artifacts by following these steps:

1. Initialize the frontend repo using `scripts/init-artifact.sh`
2. Develop your artifact by editing the generated code
3. Bundle all code into a single HTML file using `scripts/bundle-artifact.sh`
4. Display artifact to user
5. (Optional) Test the artifact

**Stack**: React 18 + TypeScript + Vite + Parcel (bundling) + Tailwind CSS + shadcn/ui

## Design & Style Guidelines

VERY IMPORTANT: To avoid what is often referred to as "AI slop", avoid using excessive centered layouts, purple gradients, uniform rounded corners, and Inter font.

## Quick Start

### Step 1: Initialize Project

```bash
bash scripts/init-artifact.sh <project-name>
cd <project-name>
```

This creates a fully configured project with React + TypeScript (via Vite), Tailwind CSS with shadcn/ui theming, path aliases (`@/`), 40+ shadcn/ui components pre-installed, and Parcel configured for bundling.

### Step 2: Develop Your Artifact

Edit the generated files to build your artifact:

- **`src/App.tsx`**: Main application component — start here for layout and routing
- **`src/components/`**: Add custom components; import shadcn/ui components from `@/components/ui/`
- **`src/lib/utils.ts`**: Utility functions including the `cn()` class merger
- **`index.html`**: Entry point (must remain in root for bundling)

Common patterns:
- **Add a page**: Create a component in `src/components/`, import and render in `App.tsx`
- **Use shadcn/ui**: `import { Button } from "@/components/ui/button"`
- **Add state**: Use React hooks (`useState`, `useReducer`) in your components
- **Add routing**: Install and configure `react-router-dom` for multi-page apps

### Step 3: Bundle to Single HTML File

```bash
bash scripts/bundle-artifact.sh
```

This creates `bundle.html` — a self-contained artifact with all JavaScript, CSS, and dependencies inlined. Your project must have an `index.html` in the root directory.

**If bundling fails**: Check that all imports resolve correctly and that `index.html` exists in the project root.

### Step 4: Share Artifact with User

Share the bundled HTML file in conversation with the user so they can view it as an artifact.

### Step 5: Testing (Optional)

Only perform if necessary or requested. Use available tools (Playwright, Puppeteer, or other Skills) to verify the artifact renders correctly. Avoid testing upfront as it adds latency — test after presenting the artifact if issues arise.

## Reference

- **shadcn/ui components**: https://ui.shadcn.com/docs/components
