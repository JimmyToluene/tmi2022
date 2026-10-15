export const meta = {
  name: 'bv1znpg6de8g-cl-lowerbody-verify',
  description: "Adversarially verify that CL's refit lower body follows her upper body as in the source (visual judge + independent measurement, shots 2-3)",
  phases: [
    { title: 'Verify', detail: '2 independent skeptics: visual judge on overlays/renders; independent measurement incl. shot 2' },
  ],
}

const S = '/tmp/claude-0/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e/scratchpad'
const B = '/home/user/tmi2022/video_analysis/BV1ZnpG6dE8g/blender'

const CONTEXT = `CONTEXT: We rebuild a 15 s AI-generated anime clip (Bilibili BV1ZnpG6dE8g, 1080x1920, 30 fps, f1-452) and export MMD motion (VMD) for two characters. CL (orange-haired girl, white/orange gown with a black studded corset, ~1.60 m) dances on a small stage. Shot 2 (f149-303): she is small and far (8.9 m, 36 mm lens); zoomed 4x crops of her are in ${S}/perf_crops/perf_NNNN.jpg (f189-303). Shot 3 (f304-452): locked-off 247.4 mm telephoto, CL head-to-mid-shin, swaying her hips with hands on her skirt/thighs. Source frames: ${S}/frames/fNNNN.jpg (internal use only; never copy them anywhere outside ${S}).
THE USER SAID: "请注意其实视频里的Claude下身是随着上身摆动的" (in the video, CL's lower body actually swings along with her upper body).
WHAT WAS DONE: The old fit (${S}/posefit_final/pose_CL.json) used annotated hip keypoints that sit under the skirt; their image height wanders +-80 px relative to the rigid corset, and the old fit's waist moved only loosely with the upper body (corr of waist x with neck x 0.53). A tracker (${B}/track_cl_waist.py, output ${S}/final/cl_shot3_waist_track.json) aligns the corset and chest patches of every unique shot-3 frame to f304 with Euclidean ECC: corset x correlates 0.89 with chest x; corset tilt counter-rotates vs chest tilt (corr -0.54); corset y bobs ~150 px. The new fit (${S}/v3/posefit/pose_CL.json, code ${B}/pose_fit.py --waist) calibrates corset->waist offsets on the first pass (shot mean) and then fits the waist joint (上半身 head) and hip line (左足/右足 heads) to the corset track, down-weighting the annotated hips to 0.3. Result: waist follows corset (corr 0.99, 3.5 px rms), hip roll follows corset tilt (corr 0.99), waist-x/neck-x correlation 0.84 (source 0.89); all other keypoints unchanged (median 7.8 vs 7.6 px). Shot 2 was NOT changed (its CL fit has median 3.1 px).
Skeleton/FK/projection helpers: ${B}/pose_fit.py (Skeleton, project, SOLVE_BONES, waist_and_hip_roll), ${B}/pose_reference.py camera_at(spec, f), spec ${S}/final/scene_spec.json, annotations ${S}/final/annotations_verified.json. In the MMD rig, legs are IK-driven with feet planted (足ＩＫ at rest), so the legs follow センター/下半身 only by bending.
Evidence images: overlays of old (red) vs new (green) skeletons on 13 source frames ${S}/clsway/overlays/ov_fNNN.jpg (f304..448 every 12); renders of the mannequin with the old and new VMD at f304,322,...,448: ${S}/v3/check_old/vmd_FNNN.png and ${S}/v3/check/vmd_FNNN.png; combined sheet ${S}/clsway/old_new_sheet.jpg. A comparison script: python3 ${S}/clsway/compare.py ${B} ${S} <pose_CL.json...>.
RULES: work only inside a new directory ${S}/verify_cl_<yourrole>/; do not modify files elsewhere; no long renders (each Cycles frame at 25% takes ~4 s; at most 20 frames). Be a skeptic: your job is to find where the new motion still does NOT match the source, or where the fix is wrong, not to confirm it.`

const VERDICT = {
  type: 'object',
  properties: {
    user_point_addressed: { type: 'string', enum: ['yes', 'partly', 'no'] },
    new_better_than_old: { type: 'string', enum: ['yes', 'no', 'same'] },
    evidence: { type: 'array', items: { type: 'string' } },
    remaining_problems: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['major', 'minor'] },
          shot: { type: 'integer' },
          frames: { type: 'string' },
          problem: { type: 'string' },
          measured: { type: 'string', description: 'numbers backing it' },
          proposed_fix: { type: 'string', description: 'concrete change to the fit/rig/data' },
        },
        required: ['severity', 'shot', 'frames', 'problem', 'measured', 'proposed_fix'],
      },
    },
  },
  required: ['user_point_addressed', 'new_better_than_old', 'evidence', 'remaining_problems'],
}

const ROLES = [
  { key: 'visual', prompt: `ROLE: visual judge. Look at the source frames of shot 3 (sample at least 15 unique frames across f304-452, plus the 13 overlays and both render sets). For each sampled frame, judge where CL's waist/hips/thighs are in the source (the corset band, the belt line, where her hands press the skirt over her thighs, the skirt's centre line) relative to her chest/neck, and whether the OLD and NEW skeletons put the waist, hip line and thighs there. Specifically answer the user's point: does the lower body move together with the upper body in the new motion as it does in the source? Check the direction and phase of the lateral sway, the hip tilt vs shoulder tilt (same or opposite?), the vertical bob, and whether the thighs should lean with the sway (hands staying on the thighs) while the mannequin's legs stay vertical. Quantify with pixel measurements on the frames where you can (e.g. hand-to-thigh-line distance for old vs new).` },
  { key: 'measure', prompt: `ROLE: independent measurer. Re-measure CL's lower-body motion WITHOUT using the corset ECC track: e.g. dense optical flow (cv2.calcOpticalFlowFarneback) averaged over the waist band and over the upper skirt below the belt, the gold buckle/sash knot position by template matching, or the hands' positions (wrist keypoints) as a proxy for the thighs they rest on. Compare your lower-body track with (a) the upper-body motion (neck/chest), (b) the corset ECC track (is it biased or wrong anywhere, e.g. low ECC frames, rotation sign), (c) the NEW fit's projected waist and hip line, (d) the OLD fit. Report correlations, amplitudes, phase lags and any frames where the new fit departs. THEN do the same check for shot 2 (f189-303) using the 4x perf_crops and the annotations: does CL's lower body sway with her upper body there too, and does the (unchanged) shot-2 fit capture it? If not, propose a concrete fix.` },
]

phase('Verify')
const res = await parallel(ROLES.map(r => () => agent(`${CONTEXT}\n\n${r.prompt}\n\nReturn the structured verdict.`, { label: `verify:${r.key}`, phase: 'Verify', schema: VERDICT })
  .then(v => v ? Object.assign({ role: r.key }, v) : null)))
return res.filter(Boolean)
