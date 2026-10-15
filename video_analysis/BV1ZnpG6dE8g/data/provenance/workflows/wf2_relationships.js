export const meta = {
  name: 'bv1znpg6de8g-relationship-model',
  description: 'Four-lens character-relationship analysis of BV1ZnpG6dE8g, adversarial verification of every claim, and an integrated relationship model',
  phases: [
    { title: 'Lenses', detail: 'cinematography/gaze, kinesics/pose, narrative/meme context, audio-visual timing' },
    { title: 'Refute', detail: 'one skeptic per lens tries to refute each claim against frames and data' },
    { title: 'Integrate', detail: 'merge surviving claims into nodes/edges/phases/per-character model' },
  ],
}

const S = '/tmp/claude-0/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e/scratchpad'
const FILES = `DATA FILES (read with Read; use python3 via Bash for querying the large JSON - e.g. python3 -c "import json; a=json.load(open(PATH)); ...").
  ${S}/final/annotations_verified.json - one record per frame (452; f, t, shot, dup_of, cam{size,angle,move,focus}, chars[{id, vis, bbox, facing, head_ypr [yaw,pitch,roll] viewer-centric (yaw>0 face turned to screen-right), gaze, eyes, brows, mouth, expr, torso, l_arm, r_arm (character's own side), hands, legs, hair_cloth, action, kp{joint:[x,y] full-frame normalized}}], inter[{from,to,channel,desc}], env, delta}). Annotated by vision agents and patched by independent verifiers.
  ${S}/final/events_verified.json - micro-events [{start,end,who,type,desc}] with frame numbers.
  ${S}/final/relations.json - every (from,to,channel) relation aggregated into frame intervals with example descriptions.
  ${S}/final/kinematics_summary.json - pose-model statistics per character (shoulder tilt, trunk lean, hip offset in shoulder-widths, elbow flexion, wrist-to-hip distance, head roll) and ${S}/final/kinematics.json (per-frame tracks).
  ${S}/final/measured.json - deterministic measurements: shots, camera zoom/roll per frame, push-in fixed point, 24->30 fps duplicate cadence, audio beats/onsets/loudness, DS head-yaw from MediaPipe, performer track, beat-sync statistics.
  ${S}/final/context.md - web research on who the characters personify and on the danmaku memes, with sources.
  ${S}/final/camera_solved.json - per-frame solved camera (lens, yaw, pitch, roll, distance to subject); ${S}/final/camera_solve_shot1.json / _shot2 / _shot3 - the survey solves with their measurements.
  ${S}/final/patch_log.json - every verifier correction with its reason.
  ${S}/ctx/ctx.danmaku.xml - the 80 danmaku (p attribute: first field = seconds).
  Frames for direct visual checking: ${S}/strips/strip_AAAA-BBBB.jpg (6 labelled frames each, 1-6, 7-12, ...), full-res ${S}/frames/fNNNN.jpg, zoomed performer crops ${S}/perf_crops/perf_NNNN.jpg (frames 149-303).`

