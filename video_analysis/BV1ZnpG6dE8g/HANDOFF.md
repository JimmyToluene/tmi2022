# 交接文档：BV1ZnpG6dE8g 逐帧分析 + Blender 场景重建 + VMD

最后更新：2026-10-15。写给接手的人或新会话：读完就能知道做了什么、东西在哪、怎么复现、还差什么。给最终用户的使用说明是 `blender/README.md`。

## 1. 现状一览

| 项目 | 状态 |
|---|---|
| 逐帧分析：452 帧标注、事件、人物关系模型、交互报告 | 完成 |
| Blender 场景（两个角色除外）和三个镜头的摄影机 | 完成。经独立复核后打了 36 处补丁（第 5 节） |
| 交付物 `camera.vmd`、`DS.vmd`、`CL.vmd` | 完成。仓库里是 v6 版，见第 5、6 节 |
| CL 下半身随上半身摆动（用户提出的问题） | v6 已实现并实测吻合。第 3 轮独立核查在用户要求下中途停止，第 6 节 |
| 最终预览视频（540×960，无声） | 没有渲染 |
| 交接包（git bundle + 工作数据包） | 没有发出；改为推送到 GitHub，第 3 节 |

用户的需求依次是：
1. 用最细的颗粒度逐帧分析人物关系，并建模姿势和动作。
2. 在 Blender 里重建场景，人物的 MMD 模型除外。
3. 最终交付物是 VMD。用户原话写的是"VMX"，21:43 通过 AskUserQuestion 确认为 .vmd：镜头 + 两个角色的动作，在 Blender + mmd_tools 里使用；不需要 PMX 舞台，也不需要 MMD 本体版本。
4. 交接文档和全部文件的 bundle。
5. 把会话转到用户的 Workstation 上。
6. 用户补充："视频里的 Claude 下身是随着上身摆动的"。

## 2. 视频与角色

- **视频**：B站 BV1ZnpG6dE8g《意气风发啊大肥鱼，但可别高兴得太早》，UP 主：阿滴指南，链接 https://b23.tv/L8OrkqL 。
- **规格**：1080×1920 竖屏，30 fps，452 帧，15.07 s。
- **补帧**：原片以 24 fps 生成后补到 30 fps。
  - 凡 `f % 5 == 2` 的帧都和前一帧完全相同（f3 也重复 f1），共 92 帧，全片 360 张独立画面。
  - 镜头 1 的 `f % 5 == 3` 帧只是几乎不动（帧差 1.38，正常帧在 7–12 之间），但摄影机和 VMD 也按停帧处理，规则写在 `scene_spec.json` 的 `meta.hold_residues = {1:[2,3]}`。
  - 所以按停帧规则只需渲染 331 张画面。
- **三个镜头**，在 f149 和 f304 硬切：
  1. f1–148：50 mm 推轨，推向倚在包厢栏杆上的 DS（大肥鱼，蓝发女仆，约 1.58 m）。
  2. f149–303：36 mm，从 DS 身后过肩俯拍舞池，CL（克劳德，橙发白裙，约 1.60 m）站在舞台圆盘上。
  3. f304–452：247.4 mm 长焦，从 DS 包厢方向锁定 CL 的中景。
- **配乐**：120 BPM，约 15 帧一拍。`.blend` 里的 31 个 `beat` 标记是实际检测到的节拍，从 f3 开始，间隔 14–17 帧。
- **人物关系的核心结论**：
  - 共 56 条关系边：6 条已证实，47 条成立但属解读，3 条被推翻；另有 16 条常见说法被否定。
  - 物理上的高处始终属于 DS，而注视、画面占比、色调和运动的主动权在 f303→304 一次性交给了 CL。
  - 全文见 `data/analysis_model.json` 和报告。

## 3. 仓库、推送，以及怎么在 Workstation 上接着做

- **tmi2022**：分支 `claude/video-character-analysis-v6hpo4` 已推到 GitHub（之前一直 403，后来恢复）。
  - 本地的 main 已经补全为完整历史（`git fetch --unshallow`）。
