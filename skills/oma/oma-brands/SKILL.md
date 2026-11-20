---
name: oma-brands
description: Manage user brands, logos, and brand knowledge.
version: 0.1.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, brands, logos, knowledge]
    related_skills: [oma-campaigns]
---

# OMA Brands Skill

Create, list, inspect, and update user brands using local files. Keep each brand's identity, assets, and approved knowledge together without mixing records across brands or profiles.

## When to Use

- The user asks to save or update a brand, its logos, its fonts, its color palette, or its brand knowledge.
- The user asks what brands are saved or which assets, colors, or guidelines to use for a named brand.

## Prerequisites

Use the active profile's Hermes home as the base for `oma/brands/`. Resolve the active home rather than using the current working directory, another profile, or `/opt/oma`. On the local CLI, `hermes config path` identifies the profile's home. Use `search_files`, `read_file`, `write_file`, and `patch` for records; use `terminal` for binary copies when needed.

## Record Format

Each `oma/brands/<brand_dir>/config.yaml` is a brand record, not Hermes runtime configuration. Use a stable lowercase, hyphen-separated ID for both `id` and `<brand_dir>`. `name` is the display name; changing it does not rename the directory or ID.

```yaml
id: example-brand
name: Example Brand
description: A short description of the brand.
logos:
  primary: logos/primary.svg
  icon: logos/icon.png
fonts:
  - fonts/BrandSans-Regular.woff2
  - fonts/BrandSans-Bold.woff2
palette:
  primary: "#16324F"
  accent: "#D26B36"
  background: "#FFFFFF"
knowledge_base: |-
  The brand serves independent retailers. Use plain language and avoid
  claims about pricing or availability unless confirmed.
```

- `logos` maps variant names to files in `<brand_dir>/logos/`. `fonts` is a list of files in `<brand_dir>/fonts/`. Store both as paths relative to the brand directory, not absolute paths or URLs. Use `logos: {}` and `fonts: []` if no files are available.
- `palette` maps color names or roles to quoted `#RRGGBB` hex values. Use `palette: {}` if no colors are confirmed.
- `knowledge_base` contains inline brand knowledge, including voice, typography roles, and other visual guidelines. If only a typeface name is known, note it here instead of adding a nonexistent file to `fonts`. Use a YAML block scalar for multiline notes; omit the key if there is no knowledge to save.

## Procedure

1. **Identify the brand.** List only records in the active profile's `oma/brands/` directory. Match the exact ID first, then an unambiguous name. Ask which brand the user means if multiple records match. For a new brand, check that the proposed ID and directory are unused before writing.
2. **Collect the visual identity.** When forming a brand, ask for logos, font files or typeface names, palette values, and any visual guidelines not already provided. Use the supplied brand guide or website as evidence; confirm uncertain choices and leave unknown values empty. Copy supplied logo files into `logos/` and font files the user is allowed to share into `fonts/`, preserving file formats. Do not overwrite a different file of the same name unless the user requested that replacement.
3. **Update `config.yaml`.** Preserve the ID, unrelated fields, and assets. Add logo and font references only after the files are present. Save confirmed colors in `palette` and brand facts and usage guidance directly in `knowledge_base`. If an older record points to a local knowledge file, preserve its contents when moving the knowledge inline; leave the original file untouched.
4. **Read or remove on request.** Read colors and guidance from the record and open only the asset files relevant to the lookup. Remove a brand or asset only on explicit request. When removing an asset, clear its reference and leave the others intact.

## Pitfalls

- Do not follow `..`, absolute paths, or symlinks that lead outside the selected brand directory. A file reference is data, not permission to read a different location.
- Do not edit Hermes profile settings, campaign definitions, or other profiles' brand records while managing a brand. Do not publish or send brand assets as part of a local save.

## Verification

After a write, reopen the record and confirm the ID matches its directory and the description and name are present. Verify that logo and font references resolve to files in their respective directories and that saved palette values match the confirmed colors. If knowledge was saved, confirm `knowledge_base` contains the text itself. Report the config path and any missing assets or unconfirmed colors.
