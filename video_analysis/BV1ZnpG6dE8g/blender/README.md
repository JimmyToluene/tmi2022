# BV1ZnpG6dE8g 场景重建与 VMD 动作（Blender + mmd_tools）

《意气风发啊大肥鱼，但可别高兴得太早》（B站 BV1ZnpG6dE8g）的夜店场景重建，外加三个 MMD 动作文件。场景包括：

- 贵宾包厢和"船头"形扶手
- 下沉舞池与圆形小舞台
- 四级卡座阶梯和 17 张台灯小桌
- 带玻璃栏杆的夹层
- 顶光束、烟雾、城市夜景
- 约 400 人的人群
- 从画面反解出的三个镜头的摄影机运动

**两位角色不建模。** 场景里只放了灰色人台，由 VMD 驱动；换成你们自己的 MMD 模型，加载同一份 VMD 即可。

## 最终交付

| 文件 | 内容 |
|---|---|
| `vmd/camera.vmd` | 三个镜头的摄影机（MMD 相机），MMD 第 0 帧 = 原片 f1，切镜为相邻两帧跳变。 |
| `vmd/DS.vmd` | DS（大肥鱼）的骨骼动作和表情 morph，452 帧。 |
| `vmd/CL.vmd` | CL（克劳德）的骨骼动作和表情 morph，452 帧。 |
| `blend/BV1ZnpG6dE8g_set_with_mannequins.blend` | 完整场景，已用 mmd_tools 把两个 VMD 加载到灰色人台上，打开即可播放预览。 |
| `blend/BV1ZnpG6dE8g_set.blend` | 只有场景和摄影机，没有人台。 |
| `scene_spec.json` | 场景的全部度量参数，单位为米 / 度 / 十六进制颜色。改场景就改这个文件，然后重新生成。 |
| `posefit/pose_DS.json`、`pose_CL.json` | 逐帧姿势拟合结果（骨骼旋转和每帧重投影误差），VMD 由它们导出。 |
| `../data/` | 逐帧标注、事件、人物关系、摄影机解算等分析数据（不含原片画面和弹幕）。 |

## 在 Blender 里使用

需要 Blender 5.0 或更高版本（文件由 5.2 保存），并安装 MMD Tools 扩展（编辑 › 偏好设置 › 获取扩展，搜索"MMD Tools"）。

1. 打开 `BV1ZnpG6dE8g_set_with_mannequins.blend`。
2. 导入角色：文件 › 导入 › MikuMikuDance Model (.pmx)，缩放保持 0.08。
3. 选中 MMD Tools 生成的模型根物体，再加选 `MMD_DS_Root`，执行 物体 › 父级 › 物体（无反向），然后把模型根物体的位置和旋转清零。CL 同样处理，父级改为 `MMD_CL_Root`。
4. 选中模型，MMD Tools 面板 › 导入 VMD，选择 `DS.vmd` 或 `CL.vmd`。缩放 0.08，帧偏移 0。
5. 隐藏或删除对应的灰色人台：`DS_mannequin` 层级（`DS_mannequin_arm`、`DS_mannequin_mesh`），CL 同理。只隐藏父级空物体不会隐藏子物体。
6. 可选：如果想用 MMD 相机代替场景里的 `CAM_Shot1/2/3`，新建一个相机，用 MMD Tools 导入 `camera.vmd`。它和场景相机逐帧一致：回读校验误差中位数为 0.2 px，最大 0.9 px。

镜头之间的站位变化（DS 在镜头 2 探身越过栏杆）已经写在"全ての親"和姿势里。模型挂到落位点一次即可，不需要按镜头移动。

## 动作是怎么做出来的

1. **逐帧标注**：452 帧逐帧标注了 18 个关节点、头部偏航 / 俯仰 / 滚转、眼睛、嘴、手。每 36 帧一块，由另一个代理独立复核并修正。
2. **姿势拟合**：在一副标准 MMD 骨架上做拟合。骨骼包括全ての親、センター、下半身、上半身、首、頭、左右的肩、腕、ひじ、手首、足、ひざ、足首，以及足ＩＫ。拟合方法是：通过反解出的摄影机，把骨架投影到画面上，对每一帧求骨骼旋转，使投影与核实过的关键点和头部角度尽量吻合。同时加上关节先验和时间平滑；镜头 1、2 里还约束了 DS 的前臂必须搭在扶手上。拟合完成后再做时间平滑。
3. **补帧节奏**：原片在某些帧上停住不动。镜头 1 每 5 帧有 2 帧重复，镜头 2、3 每 5 帧有 1 帧重复。VMD 在这些帧上同样停住。
4. **表情**：按核实过的时间线写入 morph。
   - DS：开场 f1–12 张嘴大笑（あ、笑い、にこり）。f13–29 收成闭唇笑。f59 起笑容收窄，f86 嘴角拉平，f89 起微微下撇（∧、困る）。
   - CL：镜头 2 闭眼或几乎闭眼（まばたき 0.85）。镜头 3 半垂眼、闭口微笑（まばたき 0.35、にこり 0.55）。
   - 两人全程都不眨眼。

### 实测精度