- **WUCHI**（`JimmyToluene/wuchi`）：用户新建的空仓库，用来单独存放这个项目。
  - 内容是 `git subtree split -P video_analysis/BV1ZnpG6dE8g` 拆出的独立历史，推到它的 `main`。
  - 根目录就是本目录，所以 README 里的 `blender/`、`data/` 等相对路径都不变。
- **在 Workstation 上接着做，有两种方式**：
  - **带对话记录**：在 tmi2022 的本地克隆里运行：
    ```bash
    git clone https://github.com/JimmyToluene/tmi2022 && cd tmi2022
    claude auth login     # 需要 claude.ai 账号登录
    claude --teleport     # 选这个会话
    ```
    也可以在 claude.ai/code 的会话菜单里选 Open in → Terminal。
    传送只带走 git 分支和对话记录；云端临时目录（见第 10 节）里的东西不会跟过去。
  - **只要代码和数据**：`git clone https://github.com/JimmyToluene/wuchi`，开一个新会话，先让它读这份 HANDOFF。

## 4. 交付物在哪

路径相对本目录（WUCHI 的根目录；在 tmi2022 里是 `video_analysis/BV1ZnpG6dE8g/`）。

| 路径 | 内容 |
|---|---|
| `blender/vmd/camera.vmd` | 三个镜头合成的一条 MMD 相机动作。MMD 第 0 帧 = 原片 f1 |
| `blender/vmd/DS.vmd`、`CL.vmd` | 骨骼动作和表情 morph。v6 版：IK 腿、按镜头的落位抬高和脚位、CL 下半身 |
| `blender/vmd/camera_check.json` | camera.vmd 回读校验结果，逐帧 |
| `blender/blend/BV1ZnpG6dE8g_set_with_mannequins.blend` | 场景 + VMD 驱动的灰色人台。CL 人台带一个只到饰花高度的半透明短裙 |
| `blender/blend/BV1ZnpG6dE8g_set.blend` | 只有场景和摄影机 |
| `blender/scene_spec.json` | 场景度量参数，是唯一的事实来源（复核补丁之后的版本） |
| `blender/posefit/pose_{DS,CL}.json` | 逐帧骨骼旋转、重投影误差、每个镜头的 `lift_m` 和 `feet` |
| `blender/README.md` | 给用户的使用说明（中文） |
| `blender/*.py` | 场景、摄影机、跟踪、姿势、VMD 管线 |
| `data/` | 分析数据，第 9 节 |
| `data/provenance/` | 复核结论、汇总取舍、勘测片段、各轮核查报告、工作流脚本，第 9 节 |
| `report.html` | 自包含的交互报告 |
| `figures/timeline_measured.png` | 测量时间轴图 |
| `scripts/` | 分析管线 |

在线报告（私有 artifact，链接固定）：https://claude.ai/artifact/GYHgT1SjBS67qESgYBmHqj ，现在是第 4 版，状态栏写的是"已完成"。

**已经发给用户的文件**（新版出来后，旧的都作废）：

| 时间 | 文件 | 状态 |
|---|---|---|
| 18:06 | tmi2022-video-analysis.bundle（2 个提交） | 作废 |
| 18:41 | 中期成果包.zip | 作废 |
| 18:44 | 报告截图 4 张 | — |
| 19:39 | 预览视频，静止替身、临时布局 | 作废 |
| 22:07 | VMD 预览版 | 作废 |
| 22:56 | BV1ZnpG6dE8g_VMD_Blender.zip（复核前的 VMD 和 .blend） | 作废，以仓库为准 |

另外，用户曾被告知需要 Blender 4.2 以上，这是错的：`.blend` 由 5.2 保存，需要 5.0 以上。

## 5. 精度（实测）

**摄影机**