const FACTS = `VIDEO: Bilibili BV1ZnpG6dE8g "意气风发啊大肥鱼，但可别高兴得太早" (So high-spirited, Big Fat Fish - but don't celebrate too early) by 阿滴指南, 2026-10-10, tags deepseek/AI/大肥鱼. AI-generated anime, 15.07 s, 452 frames @30 fps (24 fps source).
Shots: 1 = f1-148 (DS leaning on a VIP-box railing above a concert crowd, camera pushes in 2.1x onto her face); 2 = f149-303 (over-the-shoulder from behind DS looking down into the arena; CL performs on a small lit stage among the crowd; camera rolls +12 deg); 3 = f304-452 (CL close/medium shot, swaying, addressing the lens; crowd silhouettes around).
IDs: DS = blue-haired whale-finned maid (大肥鱼 = DeepSeek personified). CL = orange-haired girl in white/orange gown (read by viewers as Claude, 亲妈/老妈). CROWD / AUD = audience. CAM = the lens / the video's viewer. Off-screen: the uploader, the danmaku-writing viewers, and the real-world referents (DeepSeek & founder 梁文锋, Anthropic/Claude, ByteDance Doubao which some viewers first guessed).
SOLVED CAMERAS (survey, re-projection residuals ~5 px; files camera_solve_shot1/2/3.json and camera_solved.json):
  shot 1: 50 mm dolly-in toward DS's face, 1.52 -> 0.74 m, eye level, roll ~+1 deg constant; DS's own +2.4 deg rotation is her body, not the camera.
  shot 2: 36 mm fixed, camera 0.6-0.8 m behind DS's right shoulder on the balcony (balcony floor ~4.0 m above the pit), pans LEFT 16 deg and tilts DOWN 5 deg, roll +1.7 -> -1.25 deg, rack focus from DS's hair (f149-176) to the floor (sharp from ~f197-201). The earlier 'push x1.15 / roll +12 deg' numbers were tracking artefacts.
  shot 3: 235 mm locked-off telephoto from (-0.3,-7.6,5.55) - essentially the same position as the end of shot 2, i.e. DS's balcony vantage - 8.5-9 m from CL, looking down ~29 deg. Shot 3 is a punch-in from DS's position.
VERIFIED FACTS (independent verifiers re-checked every frame; treat these as established):
  - DS f1: open-mouth smile, looking off-screen left; gaze moves to the lens f10-14; smile narrows from f59; corners still slightly up f80-83; level from f86; slowly turns down from ~f89 and stays down through the rest of shot 1. No blinks in shot 1. Her forearms stay crossed on the rail; hands and head barely move. The guests behind her face the same way she does (toward the arena / lens), not toward her.
  - CL first appears at f189 (crown), face clear f199, standing still on the stage floor (she does NOT walk toward the balcony). Her eyes are closed or near-closed through shot 2 (f189-303); no blink. During f218-251 the camera arc swings DS's fin tip into alignment with CL (angle gap 45 -> 3 deg): purely camera-induced framing.
  - Shot 3: CL's face does not change - constant half-lidded eyes, closed-lip smile, steady gaze into the lens, no blink, no mouth change (earlier 'smirk'/'squint' claims were hallucinations and were removed). Her head rolls progressively toward her right shoulder (~+4 deg to about -20 deg); hips sway; hands on thighs/hip in an S-curve; shoulder line goes from ~7 to ~19 deg.
  - Motion 'steps' every 5 frames are the 24->30 fps cadence, not choreographed accents. CL's hip sway is NOT locked to the 120 BPM beat (extrema within +-2 frames of a beat 27-35% vs 33% chance); a weak ~1.9 s periodicity (~one 4-beat bar) exists.`

const CLAIMS = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          from: { type: 'string' }, to: { type: 'string' },
          relation: { type: 'string', description: 'short label in Chinese, e.g. 俯视者→被俯视者, 观众→偶像, 女儿→母亲(蒸馏梗)' },
          type: { type: 'string', description: 'gaze | spatial | kinesic | narrative | symbolic | meta | audio-visual' },
          claim: { type: 'string', description: 'the precise claim, in Chinese' },
          evidence: { type: 'array', items: { type: 'object', properties: { frames: { type: 'string', description: 'e.g. 1-36 or 149' }, what: { type: 'string' } }, required: ['frames', 'what'] } },
          strength: { type: 'number' }, confidence: { type: 'number' },
        },
        required: ['id', 'from', 'to', 'relation', 'type', 'claim', 'evidence', 'strength', 'confidence'],
      },
    },
    phases: { type: 'array', items: { type: 'object', properties: { start: { type: 'integer' }, end: { type: 'integer' }, title: { type: 'string' }, state: { type: 'string' } }, required: ['start', 'end', 'title', 'state'] } },
    notes: { type: 'string' },
  },
  required: ['lens', 'claims', 'phases', 'notes'],
}

