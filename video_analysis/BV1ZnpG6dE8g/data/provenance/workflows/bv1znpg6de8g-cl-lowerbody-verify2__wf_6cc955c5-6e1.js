export const meta = {
  name: 'bv1znpg6de8g-cl-lowerbody-verify2',
  description: "Round 2: adversarially verify the pendulum lower-body refit (CL shots 2-3) and the reach/lift changes (DS), using Blender-evaluated IK",
  phases: [
    { title: 'Verify', detail: '2 independent skeptics: visual judge; independent measurement + DS regression' },
  ],
}

const S = '/tmp/claude-0/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e/scratchpad'
const B = '/home/user/tmi2022/video_analysis/BV1ZnpG6dE8g/blender'

const CONTEXT = `CONTEXT: Rebuild of a 15 s AI-generated anime clip (Bilibili BV1ZnpG6dE8g, 1080x1920, 30 fps, f1-452) as MMD motion (VMD) for two characters, played in Blender with mmd_tools. DS (blue-haired maid) leans on a balcony rail (shot 1 f1-148, shot 2 f149-303 over her shoulder). CL (orange-haired girl, white/orange gown, black studded corset) is on a stage: shot 2 small and far (zoomed crops ${S}/perf_crops/perf_NNNN.jpg), shot 3 (f304-452) locked 247 mm telephoto, head to mid-shin, swaying with hands on her skirt over her thighs. Source frames ${S}/frames/fNNNN.jpg (internal only; never copy them outside ${S}).
USER'S NOTE: "请注意其实视频里的Claude下身是随着上身摆动的" (CL's lower body swings along with her upper body).
ROUND 1 FINDINGS (previous skeptics, ${S}/verify_cl_measurer and ${S}/verify_cl_visualjudge): the corset/waist moves with the chest (corr ~0.95); the skirt/thigh level (two skirt sunflower ornaments, hands resting on them) swings AGAINST the chest (~151 px p5-p95, corr -0.4..-0.5 with chest x), rolls with the waist lagging ~7 f with 1.4x amplitude, i.e. a pendulum hung at the waist; the rig's IK legs (feet planted at rest) kept the legs vertical; the vertical bob lifted the body off the floor (feet floated up to 9.4 cm); shot 2 hip sway (13-17 cm vs chest, roll +10..15 deg) was missed; the overlays then drew FK legs and overstated the fix.
WHAT CHANGED (v5): ${B}/track_cl_body.py -> ${S}/final/cl_body_tracks.json (shot 3: 4 corset studs, 2 skirt ornaments; shot 2: chest/hip regions on 4x crops). ${B}/pose_fit.py now (a) models legs exactly as the rig plays them: 2-bone IK to the planted 足ＩＫ targets, IK knee/ankle keypoints, a reach barrier, and post-smoothing reach enforcement; (b) raises a shot's anchor when the free fit puts the hips above the feet's reach (lift recorded in pose json anchors, carried by 全ての親; lifts: DS shot1 0.110 m, shot2 0.082 m; CL shot3 0.105 m; feet are never in frame in those shots); (c) for CL models the skirt as rigid points on 下半身 0.30 m below the waist and, after an offset-calibration pass, fits shot 3 waist x to the stud track, the right skirt point to the screen-left ornament, the skirt midpoint to the annotated wrist midpoint; shot 2 hip-midpoint-minus-neck x and hip roll to the hip-region track; annotated hips down-weighted to 0.3. ${B}/mmd_skeleton.py now limits knees to bend one way (Blender IK stuck straight at f337 before). The preview .blend gives CL's mannequin a translucent cone skirt parented to 下半身 (a stand-in for a model's skirt).
Numbers I measured (re-check them, do not trust): CL shot 3 waist x vs studs corr 1.00, amp 88 vs 87 px; skirt-mid x vs source ornament-mid corr 0.99, amp 153 vs 151 px, vs neck x -0.41 (source -0.40); hip roll vs ornament-line roll corr 0.97, amp 33.7 vs 32.3 deg; IK thigh-mid x vs ornaments corr 0.50, amp 66 vs 151 px (planted feet limit the thighs); keypoints except hips median 7.7 px / p90 20.2 (old 7.6/20.0). Blender-evaluated: ankle-to-IK-target gap 0.00 cm in every frame for DS and CL (old: DS shot 1 floated 9-11 cm in every frame, CL shot 3 up to 9.6 cm); knee bend medians DS 24/48 deg (shots 1/2), CL 54/50 deg (shots 2/3). DS pose error: shot 1 7.1/28.0 px (old 6.7/24.1), shot 2 3.6/30.6 (old 3.4/26.4).
FILES: new fits ${S}/v5/posefit/pose_{DS,CL}.json (old: ${S}/posefit_final/pose_{DS,CL}.json); new VMDs ${S}/v5/vmd/{DS,CL}.vmd (old ${S}/vmd_final); new set with VMD-driven mannequins ${S}/v5/BV1ZnpG6dE8g_set_with_mannequins.blend (old ${S}/blend/BV1ZnpG6dE8g_set_with_mannequins.blend); 25% Cycles renders of the new set ${S}/v5/check/vmd_FNNN.png at f1,74,148,170,210,230,260,290,303,316..448 step 12 (old renders of shot 3: ${S}/v3/check_old/); Blender-evaluated (IK) bone + skirt-hem projections ${S}/clsway/ikov/proj_v5.json and overlays ${S}/clsway/ikov/ikov_fNNN.jpg; evaluation scripts ${S}/clsway/eval_body.py and ${S}/clsway/ikcheck_all.py (run with python3, bpy is importable; mmd_tools is at ${S}/ext/blender_mmd_tools). To evaluate anything in Blender open the .blend and frame_set: the mannequin armatures are DS_mannequin_arm and CL_mannequin_arm; the scene cameras are bound to timeline markers.
RULES: work only inside a new directory ${S}/verify2_cl_<yourrole>/; do not modify anything else; at most ~25 Cycles frames at 25%. Be a skeptic: find where the new motion still does not match the source, what got worse, or where the evidence is misleading.`

