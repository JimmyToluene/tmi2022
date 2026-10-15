export const meta = {
  name: 'bv1znpg6de8g-set-survey',
  description: 'Survey the club set from the video frames (cameras, architecture, lighting, crowd) and consolidate a metric Blender scene spec, verified by re-projection',
  phases: [
    { title: 'Survey', detail: '6 specialists: camera solve x3 shots, architecture, lighting/materials, crowd' },
    { title: 'Consolidate', detail: 'merge into one metric scene spec and solve cameras against image anchors' },
    { title: 'Check', detail: 'independent critic re-projects the spec and compares with frames' },
  ],
}

const S = '/tmp/claude-0/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e/scratchpad'
const BL = '/home/user/tmi2022/video_analysis/BV1ZnpG6dE8g/blender'

const CONTEXT = `GOAL: rebuild the set of a 15-second AI-generated anime clip (Bilibili BV1ZnpG6dE8g) in Blender - everything EXCEPT the two characters, whose MMD models the user will import later. The scene must let the user drop MMD models in, re-shoot the three shots with matched cameras and get frames that line up with the original.
VIDEO: 1080x1920 portrait, 30 fps container, 452 frames (generated at 24 fps; every frame with f%5==2 duplicates f-1). Three shots, hard cuts at f149 and f304:
  shot 1 f1-148: DS (blue-haired maid girl with whale fins, ~1.58 m) leans with crossed forearms on a chrome handrail of a VIP balcony and faces the camera; behind her: other guests, dark interior, top-left a night-city skyline bokeh (lit windows). The camera DOLLIES in (measured: DS image scale x2.10 over the shot; background bokeh scale barely changes -> translation toward her, not a zoom), centred on her face; slight drift.
  shot 2 f149-303: over-the-shoulder from just behind DS (her back/hair fills the left of frame at first), looking DOWN into a sunken club floor: dense standing crowd around a small round brightly lit stage disc where CL (orange-haired girl in a long white/orange gown, ~1.60 m) dances; behind the crowd, raised tiers with small round cocktail tables and warm glowing table lamps; further back/up a mezzanine with a glass balustrade; a single white spotlight beam falls from the ceiling onto the stage area through haze; overall deep-blue ambience. Chrome handrail visible lower right. Measured camera: slow push x1.15, roll +12 deg (clockwise content rotation, mostly f180-210), content drifts up (camera tilts down) ~390 px.
  shot 3 f304-452: CL medium shot (head to knees), facing the lens, swaying hips, hands on skirt; camera above her eye line looking down slightly, so the crowd behind shows legs/arms at the top of frame; dark blue floor; floating sparkles; handheld-like roll +5 -> -8 -> +3 deg.
COORDINATES & CAMERA CONVENTION (mandatory): read ${BL}/camera_math.py and import it (sys.path.insert(0, '${BL}')). World = Blender Z-up metres, origin = centre of the stage disc at pit-floor level (z=0), +Y from DS's balcony toward the far side (balcony at negative Y). Cameras are {location, target, roll_deg, lens_mm} with a 36 mm VERTICAL sensor (vertical FOV = 2*atan(18/lens)). camera_math.project(points, location, target, roll_deg, lens_mm) gives pixel coords in the 1080x1920 frame; it matches Blender to 0.002 px. Positive roll_deg = content rotates clockwise on screen (same sign as the measured rot_deg).
FILES: frames ${S}/frames/fNNNN.jpg (1080x1920, 4-digit), labelled 6-frame strips ${S}/strips/strip_AAAA-BBBB.jpg (1-6, 7-12, ...), overview sheets ${S}/survey/shot1.jpg shot2.jpg shot3.jpg, zoomed performer crops ${S}/perf_crops/perf_NNNN.jpg (shot 2), measurements ${S}/final/measured.json (camera zoom/roll/pan per frame, push-in fixed point, beats), ${S}/final/image_anchors.json (DS face boxes in shot 1, CL head blob track in shot 2, CL face boxes in shot 3 - the reconstruction must reproduce these), per-frame CV ${S}/cv/per_frame_cv.json (global_motion per frame: dx,dy at 1/4 scale, scale, rot_deg). Python with numpy, opencv (cv2), PIL is available; use it to measure (lines, vanishing points, ellipses, colours, sizes) instead of guessing.
SCALE PRIORS: adult crowd members 1.55-1.90 m; anime characters ~1.58-1.62 m with heads ~0.24 m tall incl. hair (face brow-to-chin ~0.15 m, the anime-face detector box ~0.17 m wide); handrail top 1.05-1.10 m above its floor, tube diameter ~0.05 m; cocktail tables ~0.6 m diameter, ~0.75-1.05 m high; table lamps ~0.2 m tall.
Because the source is AI-generated, the three shots need not be perfectly consistent; where they conflict, keep ONE coherent venue and note the per-shot cheat (e.g. a camera that sits where it needs to) rather than distorting the architecture.`

