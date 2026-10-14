# 交接文档：BV1ZnpG6dE8g 逐帧分析 + Blender 场景重建 + VMD

最后更新：2026-10-14。本文写给接手的人或新会话：读完就能知道做了什么、东西在哪、怎么复现、还差什么。

## 1. 现状一览

| 项目 | 状态 |
|---|---|
| 逐帧分析：452 帧标注、事件、人物关系模型、交互报告 | **完成** |
| Blender 场景（不含两个角色）和三个镜头的摄影机 | **完成** |
| 最终交付 VMD：`camera.vmd`、`DS.vmd`、`CL.vmd` | **完成**，已用 mmd_tools 回读校验 |
| 含 VMD 驱动人台的 .blend | **完成** |
| 最终预览视频（无声，452 帧） | 交接时还在渲染，见第 6 节 |
| 场景独立复核（set-survey 工作流的 critic） | 交接时还在运行，见第 6 节 |
| 推送到 GitHub | **被拒绝（403）**，所有提交在 git bundle 里，见第 3 节 |

用户的原始需求依次是：
1. 用最细的颗粒度逐帧分析人物关系，并建模姿势和动作。
2. 在 Blender 里重建场景，人物的 MMD 模型除外。
3. 最终交付物是 VMD：镜头和两个角色的动作，在 Blender + mmd_tools 里使用。

## 2. 视频与角色

- **视频**：B站 BV1ZnpG6dE8g《意气风发啊大肥鱼，但可别高兴得太早》，UP 主：阿滴指南，链接 https://b23.tv/L8OrkqL。
- **规格**：1080×1920 竖屏，30 fps，452 帧，15.07 s。
- **生成方式**：AI 生成的动画，原生 24 fps，补帧到 30 fps。
  - 镜头 2、3：凡 `f % 5 == 2` 的帧都与前一帧相同。
  - 镜头 1：`f % 5 ∈ {2,3}` 的帧都重复。
  - 全片共 360 张独立画面。
- **三个镜头**，在 f149 和 f304 硬切：
  1. f1–148：50 mm 推轨，推向倚在包厢栏杆上的 DS（大肥鱼，蓝发女仆，约 1.58 m）。
  2. f149–303：36 mm，从 DS 身后过肩，俯拍舞池，CL（克劳德，橙发白裙，约 1.60 m）站在舞台圆盘上。
  3. f304–452：247 mm 长焦，从 DS 包厢方向锁定 CL 的中景。
- **配乐**：120 BPM，每 15 帧一拍，`beat` 标记写在 .blend 里。
- **人物关系的核心结论**：
  - 共 56 条关系边：6 条已证实，47 条成立但属解读，3 条被推翻；另有 16 条常见说法被否定。
  - 物理上的高处始终属于 DS，而注视、画面占比、色调和运动的主动权在 f303→304 一次性交给了 CL。
  - 全文见 `data/analysis_model.json` 和报告。

## 3. 恢复与推送（GitHub 403 的处理）

会话里的 GitHub App 对 `JimmyToluene/tmi2022` 没有写权限，三种方式都失败：`git push`、`create_branch`、`create_repository`。错误都是 "Resource not accessible by integration" / 403。

所有工作都提交在本地分支 `claude/video-character-analysis-v6hpo4` 上。远端这条分支仍停在基线 `0d395a1`（即 `main`）。

交付包里有两个 bundle：

| 文件 | 内容 | 用法 |
|---|---|---|
| `tmi2022_branch_incremental.bundle` | 只含 `main..claude/video-character-analysis-v6hpo4` 的提交 | 在已有的 tmi2022 克隆里使用 |
| `tmi2022_full.bundle` | 整个分支，包含 main 的历史 | 新建仓库时使用 |

在已有克隆里：

```bash
git fetch /path/to/tmi2022_branch_incremental.bundle claude/video-character-analysis-v6hpo4:claude/video-character-analysis-v6hpo4
git push -u origin claude/video-character-analysis-v6hpo4
```

新建仓库（例如 `video-analysis-BV1ZnpG6dE8g`）：

```bash
git clone -b claude/video-character-analysis-v6hpo4 /path/to/tmi2022_full.bundle BV1ZnpG6dE8g
cd BV1ZnpG6dE8g && git remote set-url origin git@github.com:<你>/<新仓库>.git && git push -u origin HEAD
```

如果想让 Claude 直接推送：
1. 在 https://claude.ai/connect-github 重新连接 GitHub。
2. 如果 Claude GitHub App 没有安装到这个仓库，就安装它（或请仓库所有者安装），并授予该仓库的 Contents 写权限。

