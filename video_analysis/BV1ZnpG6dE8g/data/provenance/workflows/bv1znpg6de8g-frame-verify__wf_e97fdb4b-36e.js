export const meta = {
  name: 'bv1znpg6de8g-frame-verify',
  description: 'Independent frame-by-frame verification of already-annotated BV1ZnpG6dE8g chunks (args = chunk numbers; annotations read from files)',
  phases: [
    { title: 'Verify', detail: 'independent skeptic re-checks every frame of each chunk against the images, returns patches' },
  ],
}

const S = '/tmp/claude-0/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e/scratchpad'
const pad = n => String(n).padStart(4, '0')
const CHUNKS = []
for (let k = 0; k < 13; k++) {
  const start = 36 * k + 1, end = Math.min(36 * k + 36, 452)
  const strips = []
  for (let s = start; s <= end; s += 6) strips.push(`${S}/strips/strip_${pad(s)}-${pad(Math.min(s + 5, 452))}.jpg`)
  CHUNKS.push({ k: k + 1, start, end, strips, digest: `${S}/digest/chunk_${String(k + 1).padStart(2, '0')}.json` })
}

const VIDEO_FACTS = `VIDEO: Bilibili BV1ZnpG6dE8g "意气风发啊大肥鱼，但可别高兴得太早" by 阿滴指南 (uploaded 2026-10-10), tags deepseek/AI/大肥鱼.
AI-generated anime clip, 1080x1920 vertical, 30 fps, 452 frames, 15.07 s. It was generated at 24 fps and padded to 30 fps:
every frame with frame%5==2 is a pixel-identical duplicate of the previous frame (digest field dup_of_prev=true).
SHOTS (measured): shot 1 = frames 1-148 (0-4.93 s), shot 2 = frames 149-303 (4.93-10.10 s), shot 3 = frames 304-452 (10.10-15.07 s). Hard cuts at 149 and 304.
AUDIO: music at 120 BPM (beat every ~15 frames: 3,18,32,47,62,77,92,107,124,...), quiet build 4.0-6.0 s, energy drop/hit at ~6.0 s (frame ~181), loud through the end.
CHARACTER IDS (use exactly these):
  DS  = blue-haired girl in navy/white maid outfit with whale-fin-like ear fins and a blue whale tail; viewers call her 大肥鱼 (the DeepSeek whale personified).
  CL  = orange-haired girl in white/orange/black gown with a gold flower hair ornament; viewers read her as Claude personified (弹幕: 亲妈克劳德/老妈到了).
  CROWD = the audience mass. AUD_1, AUD_2, ... = individual audience members that are distinctly visible (e.g. dark foreground heads in shot 1, raised arms/silhouettes in shot 3). Keep AUD numbering stable within your chunk and describe each so neighbours can match them.
  CAM = the camera/viewer (only as an interaction target, e.g. eye contact with the lens).
CONVENTIONS:
  - l_/r_ always means the CHARACTER'S OWN anatomical left/right (a character facing the camera has her left arm on screen-right).
  - Keypoints (kp) are [x, y] normalized to the FULL 1080x1920 frame, x rightward, y downward, 0..1. Only include joints that are visible or confidently inferable; may lie slightly outside 0..1 if just off-frame is not allowed - omit off-frame joints.
    Joint names: head_top, nose, chin, neck, l_shoulder, r_shoulder, l_elbow, r_elbow, l_wrist, r_wrist, l_hand_tip, r_hand_tip, l_hip, r_hip, l_knee, r_knee, l_ankle, r_ankle.
  - head_ypr = [yaw, pitch, roll] in degrees, VIEWER-centric: yaw>0 = face turned toward screen-right, pitch>0 = chin raised, roll>0 = top of head tilted toward screen-right. 0,0,0 = facing the lens squarely. Back-of-head shots: yaw ~ +/-180.
  - bbox = [x0, y0, x1, y1] normalized, of the character's visible body in frame.`