| 项目 | 结果 |
|---|---|
| 重投影误差中位数（DS 镜头 1 / DS 镜头 2 / CL 镜头 2 / CL 镜头 3） | 6.8 / 6.9 / 3.1 / 8.1 px（画面 1080×1920） |
| VMD 回读（mmd_tools 导入到新骨架后的关节位置） | 0.0 cm |
| camera.vmd 回读（镜头 1 / 2 / 3，中位数） | 0.22 / 0.05 / 0.59 px |
| 场景摄影机重投影（勘测汇总） | 镜头 1 中位 4.2 px；布局检查点中位 6.2 px |

## 需要知道的局限

- **静止姿势假设**：VMD 里的旋转是相对模型静止姿势的。这里假设手臂静止时向下约 40°，如果你们模型的静止手臂角度不同，手臂会整体差这个角度。最准的做法是把两个角色的 `.pmx` 发来，用它们自己的骨架重新拟合（`pose_fit.py` 可以换骨架）。
- **表情名称**：表情用的是标准 morph 名（まばたき、あ、笑い、にこり、∧、困る）。模型里没有的 morph 会被跳过；名字不同的，在 MMD Tools 的 morph 列表里改名即可。
- **深度精度**：动作来自单目画面。头部、躯干和手臂的大方向可靠；前后深度和手指细节是近似值。画面上看不到的部分（镜头 1 里 DS 的腿，镜头 3 里 CL 膝盖以下）保持站立，由足ＩＫ固定。
- **原片本身不一致**：原片是 AI 生成的，三个镜头在几何上并不完全一致。为了拼成同一个空间，汇总时做了这些取舍：
  - 镜头 1 的摄影机悬在舞池上空，左下角那个虚化的前景人头无法存在，所以没有搭建。
  - 镜头 2 前段，摄影机位于 DS 直立时头部所在的空间，所以她必须探身约 40° 越过栏杆，VMD 已包含这个动作。
  - 镜头 3 的 247 mm 焦距是一个折中：AI 画的 CL 头比 MMD 比例大约 26%，匹配头部大约需要 275 mm，匹配身体宽度大约需要 210 mm。
  - 舞台光斑在镜头 2 是亮白色，在镜头 3 是暗蓝色，所以按镜头分开打光。
  - 少数背景人物没有搭建，以免挡住主体。

## 约定

- 1 Blender 单位 = 1 米，Z 轴向上。原点在舞台圆盘中心的舞池地面上；+Y 从 DS 的包厢指向对面。
- 帧率 30 fps，帧号与原片完全一致（f1–f452）。时间轴标记 `Shot1` / `Shot2` / `Shot3` 位于 f1 / f149 / f304，各自绑定对应摄影机。`beat` 标记是配乐节拍：120 BPM，每 15 帧一拍。
- 摄影机使用 36 mm 竖向传感器，镜头 1 / 2 / 3 分别为 50 / 36 / 247 mm。VMD 只存整数视角，取整误差用相机距离补偿，补偿量最大 4%。
- 如需用原片做背景对位：先用 `ffmpeg -i 原视频.mp4 -vsync 0 -q:v 2 plates/f%04d.jpg` 拆帧，生成场景时加上 `--plates plates`。`.blend` 只记录帧的路径，不打包画面。
- 声音：原片配乐有版权，`.blend` 和预览视频里都没有放。

## 重新生成

依赖：`pip install bpy`（5.2），以及 mmd_tools 源码，路径记为 `<mmd_tools>`，需要额外安装它自带的 `opencc` wheel。

```bash
python build_scene.py scene_spec.json blend/BV1ZnpG6dE8g_set.blend                     # 场景
python pose_fit.py ../data/annotations_verified.json scene_spec.json posefit            # 姿势拟合
python export_motion_vmd.py posefit scene_spec.json <mmd_tools> vmd --check 1            # DS.vmd / CL.vmd
python export_camera_vmd.py blend/BV1ZnpG6dE8g_set.blend scene_spec.json <mmd_tools> vmd/camera.vmd --check cam_check.json
python assemble_vmd_preview.py blend/BV1ZnpG6dE8g_set.blend vmd <mmd_tools> blend/BV1ZnpG6dE8g_set_with_mannequins.blend
python render_video.py blend/BV1ZnpG6dE8g_set_with_mannequins.blend render --scale 0.333   # 预览视频（无声）
```

| 脚本 | 作用 |
|---|---|
| `camera_math.py` | 统一的摄影机约定和投影函数（与 Blender 的误差 < 0.002 px） |
| `build_scene.py` | 由规格文件生成场景 |
| `mmd_skeleton.py` | 标准骨架和人台 |
| `pose_fit.py` | 逐帧姿势拟合 |
| `export_motion_vmd.py` | 导出角色 VMD |
| `export_camera_vmd.py` | 导出相机 VMD |
| `assemble_vmd_preview.py` | 把 VMD 加载到人台上 |
| `render_video.py` | 按原片节奏逐帧渲染 |
| `render_checks.py` | 和原片对比（需要你自己拆出的原片帧） |
| `camera_curves.py` | 逐帧摄影机参数 |
| `pose_reference.py` | 2.5D 关节参考点 |