## 4. 交付物在哪

仓库内，路径相对仓库根：

| 路径 | 内容 |
|---|---|
| `video_analysis/BV1ZnpG6dE8g/blender/vmd/camera.vmd` | 三个镜头合成的一条 MMD 相机动作。MMD 第 0 帧 = 原片 f1。 |
| `.../blender/vmd/DS.vmd`、`CL.vmd` | 两个角色的骨骼动作和表情 morph |
| `.../blender/vmd/camera_check.json` | camera.vmd 回读校验结果，逐帧 |
| `.../blender/blend/BV1ZnpG6dE8g_set_with_mannequins.blend` | 完整场景，VMD 已加载到灰色人台上 |
| `.../blender/blend/BV1ZnpG6dE8g_set.blend` | 只有场景和摄影机 |
| `.../blender/scene_spec.json` | 场景度量参数，是唯一的事实来源 |
| `.../blender/posefit/pose_{DS,CL}.json` | 逐帧骨骼旋转和重投影误差 |
| `.../blender/README.md` | **给最终用户的使用说明**：怎么挂 .pmx、加载 VMD、精度、局限 |
| `.../blender/*.py` | 场景、摄影机、姿势、VMD 管线 |
| `.../data/` | 分析数据，详见第 9 节 |
| `.../report.html` | 自包含的交互报告（双击打开） |
| `.../figures/timeline_measured.png` | 测量时间轴图 |
| `.../scripts/` | 分析管线：下载后的 CV、音频、标注合并、关系、报告 |

在线报告（私有 artifact，链接固定）：https://claude.ai/artifact/GYHgT1SjBS67qESgYBmHqj 。它的状态栏还停在"接近完成"那一版，见第 6 节。

仓库外还有一个工作数据包 `BV1ZnpG6dE8g_workdir.tar.gz`，结构见第 10 节。

## 5. 精度（实测）

| 项目 | 结果 |
|---|---|
| camera.vmd 回读：探针点在 VMD 相机和场景相机里的像素差（每 3 帧测一次，共 151 帧） | 中位 0.21 px，p95 0.69，最大 0.91。分镜头：镜头 1 中位 0.22、最大 0.91；镜头 2 中位 0.05；镜头 3 为 0.59 |
| VMD 视角取整：VMD 只存整数度，取整误差用距离补偿 | 补偿量最大 4% |
| DS.vmd / CL.vmd 回读：mmd_tools 导入到新骨架后比较关节位置 | 0.0 cm |
| 姿势拟合重投影，中位 / p90：DS 镜头 1 | 6.8 / 23.7 px |
| 姿势拟合重投影，中位 / p90：DS 镜头 2 | 6.9 / 53.5 px |
| 姿势拟合重投影，中位 / p90：CL 镜头 2 | 3.1 / 10.6 px |
| 姿势拟合重投影，中位 / p90：CL 镜头 3 | 8.1 / 19.3 px |
| 场景摄影机对画面锚点（勘测汇总） | 镜头 1 中位 4.2 px；布局检查点中位 6.2 px |

关键帧叠图检查：人台在三个镜头里都和原角色对齐。对比图里含原片画面，所以只在工作目录内部使用，没有放进交付包。

## 6. 未完成和交接时正在运行的任务

1. **场景复核（critic）**
   - 运行位置：工作流 `wf_f416f09c-07e` 的 `check:reproject` 步骤，是会话休眠被杀后续跑的。
   - 内容：它独立重投影整个 scene spec，交接时正在核对镜头 1。它的思路是：DS 自身约 3 cm 的漂移被折算进了摄影机关键帧，导致 f1–69 栏杆立柱偏 20–45 px。这是已知的取巧，见第 8 节。
   - **如果它给出补丁**：
     1. 把补丁合并到 `blender/scene_spec.json`。补丁路径是相对汇总规格的点号路径。
     2. 按第 7 节的顺序重跑：`build_scene` → `pose_fit` → `export_motion_vmd` → `export_camera_vmd` → `assemble_vmd_preview` → `render_video`。
     3. 比较新旧 `camera_check.json` 和姿势拟合误差，变差就不采用。
   - **如果没有补丁或它没跑完**：现有 spec 就是最终版。
2. **最终预览视频**
   - 渲染命令：`render_video.py BV1ZnpG6dE8g_set_with_mannequins.blend render_final --scale 0.333 --samples 10 --frames 1-452 --label 1`。
   - 设置：Cycles CPU，约 6 s 一帧；只渲染独立帧，重复帧直接复制；输出 360×640 的无声 H.264 MP4。
   - 渲染完要核对 452 帧、15.07 s。
   - 交接时的进度见交付消息。如果数据包里没有这个 MP4，按上面的命令重渲染即可。