const INPUTS = c => `FILES (read them with the Read tool; images are real frames of the video):
  - Labelled strips, 6 consecutive frames per image, frame number + timestamp burned in at bottom-left of each tile: ${c.strips.join(', ')}
  - Full-resolution frames for close inspection: ${S}/frames/fNNNN.jpg (4-digit zero-padded, e.g. ${S}/frames/f${pad(c.start)}.jpg). Open full-res frames whenever eye/mouth/finger/hair detail matters - and always for frames where you claim a micro-event (blink, mouth change, finger move, head turn onset).
  - For frames 149-303 the on-stage performer (CL) is tiny in the wide shot; 4x zoomed full-body crops exist as ${S}/perf_crops/perf_NNNN.jpg and as 6-frame zoom strips in ${S}/perf_strips/ (Glob perfstrip_*.jpg and use the ones overlapping your range).
  - Machine signals per frame (JSON array): ${c.digest}. Fields: dup_of_prev, cam (frame-to-frame similarity transform: dx/dy px at 1/4 scale, scale>1 = zoom-in/push-in, rot_deg), flow_mean/residual_flow_mean (residual = motion of things in the scene after removing camera motion; residual_grid3x3 = where it happens, row-major top-left..bottom-right), anime_faces_xywh (anime-face detector boxes, full-res px), mp_poses (MediaPipe body joints [x,y,visibility] normalized - MediaPipe is trained on real humans, so treat it as a hint and check it against the image; it often fails or misplaces joints on anime bodies), mp_hands, mp_faces (head_pose_deg + blendshapes like eyeBlinkLeft/jawOpen/mouthSmileLeft - again only a hint), performer_blob / performer_pose_upscaled (CL tracker in shot 2, full-frame normalized), audio (beat/onset/rms_db), danmaku_here (viewer comments timed to that frame).`

const KP = { type: 'object', additionalProperties: { type: 'array', items: { type: 'number' } } }
const CHAR = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    vis: { type: 'string', description: 'which part of the character is in frame / occlusion' },
    bbox: { type: 'array', items: { type: 'number' } },
    facing: { type: 'string', description: 'body/face orientation relative to camera' },
    head_ypr: { type: 'array', items: { type: 'number' } },
    gaze: { type: 'string', description: 'where the eyes point and the likely target (CAM / CL / DS / stage / crowd / down / off-screen ...)' },
    eyes: { type: 'string', description: 'open/half-lidded/closed/blinking, iris position, highlights' },
    brows: { type: 'string' },
    mouth: { type: 'string' },
    expr: { type: 'string', description: 'facial expression and the emotion it reads as, with intensity 0-1' },
    torso: { type: 'string', description: 'torso orientation, lean, shoulder line, breathing/bounce' },
    l_arm: { type: 'string' },
    r_arm: { type: 'string' },
    hands: { type: 'string', description: 'both hands: what they touch/grip, finger configuration' },
    legs: { type: 'string' },
    hair_cloth: { type: 'string', description: 'secondary motion of hair, fins, ribbons, skirt' },
    action: { type: 'string', description: 'what the character is doing in this frame (verb phrase)' },
    kp: KP,
    kp_src: { type: 'string', description: 'mp | visual | mixed' },
  },
  required: ['id', 'vis', 'bbox', 'facing', 'head_ypr', 'gaze', 'eyes', 'brows', 'mouth', 'expr', 'torso', 'l_arm', 'r_arm', 'hands', 'legs', 'hair_cloth', 'action', 'kp', 'kp_src'],
}
const FRAME = {
  type: 'object',
  properties: {
    f: { type: 'integer' },
    shot: { type: 'integer' },
    cam: { type: 'object', properties: { size: { type: 'string' }, angle: { type: 'string' }, move: { type: 'string' }, focus: { type: 'string' } }, required: ['size', 'angle', 'move', 'focus'] },
    chars: { type: 'array', items: CHAR },
    inter: { type: 'array', items: { type: 'object', properties: { from: { type: 'string' }, to: { type: 'string' }, channel: { type: 'string', description: 'gaze | attention | spatial-hierarchy | framing/occlusion | proximity | timing/response | address-to-camera | other' }, desc: { type: 'string' } }, required: ['from', 'to', 'channel', 'desc'] } },
    env: { type: 'string' },
    delta: { type: 'string', description: 'what changed versus the previous unique frame (be specific, in pixels/degrees where possible)' },
  },
  required: ['f', 'shot', 'cam', 'chars', 'inter', 'env', 'delta'],
}
const EVENT = { type: 'object', properties: { start: { type: 'integer' }, end: { type: 'integer' }, who: { type: 'string' }, type: { type: 'string', description: 'blink | gaze-shift | head-turn | head-tilt | smile-onset | smile-offset | mouth | brow | hand-move | arm-move | finger | torso-lean | hip-sway | step | weight-shift | hair-sway | cloth | camera-move | cut | lighting | crowd-motion | other' }, desc: { type: 'string' } }, required: ['start', 'end', 'who', 'type', 'desc'] }
const ANNOT = {
  type: 'object',
  properties: {
    chunk: { type: 'integer' },
    frames: { type: 'array', items: FRAME },
    events: { type: 'array', items: EVENT },
    chunk_summary: { type: 'string' },
  },
  required: ['chunk', 'frames', 'events', 'chunk_summary'],
}
const PATCHES = {
  type: 'object',
  properties: {
    chunk: { type: 'integer' },
    frames_checked: { type: 'integer' },
    full_res_frames_opened: { type: 'array', items: { type: 'integer' } },
    corrections: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          f: { type: 'integer' },
          target: { type: 'string', description: 'dotted path: cam.size | cam.move | env | delta | inter | <CHARID>.<field> (e.g. DS.eyes, CL.r_arm, AUD_2.action) | <CHARID>.kp.<joint> | <CHARID>.head_ypr | <CHARID> (whole character object, to add a missing character) | -<CHARID> (remove a hallucinated character)' },
          value_json: { type: 'string', description: 'the corrected value, JSON-encoded (string values in quotes, arrays/objects as JSON)' },
          reason: { type: 'string' },
        },
        required: ['f', 'target', 'value_json', 'reason'],
      },
    },
    events_final: { type: 'array', items: EVENT, description: 'the complete corrected micro-event list for this chunk (confirmed + corrected + newly found; rejected ones removed)' },
    rejected_events: { type: 'array', items: { type: 'string' } },
    accuracy_estimate: { type: 'number', description: 'fraction of annotated fields you judged correct before your patches, 0..1' },
    verifier_notes: { type: 'string' },
  },
  required: ['chunk', 'frames_checked', 'full_res_frames_opened', 'corrections', 'events_final', 'rejected_events', 'accuracy_estimate', 'verifier_notes'],
}