| 项目 | 结果 |
|---|---|
| camera.vmd 回读：主体附近探针点，每 3 帧测一次，共 151 帧 | 中位 0.21 px，最大 0.94 px。分镜头中位：0.22 / 0.05 / 0.59 px |
| 远离主体的前景、背景（VMD 只存整数视角，靠距离补偿） | 画面边缘：镜头 1 约 10 px，镜头 3 约 20–37 px。补偿量最大 4% |

**场景对位**（独立复核，打补丁之后）

| 镜头 | 结果 |
|---|---|
| 镜头 1 | 栏杆立柱中位 0.1 px，最大 5.7 px；DS 脸中位 3.0 px |
| 镜头 2 | 栏杆上沿中位 4–5 px，最大 21 px；CL 头部中位 5.2 px；台灯、夹层边缘、光束 0–11 px |
| 镜头 3 | CL 脸中位 12 px（其中有 CL 自身的头部运动） |

**姿势拟合**（全部关键点，中位 / p90）

| 角色、镜头 | 结果 |
|---|---|
| DS 镜头 1 | 6.6 / 24.2 px |
| DS 镜头 2 | 3.6 / 31.7 px |
| CL 镜头 2 | 3.9 / 12.1 px；去掉胯点后 3.5 / 11.7 px |
| CL 镜头 3 | 9.5 / 42.7 px；去掉胯点后 7.8 / 20.4 px |

CL 的胯点是有意降低权重的，原因见第 6 节。

**CL 下半身**（和原片跟踪对比）

| 镜头 | 结果 |
|---|---|
| 镜头 3 | 腰部横移与饰扣 r 1.00，幅度 86 px（原片 87 px）。裙点与饰花 r 0.99，152 px（原片 151 px）。裙点与颈部 r −0.40（原片 −0.40）。骨盆倾斜 25°（束腰 23°，饰花连线 32°） |
| 镜头 2 | 腰部相对胸部 r 0.99，10.7 px（原片 12.9 px）。大腿裙带相对胸部 r 1.00，30.7 px（原片 30.2 px）。倾斜 r 1.00，22.6°（原片 23.8°）。右脚踝误差中位 4.8 px（旧版 41.6 px） |

**腿和脚**（按 Blender IK 实际播放，全部 452 帧）

| 项目 | 结果 |
|---|---|
| 脚踝与足ＩＫ目标 | 0.00 cm |
| 屈膝 | DS 镜头 1 为 16–41°，镜头 2 为 21–57°；CL 镜头 2 为 26–56°，镜头 3 为 25–65° |
| 脚离地（落位抬高） | DS 11.7 cm（镜头 1）、8.3 cm（镜头 2 和画面外的镜头 3）；CL 1.0 cm（镜头 1–2）、11.5 cm（镜头 3）。旧版是没抬高但脚踝够不着目标：DS 镜头 1 每帧差 9–11 cm，CL 镜头 3 最多差 9.6 cm |

**回读**：DS.vmd、CL.vmd 用 mmd_tools 回读，关节位置误差 0.0 cm。

## 6. CL 下半身：过程与未完成的部分

**过程**
- **第 1 版（v3）**：只用束腰驱动腰部。核查发现大腿、裙子都没动，IK 腿是直的，脚浮空。
- **第 2 版（v5）**：裙子作为下半身上的钟摆，抬高落位。核查又指出了一批问题：
  - 抬高量取的是最大值，导致脚离地，膝盖从不伸直。
  - CL 镜头 2 站宽太窄，屈膝 54° 原片里没有。
  - 镜头 2 的胯部跟踪混进了滞后的下摆。
  - 骨盆倾斜取自布料，没有用刚性的束腰。
  - 下半身的扭转没有约束。
  - DS 在画面外下蹲。
  - 预览里的长锥形裙会误导人。
- **第 3 版（v6，现在仓库里的版本）**：逐条修正了这些问题，第 5 节的数字都是 v6 的。v6 未经第 3 轮核查，也不是我测的有：画面里的手到大腿轴的距离，以及 DS 镜头 2 的手臂（这条是旧问题）。