3. **在线报告的状态栏**：`final/status.json` 还写着"VMD 预览版"和"镜头 3 235 mm"。应改为"VMD 正式版已交付；镜头 3 247 mm"，然后：
   1. 运行 `scripts/build_report.py final scripts/report_template.html report.html`。
   2. 用同一个 artifact 链接重新发布。
4. **推送**：见第 3 节。

## 7. 复现管线

### 环境

本会话的版本：Python 3.13，bpy 5.2.2（pip），mediapipe 1.1.0，librosa 1.0.0，scipy 1.18.1，numpy 2.5.3，opencv-python，Pillow 12.3，yt-dlp 2026.8.19，ffmpeg 6.1。

- MediaPipe 需要系统库：`apt-get install -y libegl1 libgles2 libgl1`。
- **mmd_tools**：
  - 安装：`git clone https://github.com/MMD-Blender/blender_mmd_tools`。本会话用的提交是 `e321bd02`（4.5.x）。还要 `pip install` 它 wheels 目录里自带的 `opencc` wheel。
  - 在 bpy 模块里使用：`sys.path.insert(0, <mmd_tools 克隆目录>)`，然后 `import mmd_tools; mmd_tools.register()`。
  - 坑：factory reset 之后再次 register 会报 "already registered"，要用 try/except 包住。
- **MediaPipe 模型**：`pose_landmarker_heavy.task`、`hand_landmarker.task`、`face_landmarker.task`，从 Google 的 MediaPipe 模型页下载。动漫脸检测用 `lbpcascade_animeface.xml`（nagadomi/lbpcascade_animeface）。

### A. 分析

下面用 `S` 表示工作目录，`R=video_analysis/BV1ZnpG6dE8g`。

```bash
# 原片（自行下载，版权内容不随交付分发）
yt-dlp -f "bv*[vcodec^=avc1][height>=1920]+ba/bv*+ba/b" --merge-output-format mp4 -o "$S/video/video.%(ext)s" https://www.bilibili.com/video/BV1ZnpG6dE8g
ffmpeg -i $S/video/video.mp4 -vsync 0 -q:v 2 $S/frames/f%04d.jpg
ffmpeg -i $S/video/video.mp4 -ac 1 -ar 22050 $S/audio/audio22k.wav
yt-dlp --skip-download --write-subs --sub-langs all --write-comments --write-info-json -o "$S/ctx/ctx.%(ext)s" <URL>   # 弹幕

python3 $R/scripts/cv_metrics.py $S/frames $S/models $S/cv              # 切镜、重复帧、ORB 运动、MediaPipe
python3 $R/scripts/audio_metrics.py $S/audio/audio22k.wav $S/audio/audio_metrics.json
python3 $R/scripts/track_performer.py $S/frames $S/models 149 303 $S/cv/performer_track.json $S/perf_crops
python3 $R/scripts/build_digest.py $S/cv/per_frame_cv.json $S/cv/shots.json $S/audio/audio_metrics.json $S/ctx/ctx.danmaku.xml $S/cv/performer_track.json $S/digest 36
python3 $R/scripts/make_strips.py $S/frames $S/strips 6 360
# 标注和核查：由工作流完成，36 帧一块，共 13 块；脚本在 session_records/workflows/
python3 $R/scripts/collect_journals.py $S/raw <workflows>/*/journal.jsonl
python3 $R/scripts/merge_annotations.py $S/raw $S/digest/frame_signals.json $S/final
python3 $R/scripts/kinematics.py $S/final/annotations_verified.json $S/final/kinematics.json
python3 $R/scripts/relations.py  $S/final/annotations_verified.json $S/final/relations.json
python3 $R/scripts/measured.py $S/digest/frame_signals.json $S/cv/per_frame_cv.json $S/cv/shots.json $S/audio/audio_metrics.json $S/cv/performer_track.json $S/final/kinematics.json $S/final/measured.json
python3 $R/blender/camera_curves.py $R/blender/scene_spec.json $S/final/camera_solved.json
python3 $R/scripts/plot_timeline.py $S/digest/frame_signals.json $S/cv/shots.json $S/audio/audio_metrics.json $S/final/camera_solved.json $R/figures/timeline_measured.png
python3 $R/scripts/build_report.py $S/final $R/scripts/report_template.html $R/report.html
```

### B. 场景和 VMD

在 `blender/` 目录下执行。命令与 README 的"重新生成"一节相同。