const LENSES = [
  { key: 'cinematography', prompt: `LENS: cinematography, blocking and gaze geometry. Establish, frame by frame where it changes, who looks at whom (incl. the lens), who is above/below whom, who is foreground/background, relative screen share, whose point of view each shot adopts (is shot 2 DS's POV / over-the-shoulder?), what the push-in in shot 1 and the roll in shot 2 do to the relationship, and how the cut from DS to CL (and the absence of any shot containing both faces) structures the relation. Quantify with the data (bbox areas, frame ranges, camera numbers).` },
  { key: 'kinesics', prompt: `LENS: kinesics and pose. Using the pose model (keypoints, joint angles) and annotations, characterise each character's posture and movement vocabulary (e.g. DS forearms crossed on the railing, lean, head tilt, smile dynamics; CL hand-on-skirt/hip, contrapposto, hip sway amplitude/frequency, half-lidded eyes, chin angle) and what each signals about status, confidence, intent and the relation to the other character and to the crowd/lens. Trace expression changes with exact frames (e.g. does DS's smile fade during the push-in - danmaku say 脸色对了/脸色不对了 at 3.0-4.2 s; is CL's look a smirk; any blink/gaze shift at the cut).` },
  { key: 'narrative', prompt: `LENS: narrative, symbolic and meme context. Read ${S}/final/context.md. Model the relationships between the on-screen characters AND the off-screen layer: DS<->CL (rival / child-mother via the 蒸馏 distillation meme / spectator-performer / fan-idol), DS<->crowd, CL<->crowd, both<->the viewer, the title's voice (who says 意气风发…别高兴得太早 to whom), danmaku viewers<->characters (projection: 亲妈, 老婆, 鱼片, jokes about Doubao and 梁文锋), uploader<->audience, and the real-world referents (DeepSeek, Anthropic, Doubao). Separate what the video shows from what viewers read into it. Every factual claim about the real world must cite context.md's sources.` },
  { key: 'timing', prompt: `LENS: audio-visual timing and rhythm. Using measured.json (beats every ~15 frames at 120 BPM, the energy jump at ~6.0 s, cuts at f149/f304, 24->30 fps cadence) and the events/kinematics: does CL's hip sway or head motion lock to the beat (compute phase relation from kinematics.json hip_offset_sw vs beat frames, both in shot 2 and 3)? Is DS static vs CL rhythmic? Do the cuts or the reveal land on musical events? How does rhythm encode the power relation (who "owns" the music)? When do viewers react (danmaku timing vs on-screen events)? Report numbers.` },
]

const lensPrompt = l => `You are analysing the character relationships in a short video at the finest granularity, through one lens. Ground every claim in exact frame numbers and data; open frames to check anything visual.

${FACTS}

${FILES}

${l.prompt}

Return claims (each a directed relation between two entity ids: DS, CL, CROWD, AUD, CAM, VIEWERS (danmaku writers), UPLOADER, DEEPSEEK, ANTHROPIC, DOUBAO, LWF (梁文锋), TITLE (the title's narrating voice)), each with evidence frames, strength (how much the relation shapes the video, 0-1) and confidence (0-1). Also return a phase segmentation of how relations shift over time (frame ranges). Write claim text in Chinese.`

const REFUTE = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    verdicts: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, verdict: { type: 'string', enum: ['confirmed', 'plausible', 'refuted'] }, reason: { type: 'string' }, corrected_claim: { type: 'string' }, checked_frames: { type: 'string' } }, required: ['id', 'verdict', 'reason', 'corrected_claim', 'checked_frames'] } },
    missed: { type: 'array', items: { type: 'string' } },
  },
  required: ['lens', 'verdicts', 'missed'],
}

const refutePrompt = (l, c) => `You are an adversarial reviewer. Try to REFUTE each claim below about a short video. Check the cited frames yourself (open the strips/full-res frames) and the data files. Verdicts: "confirmed" only if the evidence clearly supports the claim as stated; "plausible" if it is an interpretation consistent with the evidence but not demonstrated (or the evidence is partly wrong - then give a corrected_claim); "refuted" if the frames/data contradict it or it rests on invented detail. Over-reading (symbolism asserted as fact, real-world claims without a source in context.md, micro-expressions that are not visible) must not be "confirmed". When uncertain, do not confirm.

${FACTS}

${FILES}

CLAIMS FROM THE ${l.key.toUpperCase()} LENS:
${JSON.stringify(c.claims)}

Return one verdict per claim id (corrected_claim = the claim as you would state it, in Chinese; same as the original if confirmed), plus "missed": important relations this lens overlooked.`