const FRAG = {
  type: 'object',
  properties: {
    section: { type: 'string' },
    spec_fragment_json: { type: 'string', description: 'JSON (as a string) for your part of the scene spec, following the SPEC SCHEMA field names' },
    measurements: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, value: { type: 'string' }, unit: { type: 'string' }, method: { type: 'string' }, confidence: { type: 'number' } }, required: ['name', 'value', 'unit', 'method', 'confidence'] } },
    anchor_checks: { type: 'array', items: { type: 'object', properties: { what: { type: 'string' }, f: { type: 'integer' }, expected_px: { type: 'array', items: { type: 'number' } }, projected_px: { type: 'array', items: { type: 'number' } }, err_px: { type: 'number' } }, required: ['what', 'f', 'expected_px', 'projected_px', 'err_px'] } },
    open_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['section', 'spec_fragment_json', 'measurements', 'anchor_checks', 'open_issues'],
}

const SCHEMA_TEXT = `SPEC SCHEMA (metres, degrees, hex colours; the Blender builder consumes exactly these keys):
{
 "meta": {"fps":30,"frame_start":1,"frame_end":452,"resolution":[1080,1920],"sensor_height_mm":36},
 "world": {"bg_color":"#hex","bg_strength":0.0,"haze":{"density":0.0,"color":"#hex","anisotropy":0.0,"box":[xmin,ymin,zmin,xmax,ymax,zmax]}},
 "materials": {"<name>":{"base_color":"#hex","metallic":0,"roughness":0.5,"emission_color":"#hex","emission_strength":0,"transmission":0,"alpha":1}},
 "geometry": [ one object per entry; supported "type"s and their keys:
   {"type":"box","name","center":[x,y,z],"size":[sx,sy,sz],"rotation_deg":[rx,ry,rz],"material"}
   {"type":"cylinder","name","center":[x,y,z] (centre of the cylinder),"radius","depth","material","vertices":64}
   {"type":"steps","name","rect":[x0,y0,x1,y1],"z0","rise","count","axis":"+y|-y|+x|-x","material"}   (ascending terraces along axis; each step is a box)
   {"type":"tube_rail","name","points":[[x,y,z],...],"radius","material","posts":{"spacing","radius","height","material"}}   (points = top-of-rail polyline; posts drop to height below it)
   {"type":"glass_panel","name","from":[x,y,z],"to":[x,y,z],"height","thickness":0.012,"material"}   (bottom edge from->to, extruded up)
   {"type":"table_cluster","name","rect":[x0,y0,x1,y1],"z","rows","cols","jitter","seed","table_radius","table_height","table_material","lamp":{"height","radius","color":"#hex","strength"}}
   {"type":"skyline","name","center":[x,y,z],"size":[w,h],"rotation_deg":[rx,ry,rz],"seed","window_density","colors":["#hex"],"strength","blur":true}   (emissive backdrop plane of building silhouettes with lit windows)
   {"type":"sparkles","name","box":[xmin,ymin,zmin,xmax,ymax,zmax],"count","size","color":"#hex","strength","seed"}
 ],
 "lights": [{"name","type":"SPOT|AREA|POINT|SUN","location":[x,y,z],"target":[x,y,z],"color":"#hex","energy_w","spot_size_deg","spot_blend","size_m","volume_factor","shots":[1,2,3] (which shots it should be on in; omit = all)}],
 "crowd": {"seed","zones":[{"name","rect":[x0,y0,x1,y1],"z","exclude_circles":[[x,y,r]],"count","height_range":[min,max],"arms_up_fraction","seated_fraction","facing_target":[x,y],"palette":["#hex"]}],"animation":{"bounce_m","sway_deg","period_frames":15,"phase_jitter":1.0}},
 "characters": {"DS":{"location":[x,y,z] (point between the feet, on the floor),"facing_target":[x,y,z],"height_m","lean_note"}, "CL":{...}},
 "cameras": [{"name":"CAM_Shot1","shot":1,"frames":[1,148],"keys":[{"f","location","target","roll_deg","lens_mm"}],"dof":{"enabled":true,"focus":[x,y,z],"fstop":2.8}}, ... shots 2 and 3],
 "markers": [{"f","name"}],
 "notes": ["..."]
}`