```bash
python build_scene.py scene_spec.json blend/BV1ZnpG6dE8g_set.blend [--plates <原片帧目录>]
python pose_fit.py ../data/annotations_verified.json scene_spec.json posefit --chars DS,CL
python export_motion_vmd.py posefit scene_spec.json <mmd_tools> vmd --chars DS,CL --check 1
python export_camera_vmd.py blend/BV1ZnpG6dE8g_set.blend scene_spec.json <mmd_tools> vmd/camera.vmd --check vmd/camera_check.json
python assemble_vmd_preview.py blend/BV1ZnpG6dE8g_set.blend vmd <mmd_tools> blend/BV1ZnpG6dE8g_set_with_mannequins.blend [--render out --frames 1,60,...]
python render_video.py blend/BV1ZnpG6dE8g_set_with_mannequins.blend render --scale 0.333 --samples 10 --frames 1-452 --label 1
```

`scene_spec.json` 的来历：
1. set-survey 工作流里，6 个勘测代理分别负责镜头 1/2/3 的摄影机、建筑、灯光、人群。
2. 汇总代理把它们合并，输出 `consol/scene_spec.json`。
3. 我再手动设定 `rail_top_z = 5.115`，得到最终版。
4. 镜头 3 的焦距在汇总阶段从 235 mm 调整为 247.4 mm。报告正文的镜头 3 段落里仍写着 235 mm，这是旧值。

## 8. 约定（改动前务必看）

- **世界坐标**：Blender，Z 轴向上，单位米。原点在舞台圆盘中心的舞池地面上；+Y 从 DS 的包厢（−Y）指向对面看台。
- **摄影机**（`blender/camera_math.py`）：
  - 表示为 `{location, target, roll_deg, lens_mm}`，36 mm **竖向**传感器。
  - `roll_deg > 0` 表示画面内容顺时针转。
  - `project()` 与 Blender 的误差 < 0.002 px，所有重投影检查都用它。
- **补帧节奏**：重复帧在摄影机上用逐帧 CONSTANT 关键帧保持，场景属性 `hold_residues` 记录了残差。VMD 在同样的帧上停住。
- **MMD**：
  - 1 MMD 单位 = 0.08 m；Blender (x,y,z) 对应 MMD (x,z,y)；模型面朝 −Y。
  - VMD 第 0 帧 = Blender 第 1 帧。
  - 骨骼名是标准日文名：全ての親、センター、下半身、上半身、首、頭、肩、腕、ひじ、手首、足、ひざ、足首、足ＩＫ。
  - 姿势骨骼的 basis 旋转 = Rest⁻¹·R·Rest。
  - 每个镜头的站位写在"全ての親"上。
  - morph 名：まばたき、あ、笑い、にこり、∧、困る。
- **落位点**：
  - `MMD_DS_Root` 在 (−0.46, −7.285, 4.05)，面向 +Y；`MMD_CL_Root` 在 (0.12, 0.42, 0.15)。
  - 用户的 .pmx 根物体挂到这两个落位点上，变换清零即可。
- **camera.vmd 的目标点**：
  - 镜头 1 对准 DS 的脸，位置是脚底点 + 0.10 m × 朝向 + 1.45 m 高。如果对准脚底轴线，取整补偿会失效，镜头 1 的误差会变成 19.6 px。
  - 镜头 2、3 对准 CL 头部，位置是脚底点 + 1.45 m。
- **静止姿势假设**：手臂静止时向下约 40°。换成真实 .pmx 时，手臂会整体差"该模型的静止角 − 40°"。最准的做法是用 .pmx 的骨架重新拟合，`pose_fit.py` 支持换骨架。

为了把三个镜头拼成一个空间，汇总阶段做了一些取舍，完整列表在工作数据包的 `consol/cheats.json`，README 里有摘要：
- 镜头 1 的摄影机悬在舞池上空。
- 镜头 2 需要 DS 探身 40–45° 越过栏杆。
- 镜头 3 的 247 mm 是头和身体比例之间的折中。
- 镜头 2 和镜头 3 分开打光。
- 少数背景人物没有搭建。

## 9. `data/` 文件说明

