---
name: atlas-cms
description: Use the Atlas CMS to manage posts, collections, résumé records, notes, images and publication, or to sync and render content.
---

# Atlas CMS

Run `uv run at cms ...` from the repository root. Use `new`, `ls`, `show` or
`cms id` for exact IDs because collisions can produce suffixes. Use record
revisions from `show` for `--expected-revision`. Each post must own a distinct
notebook source path. Repair ownership conflicts before sync or removal.
See [workspace and record IDs](../../../README.md#workspace-and-record-ids).

- Use CMS commands for IDs, managed metadata, publication, membership, order,
  notes, to-dos and destructive operations. Publishing sets build eligibility.
  Deployment is separate. Publishing a collection leaves its members'
  publication states as they were.
- Edit the authored post YAML directly or through CMS. Keep only `title`,
  `short_description` and `tags` in `content/posts/<id>.yaml`. Collection
  introductions live in `content/collections/<id>.md`, with title, short
  description and optional cover caption in the matching YAML. Edit authored
  collection and résumé text directly or through CMS. Keep résumé section and
  position in backend records. See [posts](../../../README.md#posts),
  [collections](../../../README.md#collections) and [résumé](../../../README.md#résumé).
- Supply `--file` for noninteractive `collection open`, `resume open` and
  `notes` and field flags for metadata edits. Keep private plans in
  [CMS notes or to-dos](../../../README.md#writing-notes-and-storage).
- Import and replace figures, thumbnails and covers with the
  [image commands](../../../README.md#images). Keep managed copies that may
  still have references. Preserve the existing caption, alt text, label and
  sizing when replacing figures. Omit `--caption` and `--alt` with `--replace`.
- Use the [CMS preview or build](../../../README.md#preview-and-build) so sync
  runs first and Quarto receives `--no-execute`. A running `make preview`
  watches saved edits. Use `uv run at cms sync --preview` for projection only
  or `uv run at cms build --preview` for a one-time render. Creation already
  refreshes the draft preview. Keep résumé sync enabled in preview and public
  mode so edits reach the page and PDF.
- Review UTC public modification dates updated by sync or build alongside the
  source changes. Report relevant draft blockers from `cms check` and leave
  unrelated drafts alone. Keep related authored content, managed images,
  backend records and deliberate template changes together when committing.