const SPECIALISTS = [
  { key: 'cam1', prompt: `SPECIALTY: solve the shot-1 camera (f1-148). Determine lens (mm), distance to DS, camera height relative to the handrail, look direction, the dolly path (keys at least at f1, 37, 74, 111, 148 plus wherever the measured motion changes), roll. Use DS's face box sizes (anime_faces 390 px at f1 -> 827 px at f148) with the head-size prior to get distance x lens, and use perspective cues (how much the background bokeh/railing perspective changes, the rail's apparent slope, DS's foreshortening - is the camera at her eye level or slightly above/below?) to pick the lens. Place DS's feet at a balcony location consistent with the venue (balcony floor height is the architecture specialist's job; express your solution relative to DS's head position and also give it in world coordinates assuming DS head centre at world [0, -Ybal, zbal+1.45] - state your assumed Ybal/zbal so the consolidator can re-anchor). Project DS's head through your keys with camera_math and report anchor_checks against image_anchors shot1_DS_face (box centres).` },
  { key: 'cam2', prompt: `SPECIALTY: solve the shot-2 camera (f149-303) and, from it, the geometry of the view: elevation angle (use the stage disc's ellipse minor/major ratio - measure it on frames ~260-303 where the lit disc is visible - and the perspective of the crowd/table rows), horizontal distance and height of the camera above the stage, lens (use the size gradient of standing people's heads/bodies across rows, the performer's ~1.60 m height in the zoomed crops, table spacing), and the camera's motion over the shot (measured: push x1.15, +12 deg roll mostly f180-210, upward content drift = tilting down; decide which part is translation vs rotation). Also give DS's position relative to the camera (over-the-shoulder distance) from how large her head/hair and fin appear. Report anchor_checks for the CL head blob track (shot2_CL_head_blob) by projecting a point 1.50 m above the stage centre (CL stands at about the stage centre; refine her xy if needed).` },
  { key: 'cam3', prompt: `SPECIALTY: solve the shot-3 camera (f304-452): lens, distance to CL, camera height and downward tilt (from CL's foreshortening, how much of the background floor and the background crowd's legs are visible, where the horizon would be), and the handheld motion (measured roll +5, then -8, then +3 deg; small pans/tilts - see per_frame_cv global_motion). CL stands on the stage disc (centre ~[0,0,stage_height]); reconcile her facing with shot 2 (in shot 2 she faces roughly toward DS's balcony = -Y). Report anchor_checks for shot3_CL_face boxes by projecting CL's face centre (~1.45 m above her feet).` },
  { key: 'arch', prompt: `SPECIALTY: architecture and layout of the venue as one coherent metric model: sunken pit / dance floor extent, stage disc radius and height, how the crowd area meets the raised tiers (number of tiers, rise per tier, depth), cocktail-table layout (count per tier, spacing, table+lamp sizes), the mezzanine/upper gallery with glass balustrade (height, depth, downlights), back walls, ceiling height and the spotlight rig, the VIP balcony DS stands on (floor height above the pit, distance from the stage, handrail line, posts, glass panels), and the interior behind DS seen in shot 1 (guests, window wall with the night-city skyline). Measure from frames (counts of tables/lamps, relative sizes, ellipse of the stage, perspective of rows). Output geometry entries (box/cylinder/steps/tube_rail/glass_panel/table_cluster/skyline) and characters.DS/CL placement.` },
  { key: 'light', prompt: `SPECIALTY: lighting, atmosphere and materials. Sample colours from the frames (python: average/median colours of regions) to define: world/ambient blue, haze density/colour, the ceiling spotlight beam (colour, cone angle from the beam's width/spread, where it comes from), stage-disc emission/brightness, table-lamp colour/strength, mezzanine downlights, rim/key lights on DS in shot 1 (direction from highlights on her hair/face; there is a cool key from camera-left/top?) and on CL in shot 3 (warm key on her face/dress from camera-left? soft fill), city-skyline window colours, sparkles in shot 3, chrome/glass/floor materials. Give energies in watts for Blender (Cycles/EEVEE) at a plausible exposure, and state the colour-management assumption (Filmic/AgX, exposure). Mark which lights are per-shot cheats (shots: [...]).` },
  { key: 'crowd', prompt: `SPECIALTY: the crowd. From the frames, estimate how many people stand in the pit around the stage (count heads in shot 2 frames ~260-303 by region), how many sit/stand at the tiers' tables, density per m^2 by zone, the gap around the stage disc, height distribution, fraction with arms raised (count in shot 2 and the arms visible at the top of shot 3), facing (most face the stage?), clothing palette (sample colours: mostly dark/black with white/light-blue shirts?), motion (bouncing/swaying amplitude and rhythm: use per_frame_cv residual_flow and residual_grid3x3 in shot 2/3; the music is 120 BPM = one beat per 15 frames) and the people behind DS in shot 1. Output a crowd spec (zones with rects in world coordinates consistent with a stage disc at the origin) and the animation parameters.` },
]