**未完成**
1. **第 3 轮独立核查**：中途停止。逐条确认第 2 轮问题已修复、找回归。
   - 第 2 轮报告：`data/provenance/reviews/cl_lowerbody_verify_round2.json`。
   - 第 3 轮工作流脚本：`data/provenance/workflows/bv1znpg6de8g-cl-lowerbody-verify3-*.js`。
2. **已知的残留问题，都已写进 README 的局限**：
   - 大腿只跟随约一半的摆动。MMD 骨架的髋关节离腰只有约 5 cm，脚又是固定的。
   - 裙子下半段的滞后（12–18 帧）要靠模型自己的裙子物理。
   - CL 镜头 2 的脚位是从斜俯视推出来的。
   - 各镜头的落位抬高，等于用脚离地来换。
3. **渲染最终视频**：
   ```bash
   cd blender
   python3 render_video.py blend/BV1ZnpG6dE8g_set_with_mannequins.blend render_final --scale 0.5 --samples 10
   ```
   每帧约 14 s，331 张。渲完核对 452 帧、15.07 s，再发给用户。用户曾被承诺一版"更高分辨率的正式视频"。
4. **在线报告**：如果改了数据，运行 `python3 scripts/build_report.py <final 目录> scripts/report_template.html report.html`，再发布到同一个 artifact 链接。
5. **待用户决定**（都还没答复）：
   1. **声音**：A 是由 Claude 做一条原创同步音轨，还没开始；B 是用户在本地用原片配上原声，命令是 `ffmpeg -i 预览.mp4 -i 原视频.mp4 -map 0:v -map 1:a -c:v copy -c:a aac -shortest 带原声.mp4`。任何交付文件都不能混入原片音频。
   2. **是否提供 DS/CL 的 .pmx**，用于按真实骨架重新拟合。`pose_fit.py` 目前用的是写死的骨架，换骨架需要先读出 .pmx 的骨骼静止位置，这部分还没实现。
   3. **帧率**：默认 30 fps，用户没确认过。
   4. **是否把 452 条英文逐帧记录翻译成中文**。

## 7. 复现管线

**环境**
- 本会话的版本：Python 3.13，bpy 5.2.2（pip），mediapipe 1.1.0，librosa 1.0.0，scipy 1.18.1，numpy 2.5.3，opencv-python，Pillow 12.3，yt-dlp 2026.8.19，ffmpeg 6.1。
- 系统包：`apt-get install -y libegl1 libgles2 libgl1 ffmpeg fonts-dejavu fonts-wqy-zenhei`。`render_video.py` 默认加帧号，需要这两种字体，或者传 `--label 0`。
- **mmd_tools**：`git clone https://github.com/MMD-Blender/blender_mmd_tools`，本项目用的是提交 e321bd02。下文的 `<mmd_tools>` 指这个克隆目录本身。另外要 `pip install` 它 `mmd_tools/wheels/` 里的 opencc wheel。
- **MediaPipe 模型**：pose_landmarker_heavy、hand_landmarker、face_landmarker 三个 `.task` 文件。动漫脸检测用 nagadomi 的 `lbpcascade_animeface.xml`。
- **Playwright**：用预装的 Chromium，要传 `executable_path='/opt/pw-browsers/chromium'`；headless shell 那个版本对不上。

### A. 分析

`S` = 工作目录。原片等版权内容不在仓库里，需要自己下载。