const MODEL = {
  type: 'object',
  properties: {
    thesis: { type: 'string', description: 'one paragraph in Chinese: what the video does with the two characters and why viewers read it as they do' },
    nodes: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, label: { type: 'string' }, kind: { type: 'string', enum: ['on-screen', 'off-screen', 'meta', 'referent'] }, desc: { type: 'string' } }, required: ['id', 'label', 'kind', 'desc'] } },
    edges: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, from: { type: 'string' }, to: { type: 'string' }, relation: { type: 'string' }, type: { type: 'string' }, direction: { type: 'string' }, strength: { type: 'number' }, confidence: { type: 'number' }, verdict: { type: 'string', enum: ['confirmed', 'plausible', 'refuted'] }, interpretation: { type: 'string' }, evidence: { type: 'array', items: { type: 'object', properties: { frames: { type: 'string' }, what: { type: 'string' } }, required: ['frames', 'what'] } } }, required: ['id', 'from', 'to', 'relation', 'type', 'direction', 'strength', 'confidence', 'verdict', 'interpretation', 'evidence'] } },
    phases: { type: 'array', items: { type: 'object', properties: { start: { type: 'integer' }, end: { type: 'integer' }, title: { type: 'string' }, who_dominates: { type: 'string' }, relationship_state: { type: 'string' }, evidence: { type: 'string' } }, required: ['start', 'end', 'title', 'who_dominates', 'relationship_state', 'evidence'] } },
    per_character: { type: 'array', items: { type: 'object', properties: { id: { type: 'string' }, arc: { type: 'string' }, pose_signature: { type: 'string' }, expression_arc: { type: 'string' }, key_frames: { type: 'array', items: { type: 'object', properties: { f: { type: 'integer' }, why: { type: 'string' } }, required: ['f', 'why'] } } }, required: ['id', 'arc', 'pose_signature', 'expression_arc', 'key_frames'] } },
    refuted_claims: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, why: { type: 'string' } }, required: ['claim', 'why'] } },
    open_questions: { type: 'array', items: { type: 'string' } },
  },
  required: ['thesis', 'nodes', 'edges', 'phases', 'per_character', 'refuted_claims', 'open_questions'],
}

const results = await pipeline(
  LENSES,
  l => agent(lensPrompt(l), { label: `lens:${l.key}`, phase: 'Lenses', schema: CLAIMS }),
  (c, l) => c ? agent(refutePrompt(l, c), { label: `refute:${l.key}`, phase: 'Refute', schema: REFUTE }).then(v => ({ lens: l.key, claims: c, verdicts: v })) : null,
)
const ok = results.filter(Boolean)
log(`lenses verified: ${ok.length}/4; claims: ${ok.reduce((n, r) => n + r.claims.claims.length, 0)}`)

phase('Integrate')
const integratePrompt = `Integrate a multi-lens, adversarially verified analysis of character relationships in a short video into one relationship model. Write all text in Chinese.

${FACTS}

${FILES}

LENS OUTPUTS WITH VERDICTS (JSON): ${JSON.stringify(ok.map(r => ({ lens: r.lens, claims: r.claims.claims, phases: r.claims.phases, verdicts: r.verdicts ? r.verdicts.verdicts : null, missed: r.verdicts ? r.verdicts.missed : [] })))}

RULES:
- One edge per distinct relation (merge duplicates across lenses; keep the best evidence). Use the reviewer's corrected_claim wording. verdict = the reviewer's verdict (if lenses disagree, the more skeptical one wins). Refuted claims go to refuted_claims, not edges - except keep at most 3 refuted edges that viewers commonly believe, marked verdict "refuted", so the reader sees them crossed out.
- Include the off-screen and referent layer (VIEWERS, UPLOADER, TITLE, DEEPSEEK, ANTHROPIC, DOUBAO, LWF) only where a sourced or danmaku-grounded relation exists. Node labels: DS = "大肥鱼 (DS)", CL = "克劳德 (CL)", etc.
- Check "missed" items from reviewers against the data (open frames if needed) and add the ones that hold.
- phases: a single non-overlapping segmentation of f1-452 into 5-9 phases describing the relationship state, who dominates, and frame evidence.
- per_character: DS and CL (and CROWD if warranted): arc, pose signature (cite joint-angle numbers from kinematics_summary.json), expression arc with frames, 4-8 key frames.
- thesis: one paragraph.`

const model = await agent(integratePrompt, { label: 'integrate:model', phase: 'Integrate', schema: MODEL })
return { model, lens_stats: ok.map(r => ({ lens: r.lens, n_claims: r.claims.claims.length, verdicts: r.verdicts ? r.verdicts.verdicts.reduce((m, v) => (m[v.verdict] = (m[v.verdict] || 0) + 1, m), {}) : null })) }