const specPrompt = s => `You are a set-survey specialist rebuilding a club environment for Blender from video frames.

${CONTEXT}

${SCHEMA_TEXT}

${s.prompt}

Work from the images and measure with code. Return: spec_fragment_json (only the keys you own, as a JSON string), measurements (each with method and confidence), anchor_checks (projection vs image anchors where applicable), open_issues.`

phase('Survey')
const frags = await parallel(SPECIALISTS.map(s => () => agent(specPrompt(s), { label: `survey:${s.key}`, phase: 'Survey', schema: FRAG })))
const got = frags.map((f, i) => f ? Object.assign({ key: SPECIALISTS[i].key }, f) : null).filter(Boolean)
log(`survey fragments: ${got.length}/6`)

phase('Consolidate')
const SPEC = {
  type: 'object',
  properties: {
    spec_json: { type: 'string', description: 'the complete scene spec as a JSON string following the SPEC SCHEMA' },
    anchor_checks: FRAG.properties.anchor_checks,
    decisions: { type: 'array', items: { type: 'string' } },
    cheats: { type: 'array', items: { type: 'string' } },
  },
  required: ['spec_json', 'anchor_checks', 'decisions', 'cheats'],
}
const consolidated = await agent(`Consolidate set-survey fragments into ONE complete, coherent, metric Blender scene spec.

${CONTEXT}

${SCHEMA_TEXT}

FRAGMENTS (JSON): ${JSON.stringify(got)}

TASKS:
1. Resolve conflicts between fragments (scale, balcony height, distances, lens). Prefer measured values with higher confidence; keep one coherent venue.
2. Re-anchor the camera solutions into the final world (shot-1 keys were expressed relative to an assumed DS head position; shot-2 relative to the stage; make DS's placement, the balcony and the shot-1/shot-2 cameras mutually consistent - DS stands at the balcony rail, the shot-2 camera is just behind/above her, the shot-1 camera floats on the arena side looking back at her).
3. Write the spec and RUN python with camera_math.project to check: shot 1 DS face centre vs shot1_DS_face box centres (and apparent face size vs box width, using a 0.17 m face width), shot 2 CL head vs shot2_CL_head_blob, shot 3 CL face vs shot3_CL_face. Iterate on the camera keys (interpolate between keys linearly when checking intermediate frames) until the median error is under ~40 px per shot, and report the final anchor_checks.
4. Add markers for both cuts and every beat frame from measured.json (name "beat"), and notes. Make sure every geometry entry uses a supported type and every material referenced exists.
Return spec_json (complete), anchor_checks, decisions, cheats.`, { label: 'consolidate:spec', phase: 'Consolidate', schema: SPEC })

phase('Check')
const CHECK = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['pass', 'pass-with-patches', 'fail'] },
    patches: { type: 'array', items: { type: 'object', properties: { path: { type: 'string', description: 'JSON pointer-like dotted path into the spec, e.g. cameras.1.keys.0.lens_mm or geometry[name=Stage].radius' }, value_json: { type: 'string' }, reason: { type: 'string' } }, required: ['path', 'value_json', 'reason'] } },
    findings: { type: 'array', items: { type: 'string' } },
    anchor_checks: FRAG.properties.anchor_checks,
  },
  required: ['verdict', 'patches', 'findings', 'anchor_checks'],
}
const check = consolidated ? await agent(`You are an independent critic of a Blender scene spec reconstructed from video frames. Try to find what is wrong.

${CONTEXT}

${SCHEMA_TEXT}

SPEC TO CHECK: ${consolidated.spec_json}

CONSOLIDATOR'S DECISIONS: ${JSON.stringify(consolidated.decisions)}  CHEATS: ${JSON.stringify(consolidated.cheats)}

CHECKS (run python with camera_math; open frames to compare):
- Re-project anchors yourself (do not trust the reported numbers): DS face (shot 1), CL head (shot 2), CL face (shot 3), and additionally: the handrail line in shot 1 (where the rail top crosses the frame in f1 and f148) and in shot 2 (lower right in f260-303), the stage disc ellipse in shot 2 (f280), the tier/table rows and the mezzanine edge in shot 2 (f260), the spotlight beam's position in shot 2. Compare with the frames (measure the image positions with code).
- Physical plausibility: people/tables/rail sizes, balcony height vs the steep downward view, lens values, camera inside geometry, lights pointing at targets, crowd zones overlapping the stage or tiers, materials missing.
- Schema validity: only supported geometry types, all referenced materials exist, cameras have keys covering their frame ranges.
Return verdict, patches (each a concrete replacement value as JSON, with the dotted path), findings and your own anchor_checks.`, { label: 'check:reproject', phase: 'Check', schema: CHECK }) : null

return { fragments_summary: got.map(f => ({ key: f.key, measurements: f.measurements, open_issues: f.open_issues, anchor_checks: f.anchor_checks })), consolidated, check }