```bash
mkdir -p $S/video $S/frames $S/audio $S/ctx
yt-dlp -f "bv*[vcodec^=avc1][height>=1920]+ba/bv*+ba/b" --merge-output-format mp4 -o "$S/video/video.%(ext)s" https://www.bilibili.com/video/BV1ZnpG6dE8g
ffmpeg -i $S/video/video.mp4 -vsync 0 -q:v 2 $S/frames/f%04d.jpg
ffmpeg -i $S/video/video.mp4 -ac 1 -ar 22050 $S/audio/audio22k.wav
yt-dlp --skip-download --write-subs --sub-langs all --write-comments --write-info-json -o "$S/ctx/ctx.%(ext)s" <URL>
python3 scripts/cv_metrics.py $S/frames <models> $S/cv
python3 scripts/audio_metrics.py $S/audio/audio22k.wav $S/audio/audio_metrics.json
python3 scripts/track_performer.py $S/frames <models> 149 303 $S/cv/performer_track.json $S/perf_crops
python3 scripts/build_digest.py $S/cv/per_frame_cv.json $S/cv/shots.json $S/audio/audio_metrics.json $S/ctx/ctx.danmaku.xml $S/cv/performer_track.json $S/digest 36
python3 scripts/make_strips.py $S/frames $S/strips 6 360
# 标注和核查由工作流完成，36 帧一块，共 13 块；脚本在 data/provenance/workflows/
python3 scripts/collect_journals.py $S/raw <各工作流的 journal.jsonl>
python3 scripts/merge_annotations.py $S/raw $S/digest/frame_signals.json $S/final
python3 scripts/kinematics.py $S/final/annotations_verified.json $S/final/kinematics.json
python3 scripts/relations.py $S/final/annotations_verified.json $S/final/relations.json
python3 scripts/measured.py $S/digest/frame_signals.json $S/cv/per_frame_cv.json $S/cv/shots.json $S/audio/audio_metrics.json $S/cv/performer_track.json $S/final/kinematics.json $S/final/measured.json
# analysis_model.json：关系模型工作流（integrate:model）的返回值
# meta/context_cards/method_cards/status.json 是手工整理的
cp $S/digest/frame_signals.json $S/final/
python3 blender/camera_curves.py blender/scene_spec.json data/camera_solved.json
python3 scripts/plot_timeline.py $S/digest/frame_signals.json $S/cv/shots.json $S/audio/audio_metrics.json data/camera_solved.json figures/timeline_measured.png
python3 scripts/build_report.py $S/final scripts/report_template.html report.html
```

### B. 场景和 VMD

在 `blender/` 下执行，命令和 README 的"重新生成"一节相同：

```bash
python3 build_scene.py scene_spec.json blend/BV1ZnpG6dE8g_set.blend [--plates <原片帧目录>]
python3 track_cl_body.py <原片帧目录> ../data/annotations_verified.json ../data/cl_body_tracks.json
python3 pose_fit.py ../data/annotations_verified.json scene_spec.json posefit --chars DS,CL --body ../data/cl_body_tracks.json   # 约 6 分钟
python3 export_motion_vmd.py posefit scene_spec.json <mmd_tools> vmd --chars DS,CL --check 1
python3 export_camera_vmd.py blend/BV1ZnpG6dE8g_set.blend scene_spec.json <mmd_tools> vmd/camera.vmd --check vmd/camera_check.json
python3 assemble_vmd_preview.py blend/BV1ZnpG6dE8g_set.blend vmd <mmd_tools> blend/BV1ZnpG6dE8g_set_with_mannequins.blend [--render out --frames 1,60,...]
```

`scene_spec.json` 的来历：
1. 勘测工作流 `wf_f416f09c-07e`：6 个专项代理，分别负责镜头 1/2/3 的摄影机、建筑、灯光、人群。
2. 汇总代理把它们合并，输出 `consol/scene_spec.json`；我再加上 `rail_top_z 5.115`。对应 `data/provenance/scene_spec_before_critic.json`。
3. 独立复核给出 36 处补丁（`data/provenance/set_critic_result.json`），全部采用：
   - 镜头 1 摄影机锁定在场景上；
   - 镜头 2 摄影机按近处的栏杆重新解算；
   - 12 盏夹层下照灯和对应的聚光灯从墙里移出；
   - 移焦关键帧和说明文字。
4. 另外裁剪了几个人群分区，避免人穿进栏板和台阶。
5. 场景生成脚本修了人群跳动的 bug：原来只有一半人在动。

## 8. 约定和约束

