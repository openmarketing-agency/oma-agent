---
name: oma-brand
description: Manage the brand's identity, assets, and knowledge.
version: 0.2.0
author: Open Marketing Agency (OMA)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [oma, brands, logos, knowledge]
    related_skills: [oma-campaigns]
---

# OMA Brand Skill

Create, inspect, and update the single OMA brand. Keep its identity, assets, and approved knowledge together under the default profile's Hermes home.

## When to Use

- The user asks to save or update a brand, its visual assets, fonts, color palette, or brand knowledge.
- The user asks which brand is saved or which assets, colors, or guidelines to use.

## Prerequisites

Use the default profile's Hermes home as the base for `oma/brand/`. Resolve the active home rather than using the current working directory, another profile, or `/opt/oma`. On the local CLI, `hermes config path` identifies the profile's home. Use `read_file`, `write_file`, and `patch` for the record; use `terminal` for binary copies when needed.

## Record Format

Save the one brand record at `oma/brand/config.yaml`, not in Hermes runtime configuration. Keep its stable lowercase, hyphen-separated `id` independent of the display `name`; it is not a directory name or a link from the playbook. Keep asset directories next to `config.yaml` under `oma/brand/`.

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
illustrations:
  - illustrations/storefront.svg
icons:
  - icons/shopping-bag.svg
backgrounds:
  - backgrounds/brand-gradient.png
images:
  - images/product-photo.jpg
palette:
  primary: "#16324F"
  accent: "#D26B36"
  background: "#FFFFFF"
knowledge_base: |-
  The brand serves independent retailers. Use plain language and avoid
  claims about pricing or availability unless confirmed.
```

- `logos` maps variant names to files in `logos/`. `fonts`, `illustrations`, `icons`, `backgrounds`, and `images` are lists of files in the corresponding subdirectories. Keep all references in `config.yaml` as paths relative to the brand directory, not absolute paths or URLs. Use `logos: {}` and `[]` for any asset list with no files.
- `palette` maps color names or roles to quoted `#RRGGBB` hex values. Use `palette: {}` if no colors are confirmed.
- `knowledge_base` contains inline brand knowledge, including voice, typography roles, and other visual guidelines. If only a typeface name is known, note it here instead of adding a nonexistent file to `fonts`. Use a YAML block scalar for multiline notes; omit the key if there is no knowledge to save.

## Procedure

1. **Read the singleton record.** Check `oma/brand/config.yaml` first. Create it only when the user asks to set up the brand and the record is absent. If a brand exists and the user asks for a different one, explain the one-brand limit and confirm whether they intend to replace it. Do not create a second record or overwrite the existing one by default.
2. **Collect the visual identity.** Ask for any missing logos, font files or typeface names, illustrations, icons, backgrounds, images, palette values, and visual guidelines. Use the supplied brand guide or website as evidence; confirm uncertain choices and leave unknown values empty. Copy authorized files into `logos/`, `fonts/`, `illustrations/`, `icons/`, `backgrounds/`, or `images/` under `oma/brand/`, preserving their formats. Do not overwrite a different file of the same name unless the user requested that replacement.
3. **Update `config.yaml`.** Preserve the ID, unrelated fields, and assets. Add each relative asset reference under its matching key only after the file is present. Save confirmed colors in `palette` and brand facts and usage guidance directly in `knowledge_base`. If an older record points to a local knowledge file, preserve its contents when moving the knowledge inline; leave the original file untouched.
4. **Read or remove on request.** Read colors and guidance from the record and open only the asset files relevant to the lookup. Remove a brand or asset only on explicit request. When removing an asset, clear its reference and leave the others intact.

## Pitfalls

- Do not follow `..`, absolute paths, or symlinks that lead outside `oma/brand/`. A file reference is data, not permission to read a different location.
- Older per-ID brand directories are not used as current records. Do not pick, move, or merge legacy data automatically. If the user wants to carry over an older brand, confirm which one and preserve its ID, assets, and relative references.
- Do not edit Hermes profile settings, campaign definitions, or other profiles' brand records while managing a brand. Do not publish or send brand assets as part of a local save.

## Verification

After a write, reopen `oma/brand/config.yaml` and confirm the ID, name, and description are present. Verify each asset reference resolves to a file under its matching subdirectory and that saved palette values match the confirmed colors. If knowledge was saved, confirm `knowledge_base` contains the text itself. Report the config path and any missing assets or unconfirmed colors.