const annotatePrompt = c => `You are doing the finest-grained, frame-by-frame visual annotation of one chunk (frames ${c.start}-${c.end}) of a short video, for pose modeling and character-relationship analysis.

${VIDEO_FACTS}

${INPUTS(c)}

TASK:
1. Read the digest JSON first, then every strip image of your range, then full-res frames as needed (open at least 8 full-res frames spread over your range, more around any change).
2. Produce one record in "frames" for EVERY frame in ${c.start}-${c.end} whose dup_of_prev is false (skip duplicates; they are copied automatically). For each record describe every visible character (DS, CL, distinct AUD_n; CROWD as one entry when the crowd is visible) with all fields, at the finest detail you can actually see: exact eye state (open / half / closing / closed / opening), iris direction, mouth shape (closed smile, parted lips, teeth visible...), brow shape, head yaw/pitch/roll estimate, shoulder line, each arm and hand separately (what the fingers do, what they rest on), legs/stance when visible, secondary motion of hair/fins/ribbons/skirt, and the action. Give kp for each visible joint (prefer MediaPipe values only where they visibly land on the right body part; otherwise estimate from the image) and set kp_src.
3. "inter": every relation observable IN THIS FRAME between entities: who looks at whom (incl. CAM), who is above/below whom, who occludes/frames whom, foreground/background hierarchy, relative screen size, whether a motion answers another's motion or a beat.
4. "delta": what changed vs the previous unique frame, concretely.
5. "events": every micro-event with start/end frames (blinks, gaze shifts, smile onset, head turns/tilts, finger and hand moves, hip sways, weight shifts, hair sways, camera moves, light/crowd changes). Use exact frame numbers.
6. Report only what is visible. Do not interpret what the characters symbolize - that is a later step. Do not invent detail you cannot see; say "not visible" or "indistinct".
Return the structured result.`

const verifyPrompt = (c, a) => `You are an independent, skeptical verifier of a frame-by-frame video annotation (frames ${c.start}-${c.end}). Another annotator produced the JSON below. Assume it contains errors - typical ones: left/right swapped (l_/r_ must be the CHARACTER'S OWN anatomical side), blinks or mouth changes claimed that do not happen (or missed ones), wrong gaze target, invented hand/finger motion, keypoints on the wrong body part, head angles with wrong sign convention, characters missing or hallucinated, events with wrong frame ranges, camera movement misdescribed (check the digest's cam field: scale>1 means push-in).

${VIDEO_FACTS}

${INPUTS(c)}

ANNOTATION TO VERIFY: read the JSON file ${a} (an object {chunk, frames, events, chunk_summary}; use python3 to load and iterate it).

TASK: Look at every strip in the range and open full-res frames to check every claimed micro-event and at least 10 frames in total. Check every frame record. Return:
- corrections: one patch per wrong or missing field (dotted target path, JSON-encoded corrected value, reason). Also patch frames that are missing from the annotation (target = the character id with a whole character object, plus cam/env/delta) if a non-duplicate frame has no record.
- events_final: the full corrected micro-event list for the chunk.
- rejected_events: short descriptions of annotator events you removed and why.
- accuracy_estimate and notes.
Be strict but fair: only patch what is actually wrong or materially imprecise.`