**约定**
- **世界坐标**：Z 轴向上，单位米。原点在舞台圆盘中心的舞池地面上；+Y 从 DS 的包厢（−Y）指向对面。
- **摄影机**（`blender/camera_math.py`）：
  - 表示为 `{location, target, roll_deg, lens_mm}`，36 mm 竖向传感器。
  - `roll_deg > 0` 表示画面内容顺时针转。
  - `project()` 与 Blender 的误差 < 0.002 px。
  - `pixel_ray()` 是它的逆运算，在 `pose_fit.py` 里。
- **MMD**：
  - 1 MMD 单位 = 0.08 m；Blender (x,y,z) 对应 MMD (x,z,y)；模型面朝 −Y。
  - VMD 第 0 帧 = Blender 第 1 帧。mmd_tools 以当前帧作为 VMD 的第 0 帧，所以导入前必须回到第 1 帧。
  - 姿势骨骼的 basis 旋转 = Rest⁻¹·R·Rest。
  - 骨骼用标准日文名；表情 morph 用 まばたき、あ、笑い、にこり、∧、困る。
- **全ての親 和 足ＩＫ**：
  - 全ての親 记录各镜头的落位，相对 spec 里的落位点（`MMD_<ID>_Root`），包括 `lift_m`。
  - 足ＩＫ 记录各镜头的脚位 `feet`。
  - 画面外的帧沿用最近一个已解帧的姿势和落位。
- **补帧停帧**：骨骼和摄影机在停帧上保持不动，表情 morph 不停。
- **人台骨架**：膝关节只能单向弯曲（0.5°–180°），否则 Blender 的 IK 会卡在直腿上。
- **静止姿势**：手臂静止时向下约 40°。

**约束**（来自用户要求和会话中的原则）
- 不建 PR，除非用户要求。分支名固定为 `claude/video-character-analysis-v6hpo4`。用中文回复用户。
- 不分发原片画面、裁图、音频。和原片的对比叠图只留在本地。`.blend` 只按路径挂背景帧，不打包。
- 不给角色建模，只用灰色人台。
- `report.html` 和工作流脚本里引用了公开弹幕原文，`data/meta.json` 不含弹幕列表。
- 会话休眠会杀掉后台工作流，续跑用 `resumeFromRunId`。

## 9. `data/` 文件说明

| 文件 | 内容 |
|---|---|
| `annotations_verified.json` | 452 帧逐帧标注：18 个关节点（整帧归一化坐标）、头部角度、眼、嘴、手、镜头、重复帧标记 |
| `events_verified.json` | 微事件 |
| `relations.json` | 56 个关系区间 |
| `analysis_model.json` | 关系模型：thesis、nodes、edges、phases、per_character、refuted_claims、open_questions |
| `measured.json` | 推近不动点、节拍、镜头、补帧。其中"镜头 2 推近 ×1.15、滚转 12°"是 ORB 测到的人物和人群运动，不是摄影机运动 |
| `camera_solved.json` | 由最终 spec 逐帧求出的焦距、偏航、俯仰、滚转、距离 |
| `camera_solve_shot{1,2,3}.json` | 三个镜头的勘测解算。镜头 3 那份还是旧的 235 mm |
| `image_anchors.json` | 重投影的目标点 |
| `cl_body_tracks.json` | CL 身体跟踪：镜头 3 的束腰饰扣、裙上饰花；镜头 2 的胸部、束腰、大腿裙带 |
| `kinematics_summary.json`、`context_cards.json`、`method_cards.json`、`meta.json` | 运动学摘要；报告用的语境卡片和方法卡片；视频元数据 |
| `provenance/` | 下列来源文件 |

`provenance/` 里有：
- `set_critic_result.json`：场景复核的结论和补丁。
- `consolidator_cheats.json`：汇总时做的取舍。
- `survey_*.json`：勘测片段。只有建筑、镜头 1/2/3 四份，灯光和人群片段只存在于工作流记录里。
- `scene_spec_before_critic.json`：复核前的场景规格。
- `reviews/`：交接审计、CL 下半身第 1、2 轮核查的完整报告。
- `workflows/`：本会话所有工作流脚本。

