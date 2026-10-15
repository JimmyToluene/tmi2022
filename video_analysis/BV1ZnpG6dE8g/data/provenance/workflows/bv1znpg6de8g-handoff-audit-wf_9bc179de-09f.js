export const meta = {
  name: 'bv1znpg6de8g-handoff-audit',
  description: 'Independently audit the handoff bundle: restore + path/command check, numeric accuracy, completeness and content safety',
  phases: [
    { title: 'Audit', detail: '3 independent auditors: restore/reproducibility, accuracy, completeness+safety' },
  ],
}

const S = '/tmp/claude-0/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e/scratchpad'
const H = `${S}/handoff`
const REPO = '/home/user/tmi2022'
const R = `${REPO}/video_analysis/BV1ZnpG6dE8g`
const T = '/root/.claude/projects/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e.jsonl'

const COMMON = `CONTEXT: A Claude Code session analysed a 15 s AI-generated anime clip (Bilibili BV1ZnpG6dE8g), rebuilt its set in Blender (without the two characters) and produced MMD motion files camera.vmd / DS.vmd / CL.vmd. GitHub push is blocked (403), so the user asked for a HANDOFF document plus a bundle of all files. The bundle is in ${H}:
- HANDOFF.md (Chinese handoff, also committed at ${R}/HANDOFF.md)
- tmi2022_branch_incremental.bundle (git bundle main..claude/video-character-analysis-v6hpo4)
- tmi2022_full.bundle (branch + main)
- BV1ZnpG6dE8g_workdir.tar.gz (filtered snapshot of the session scratchpad under workdir/, plus workdir/session_records/{workflows,journals})
- MANIFEST.json
The repo working copy is ${REPO} (branch claude/video-character-analysis-v6hpo4). The user-facing usage guide is ${R}/blender/README.md.
Python 3.13 with bpy 5.2.2 (import bpy works in plain python3), numpy, scipy are installed. mmd_tools source is at ${S}/ext/blender_mmd_tools (add it to sys.path, then import mmd_tools; mmd_tools.register(), wrap in try/except ValueError).
RULES: Do NOT modify anything under ${REPO} or ${H} or ${S} except inside your own new directory ${S}/audit_<yourname>/ (create it). Do not start renders or long jobs (> 3 minutes). A background render process (render_video.py) and another workflow are running - do not stop them. Report concrete findings only; each finding must say exactly where (file + section/line) and what the correct text/value should be.`

const FINDINGS = {
  type: 'object',
  properties: {
    checked: { type: 'array', items: { type: 'string' }, description: 'what you verified OK (short lines)' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['blocker', 'major', 'minor'] },
          where: { type: 'string' },
          problem: { type: 'string' },
          evidence: { type: 'string' },
          fix: { type: 'string', description: 'exact replacement text/value or exact action' },
        },
        required: ['severity', 'where', 'problem', 'evidence', 'fix'],
      },
    },
  },
  required: ['checked', 'findings'],
}

