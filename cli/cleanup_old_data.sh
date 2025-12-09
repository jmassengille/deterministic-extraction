#!/bin/bash
# Cleanup script for old test/debug data (>10 days old as of 2024-12-04)
# Run from project root: bash cli/cleanup_old_data.sh

echo "=== Cleaning up old data ==="

# Oct artifacts
rm -rf data/artifacts/20251021_* data/artifacts/20251022_* data/artifacts/20251027_*
echo "✓ Deleted Oct artifacts"

# Oct-Nov LLM responses
rm -rf data/llm_responses/20251021_* data/llm_responses/20251022_* data/llm_responses/20251027_*
rm -rf data/llm_responses/20251107_* data/llm_responses/20251108_* data/llm_responses/20251110_*
echo "✓ Deleted Oct-Nov LLM responses"

# Nov test extractions
rm -rf data/test_extraction/20251110_* data/test_extraction/20251111_*
echo "✓ Deleted Nov test extractions"

# Old output folders
rm -rf data/output/dd76f399-* data/output/f158d819-* data/output/2135a01c-*
echo "✓ Deleted old output folders"

# Stale session and empty dirs
rm -rf .claude/session/2025-12-02 data/temp bmad-output
echo "✓ Deleted stale session and empty dirs"

echo ""
echo "=== Cleanup complete ==="
du -sh data/