| 文件 | 内容 |
|---|---|
| `annotations_verified.json` | 452 帧逐帧标注：18 个关节点（整帧归一化坐标），头部偏航/俯仰/滚转，眼、嘴、手，镜头，重复帧标记。每块都经独立核查和修补。 |
| `events_verified.json` | 微事件，带起止帧 |
| `relations.json` | 56 个关系区间 |
| `analysis_model.json` | 关系模型：thesis、nodes、edges、phases、per_character、refuted_claims、open_questions |
| `measured.json` | 推近不动点、节拍、镜头、补帧等测量结果 |
| `camera_solved.json` | 由 spec 逐帧求出的焦距、偏航、俯仰、滚转、距离 |
| `camera_solve_shot{1,2,3}.json` | 三个镜头的勘测解算 |
| `image_anchors.json` | DS 脸框、CL 头部轨迹、CL 脸框，用作重投影的目标 |
| `kinematics_summary.json` | 运动学摘要。完整的 `kinematics.json` 在工作数据包的 `final/` 里 |
| `context_cards.json`、`method_cards.json` | 报告里的语境卡片和方法卡片 |
| `meta.json` | 视频元数据，已去掉弹幕 |

## 10. 工作数据包 `BV1ZnpG6dE8g_workdir.tar.gz`

这是会话临时目录的快照。**不含**以下内容：
- 原片：`video/`、`frames/`、`strips/`、`perf_crops/` 等，以及所有由原片画面裁出或合成的 jpg/png。
- 音频。
- B站 API 原始响应和匿名 cookie：`bili/`、`ctx/`。
- 第三方二进制：`models/`、`wheels/`、`ext/`，按第 7 节重新获取。

需要原片画面时，按第 7 节 A 段重新下载并拆帧。

主要目录：

| 目录 | 内容 |
|---|---|
| `final/` | 分析定稿：标注、事件、关系、运动学、测量、摄影机解算、`scene_spec.json`、`status.json`、`context.md` |
| `raw/` | 13 块标注、核查补丁、6 个勘测片段（`survey_*.json`）、语境调研 |
| `consol/` | 汇总代理的 `scene_spec.json`、`cheats.json`、求解脚本 |
| `cam1/`、`s2cam/`、`s3cam/`、`arch/`、`light/`、`light2/`、`crowd/` | 各勘测专项的脚本和测量结果（图片已去掉） |
| `c01…c13/`、`v*/`、`verify*/`、`*_lens/` | 各标注块和核查代理的脚本与中间 JSON |
| `cv/`、`digest/`、`audio/` | CV 指标、每帧信号、音频特征（只有 JSON） |
| `posefit_final/`、`vmd_final/`、`blend/` | 最终姿势拟合、VMD、.blend（与仓库内容一致） |
| `render_final/` | 预览视频（如果已渲染完） |
| `session_records/workflows/` | 所有工作流脚本（.js）和运行记录 |
| `session_records/journals/` | 各工作流的 journal：每个代理的原始返回值 |

本会话的工作流运行：

| 运行 ID | 内容 |
|---|---|
| `wf_8ec0a3f5-d05` | 逐帧标注主运行（第 1–4 块）。因并发上限 2，第 4 块后停止 |
| `wf_7d467baf-e32`、`wf_009f1899-9e0` | 标注子集：第 13–9 块、第 8–5 块 |
| `wf_13a095d3-754`、`wf_783d6a68-c3f`、`wf_097fe29c-582`、`wf_e97fdb4b-36e` | 第 1–4 块的单独核查 |
| `wf_18ade5f9-3e5` | 人物关系模型：4 个视角提出关系说法，再经对抗审查 |
| `wf_f416f09c-07e` | 场景勘测：6 个专项 → 汇总 → critic |

## 11. 踩过的坑

- **ORB 测出的"滚转/推拉"是假象**：它跟随的是 DS 的身体、头发和人群，不是摄影机。时间轴图和报告已改用勘测解算的摄影机数据。
- **合并标注时**，缺失帧标为 `pending`，不要用相邻帧填补。
- **AUD（观众）编号在每块内独立**，所以运动学只追踪 DS 和 CL。
- **MediaPipe 在动漫脸上的眨眼/微笑系数恒为 0**。表情以视觉标注为准，MediaPipe 只用作关节和头部朝向的参考。
- **VMD 校验必须在新场景里做**：先 factory reset，把相机 VMD 导入到相机物体上（不能导到 rig 根上）。在已打开的 .blend 里导入时动画不生效。
- **镜头 2 的摄影机路径会穿过 DS 直立时的头部位置**，所以静止替身会把 f230 挡成黑屏。最终版改用 VMD 驱动、已经探身的人台。
- **玻璃反射伪影**：粗糙度设为 0.35，alpha 设为 0.14。
- **手指尖和头顶的系统误差**：手指尖长度设为 `HAND_TIP_UNITS = 2.1`，并降低这两类点的拟合权重。
- **会话休眠会杀掉工作流**：用 `resumeFromRunId` 续跑。
