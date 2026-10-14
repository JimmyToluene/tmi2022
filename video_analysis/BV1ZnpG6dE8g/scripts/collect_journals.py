"""Collect agent results from workflow journals into per-chunk files.

Usage: python collect_journals.py <out_dir> <journal.jsonl> [<journal.jsonl> ...]

Maps each agent's label (annotate:A-B, verify:A-B, context:web-research, ...) to its returned value and writes
chunk_KK.annot.json / chunk_KK.patches.json (KK = (A-1)//36 + 1) and context.md. When the same label ran in
more than one workflow, the first completed result wins.
"""
import json
import sys
from pathlib import Path


def main(out_dir, journals):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    seen = {}
    for j in journals:
        labels = {}
        for line in open(j, encoding="utf-8"):
            d = json.loads(line)
            if d.get("type") == "started":
                labels[d["agentId"]] = d.get("label", "")
            elif d.get("type") == "result" and d.get("agentId") in labels:
                lab = labels[d["agentId"]]
                if lab not in seen and d.get("result") is not None:
                    seen[lab] = d["result"]
    for lab, res in seen.items():
        kind, _, rng = lab.partition(":")
        if kind in ("annotate", "verify"):
            a = int(rng.split("-")[0])
            k = (a - 1) // 36 + 1
            name = f"chunk_{k:02d}.{'annot' if kind == 'annotate' else 'patches'}.json"
            json.dump(res, open(out / name, "w", encoding="utf-8"), ensure_ascii=False)
        elif lab == "context:web-research":
            open(out / "context.md", "w", encoding="utf-8").write(res if isinstance(res, str) else json.dumps(res, ensure_ascii=False))
        else:
            safe = lab.replace(":", "_").replace("/", "_")
            json.dump(res, open(out / f"{safe}.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("collected:", sorted(seen))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