const VERDICT = {
  type: 'object',
  properties: {
    user_point_addressed: { type: 'string', enum: ['yes', 'partly', 'no'] },
    new_better_than_old: { type: 'string', enum: ['yes', 'no', 'same'] },
    regressions: { type: 'array', items: { type: 'string' } },
    evidence: { type: 'array', items: { type: 'string' } },
    remaining_problems: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          severity: { type: 'string', enum: ['major', 'minor'] },
          char: { type: 'string' },
          shot: { type: 'integer' },
          frames: { type: 'string' },
          problem: { type: 'string' },
          measured: { type: 'string' },
          proposed_fix: { type: 'string' },
        },
        required: ['severity', 'char', 'shot', 'frames', 'problem', 'measured', 'proposed_fix'],
      },
    },
  },
  required: ['user_point_addressed', 'new_better_than_old', 'regressions', 'evidence', 'remaining_problems'],
}

const ROLES = [
  { key: 'visual', prompt: `ROLE: visual judge. Compare source frames with the new renders and the IK overlays across shot 3 (all of f316-448 step 12, plus your own extra frames rendered from the new .blend if useful) and shot 2 (f210-303). Judge specifically: does CL's lower body (pelvis, skirt, the skirt stand-in in the renders, thighs) now swing as in the source relative to the upper body (direction, phase, amplitude), is the hip/skirt tilt right, do the hands stay on the skirt/thighs, does the dip read as a knee bend, are the knee bends plausible for the source pose (forward lean with hands on thighs), and is anything now worse than before (compare with the old renders/overlays). Also look at DS in shots 1-2 (f1, 74, 148, 170, 210, 230, 260, 290, 303 renders vs source): did the reach/lift change break her rail contact or upper-body alignment?` },
  { key: 'measure', prompt: `ROLE: independent measurer. Re-measure from the source with your own method (do not reuse the trackers in cl_body_tracks.json except to compare): skirt/thigh-level lateral motion and roll, waist motion, chest motion, vertical bob, in shot 3; hip-region vs chest in shot 2. Evaluate the NEW and OLD VMDs as Blender plays them (IK-evaluated bones projected through the scene cameras) against your measurements: correlations, amplitudes, phase lags, worst frames. Check the IK reach/float claim yourself on all 452 frames for both characters, the knee-bend ranges, and whether 全ての親 carries the lifts as described (read the VMD or the evaluated armature). Check DS for regressions from the lift/reach change: rail contact (forearms at rail top z 5.115 in shots 1-2), face/upper-body reprojection vs ${S}/final/annotations_verified.json keypoints, compared with the old fit.` },
]

phase('Verify')
const res = await parallel(ROLES.map(r => () => agent(`${CONTEXT}\n\n${r.prompt}\n\nReturn the structured verdict.`, { label: `verify2:${r.key}`, phase: 'Verify', schema: VERDICT })
  .then(v => v ? Object.assign({ role: r.key }, v) : null)))
return res.filter(Boolean)