const AUDITORS = [
  {
    key: 'restore',
    prompt: `ROLE: restore-and-reproducibility auditor. Pretend you are the next person who only has the bundle.
1. In ${S}/audit_restore/: git bundle verify both bundles; clone the full bundle on branch claude/video-character-analysis-v6hpo4; separately simulate the incremental path: clone ${REPO} at main only (git clone --branch main --single-branch file://${REPO} base) then follow HANDOFF section 3's exact fetch command against the incremental bundle and confirm the branch head equals MANIFEST branch_head. Report any command in HANDOFF section 3 that fails as written.
2. Extract the workdir tarball. Check every file/dir path mentioned anywhere in HANDOFF.md exists either in the restored repo (relative to repo root or to video_analysis/BV1ZnpG6dE8g as the text implies) or in workdir/. List missing ones.
3. Compare every command line in HANDOFF section 7 (A and B) and README "重新生成" with the actual CLI of the scripts (read their Usage docstrings and argv parsing). Flag wrong argument order/count/flags and wrong file names (e.g. outputs written vs. later read).
4. Smoke tests on the restored repo: py_compile every .py under video_analysis/BV1ZnpG6dE8g; json.load every .json in data/, blender/, blender/vmd, blender/posefit; parse each .vmd header (30-byte magic 'Vocaloid Motion Data 0002', 20-byte model name, then bone keyframe count etc.) and report bone/morph/camera keyframe counts and frame ranges (expect frames 0..451); open both .blend files with bpy and check that objects named in README/HANDOFF exist (MMD_DS_Root, MMD_CL_Root, DS_mannequin, DS_mannequin_arm, DS_mannequin_mesh, CL_mannequin*, CAM_Shot1/2/3), that timeline markers Shot1/Shot2/Shot3 sit at frames 1/149/304 and are bound to the cameras, frame range 1-452, fps 30, and that no image other than the procedurally generated CitySkyline_img is packed or referenced.
5. Optionally (if quick): import DS.vmd into a fresh mmd_tools armature built by blender/mmd_skeleton.py build_mmd_model and confirm it animates (bone pose differs between frame 1 and 200).`,
  },
  {
    key: 'accuracy',
    prompt: `ROLE: numeric/factual accuracy auditor. Check EVERY number and factual claim in ${R}/HANDOFF.md and ${R}/blender/README.md against the data. Sources: ${R}/blender/vmd/camera_check.json (camera VMD round trip; frames with shot and max_err_px), ${R}/blender/posefit/pose_{DS,CL}.json (frames[].reproj_px dict per keypoint, shot), ${R}/blender/scene_spec.json (cameras keys lens_mm, locations, characters, markers, meta, rail_top_z), ${R}/data/*.json (meta, measured, analysis_model edges status counts, relations count, annotations_verified dup cadence), ${S}/consol/cheats.json, ${S}/final/status.json, ${R}/report.html (embedded data), the .blend files (open with bpy: object locations of MMD_DS_Root/MMD_CL_Root, camera lens per shot, markers, beat markers). Recompute: per-shot pose-fit median/p90 over all keypoint residuals; camera check median/p95/max overall and per shot; duplicate-frame cadence per shot (which f%5 residues duplicate the previous frame, per shot, from annotations_verified or ${S}/final/frame_signals.json dup_of_prev); unique frame count; beat spacing; shot boundaries; lens per shot; DS/CL anchor coordinates; DS facing; the integer-FOV distance compensation max (re-derive from lens values: ratio tan(fov/2)/tan(round(fov_deg)/2) with vertical FOV = 2*atan(18/lens)); morph names and values used in ${R}/blender/export_motion_vmd.py vs README text; bone names in ${R}/blender/mmd_skeleton.py vs README/HANDOFF; HAND_TIP_UNITS value; glass material values in scene_spec; the 40 deg rest-arm claim vs mmd_skeleton.py; where the 235 mm vs 247.4 mm shot-3 lens appears. Report every mismatch with the correct value.`,
  },
  {
    key: 'complete',
    prompt: `ROLE: completeness and content-safety critic.
PART A - completeness: The session transcript is ${T} (JSONL, ~24 MB; grep/python it, do not read it whole). Extract all genuine user messages (type=user with string content or text parts that are not tool_result and not system reminders / stop-hook feedback) and the assistant's final replies to them. Then compare with ${R}/HANDOFF.md and list anything a successor would need that is missing or wrong: open questions the user never answered (e.g. audio choice, .pmx models, repo name), commitments made to the user that are not yet fulfilled, constraints the user or assistant set (copyright handling of frames/audio, no PR unless asked, branch name, Chinese language), decisions and their reasons, known limitations, gotchas/errors encountered and their fixes, artifacts/links already sent to the user (report artifact URL, files sent), and anything in the HANDOFF that contradicts the transcript. Do not pad: only items that matter for continuing the work.
PART B - content safety of what is being handed over: list the contents of ${H}/BV1ZnpG6dE8g_workdir.tar.gz (tar tzf) and of the full git bundle's branch tree (clone it into ${S}/audit_complete/). Flag: any original video frames or images/crops derived from the source video (jpg/png/gif/mp4/webp anywhere, except the repo's figures/timeline_measured.png which is a plot), any audio, any credentials/cookies/tokens/API keys/session ids (grep for buvid, SESSDATA, bili_jct, token, Authorization, api_key, password, cookie, BEGIN PRIVATE KEY, ghp_, sk-), personal data, and unexpectedly large files (>5 MB). Policy for judging: public danmaku/comment text inside the private workdir tarball is acceptable; the repo's data/ must not contain a danmaku list; source frames and audio must not be anywhere; .blend files must not pack source frames. Report each violation with the exact path.`,
  },
]

phase('Audit')
const results = await parallel(AUDITORS.map(a => () =>
  agent(`${COMMON}\n\n${a.prompt}\n\nReturn checked (what passed) and findings.`, { label: `audit:${a.key}`, phase: 'Audit', schema: FINDINGS })
    .then(r => r ? Object.assign({ auditor: a.key }, r) : null)))
const got = results.filter(Boolean)
log(`auditors returned: ${got.map(r => r.auditor + ':' + r.findings.length).join(', ')}`)
return got