const contextPrompt = `Research the cultural and real-world context of a Bilibili video, for an analysis of the relationships between its characters. Use WebSearch/WebFetch (load them via ToolSearch first: query "select:WebSearch,WebFetch"). Search in Chinese and English.

${VIDEO_FACTS}

What viewers wrote (danmaku, with second offsets): 0.36s 我还以为是lwf在那眺呢 | 0.48s 依旧渲染大赛 | 0.51s 吓我一跳，我还以为豆包呢 | 0.97s 世界第三次渲染大赛正式开始 | 2.1-5.4s many 大肥鱼！ | 2.12s claude：看什么，中国人？ | 3.0-4.2s 脸色对了 / 脸色不对了 | 3.87s 看什么看毛绒绒小笨蛋 | 3.92s+ 老妈到了 / 严厉的老妈到了 / 严母到了 / 亲妈克劳德 (repeated to ~11.8s) | 5.15s 舞蹈出自美国丽人 | 5.21s 我猜是豆包 | 6.66s 吓哭了，老妈到了，一个照面给大肥鱼切成鱼片了 | 8.11s 『现代最强』 | 8.67s 我还以为是梁文峰呢 | 9.81s 大肥鱼喝大了 | 10.62s 只不过是生在没有我时代的凡夫 | 11.27s 这是死亡回归的声音吗 | 11.38s 报告总部，事情比我们想象的还要好 | 11.55s 两个老婆 | 11.67s 小克好看捏 | 11.96s 敢说中文吗 | 12.08s 报告总部，事情没我们想的那么糟糕 | 13.5-13.9s 小克这个妖娆 / 小克魅完了 | 14.10s 豆包上不了桌吧 | 14.57s 克劳德.
Comments: "claude这几下明明动作幅度不大，为什么这么瑟琴啊" / "因为长裙做这种动作就会很媚" / "ds那个不媚" / "明明是二创里穿的最多的。但总感觉有股外冷内齁的劲…我感觉鱼片都没克劳德穿着衣服色" / "她们在干嘛？" -> "蒸馏ing勿扰…" / "跳完后：" / "给配了".

ANSWER, with a source URL for every factual claim and a confidence for each:
1. Why DeepSeek is called 大肥鱼 and personified as a whale-finned blue girl; who lwf/梁文峰 is.
2. Why Claude is called DeepSeek's 亲妈/老妈 by Chinese netizens (distillation allegations; any Anthropic statement naming DeepSeek; Anthropic's policy on Chinese-controlled companies - relevant to the danmaku "claude：看什么，中国人？" and "敢说中文吗"). What "蒸馏" means here.
3. What real events around late Sept - 10 Oct 2026 could make DeepSeek "意气风发" and warn "别高兴得太早" (new DeepSeek release, benchmark wins, a Claude release, etc.). Search news for DeepSeek and for Claude/Anthropic in that window. If you cannot find anything definitive say so explicitly - do not guess.
4. The "渲染大赛" / AI-model-personification (AI拟人) trend on Bilibili, the uploader 阿滴指南, and whether this is part of a series; why some viewers thought the orange girl was 豆包 (Doubao) or what Doubao's personification looks like.
5. Decode the anime/meme references in the danmaku: 『现代最强』, 只不过是生在没有我时代的凡夫, 死亡回归的声音, 报告总部…, 美国丽人, 鱼片, 脸色对了.
Return a structured report: findings per question with sources and confidence, then a short list of what remains uncertain.`

phase('Verify')
const RAW = S + '/raw'
const WANT = (args || []).map(Number)
const res = await parallel(WANT.map(k => () => {
  const c = CHUNKS[k - 1]
  return agent(verifyPrompt(c, `${RAW}/chunk_${String(k).padStart(2, '0')}.annot.json`), { label: `verify:${c.start}-${c.end}`, phase: 'Verify', schema: PATCHES })
    .then(v => v ? ({ chunk: k, corrections: v.corrections.length, accuracy_estimate: v.accuracy_estimate, verifier_notes: v.verifier_notes }) : null)
}))
return { chunks: res }