## 10. 云端临时目录（不在仓库里，会话回收后消失）

`/tmp/claude-0/-home-user-tmi2022/15258eef-8986-57e2-bae2-19a7d6419b6e/scratchpad/`：
- **原片相关**：原片、帧、裁图（版权内容）。
- **分析中间数据**：
  - `raw/`：13 块标注和补丁。
  - `cv/`、`digest/`、`audio/`：CV 指标、逐帧信号、音频特征。
  - `final/`：完整的 `kinematics.json`、`frame_signals.json`、`status.json`。
- **勘测和复核**：各专项的勘测目录，以及 `critic/`（复核时的检查脚本和数据）。
- **姿势拟合各版本**：`v2`–`v6` 的拟合、VMD、.blend 和对比渲染。
- **核查目录**：`verify*/`。
- **渲染**：渲染帧、预览视频。

需要这些的话，从第 7 节的命令重新生成，或者在会话还在时让它打包。

## 11. 踩过的坑

- **ORB 测出的"滚转/推拉"是假象**：它跟随的是人物和人群，不是摄影机。时间轴图和报告已改用勘测解算的摄影机。
- **合并标注**：缺失帧标为 `pending`，不要用相邻帧填补。
- **AUD（观众）编号在每块内独立**，所以只追踪 DS 和 CL。
- **MediaPipe 在动漫脸上的眨眼/微笑系数恒为 0**，表情以视觉标注为准。
- **VMD 回读**：导入要在第 1 帧做；相机 VMD 要导入到相机物体上。
- **时间轴标记绑定了 CAM_Shot1/2/3**：要用 MMD 相机，得先解除绑定。
- **玻璃材质**：最终版是 glass 粗糙度 0.04、alpha 0.25，window_glass 0.02 / 0.12。0.35 / 0.14 那组值只在早期预览里用过。
- **CL 的胯点标注不可靠**：它们隔着裙子，相对刚性的束腰会上下飘 ±80 px，y 方向还比束腰慢约 15 帧。所以要用跟踪数据，不能拿它们当下半身的依据。
- **骨架叠图要按 IK 腿画**：只要 VMD 里的腿由 IK 驱动，画叠图和做评估都必须按 IK 腿计算，按 FK 画会夸大效果。
- **Blender IK 在直腿附近会卡住**：给膝关节加单向弯曲限制即可。
- **仓库原来是浅克隆**：完整 bundle 打不全，先 `git fetch --unshallow origin main`。
- **Playwright 的 headless shell 版本对不上**：用 `executable_path='/opt/pw-browsers/chromium'`。
- **report.html 在手机宽度下会横向溢出**：`.edge`、`.frame-log` 加了 `minmax(0,1fr)` 和 `min-width:0`。
- **场景生成脚本的人群跳动 bug**：关键帧间隔取半个周期时，偶数周期的 sin 采样恒为 0，一半人永远不动。已改为每 1/6 周期取一个关键帧。
- **会话休眠会杀掉工作流**：用 `resumeFromRunId` 续跑。

## 12. 工作流运行记录

| 运行 ID | 内容 |
|---|---|
| `wf_8ec0a3f5-d05` | 逐帧标注主运行，第 1–4 块 |
| `wf_7d467baf-e32`、`wf_009f1899-9e0` | 标注子集：第 13–9 块、第 8–5 块 |
| `wf_13a095d3-754`、`wf_783d6a68-c3f`、`wf_097fe29c-582`、`wf_e97fdb4b-36e` | 第 1–4 块的核查 |
| `wf_18ade5f9-3e5` | 人物关系模型 |
| `wf_f416f09c-07e` | 场景勘测：6 个专项 → 汇总 → 复核 |
| `wf_9bc179de-09f` | 交接包审计：恢复测试、数字核对、遗漏和安全检查 |
| `wf_c730bc57-c3d`、`wf_6cc955c5-6e1` | CL 下半身第 1、2 轮核查 |
| `wf_8e93d0d4-1bc` | 第 3 轮核查，已中途停止 |
