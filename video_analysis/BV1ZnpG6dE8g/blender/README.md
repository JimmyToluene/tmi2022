# BV1ZnpG6dE8g 场景重建（Blender）

《意气风发啊大肥鱼，但可别高兴得太早》里的夜店场景：贵宾包厢栏杆、下沉舞池、圆形小舞台、带台灯的卡座阶梯、玻璃栏杆夹层、顶光束与烟雾、城市夜景、人群，以及三个镜头的摄影机运动。**两位角色不建模**：场景里只放了 MMD 模型的落位点和中性灰色替身，导入你们自己的 MMD 模型后对位即可。

## 文件

| 文件 | 用途 |
|---|---|
| `scene_spec.json` | 场景的全部度量参数（米 / 度 / 十六进制颜色）。改场景就改这里，然后重新生成。 |
| `build_scene.py` | 从 `scene_spec.json` 生成 `.blend`。 |
| `pose_reference.json` | 逐帧标注的 2D 关键点经对应镜头反投影得到的 3D 关节参考点。 |
| `pose_reference.py` | 生成上面的文件。 |
| `render_checks.py` | 渲染指定帧，与原片并排、半透明叠加、描边对比。 |
| `camera_math.py` | 统一的摄影机约定与投影函数；与 Blender 的 `world_to_camera_view` 误差 < 0.002 px。 |
| `checks/` | 对位检查图（原片｜渲染｜50% 叠加｜渲染边缘描在原片上）。 |

生成（Blender 4.2 以上，或 `pip install bpy`）：

```bash
blender -b -P build_scene.py -- scene_spec.json BV1ZnpG6dE8g_set.blend --pose pose_reference.json
# 或
python build_scene.py scene_spec.json BV1ZnpG6dE8g_set.blend --pose pose_reference.json --engine EEVEE
```

## 约定

- 1 Blender 单位 = 1 米，Z 轴向上。
- 原点在圆形舞台中心的舞池地面（z = 0）。+Y 从 DS 的包厢指向对面，包厢在 −Y 一侧。
- 帧率 30 fps，帧号与原视频完全一致（f1–f452）。原片以 24 fps 生成，补帧到 30 fps：每 5 帧中 `f % 5 == 2` 的那一帧是复制帧。
- 时间轴标记 `Shot1` / `Shot2` / `Shot3` 分别位于 f1、f149、f304，并绑定了对应摄影机，播放时会自动切换镜头。`beat` 标记是配乐节拍（120 BPM，每 15 帧一拍）。
- 摄影机使用 36 mm 竖向传感器（`sensor_fit = VERTICAL`），竖向视角 = 2·atan(18 / 焦距)。

## 集合

| 集合 | 内容 |
|---|---|
| Architecture | 舞池地面、舞台、阶梯、包厢、栏杆与玻璃、夹层、墙体、天花 |
| Props | 卡座桌与台灯（自发光加少量点光）、城市夜景背板、镜头 3 的漂浮光点 |
| Lights | 顶光束、氛围蓝光、各镜头的主光与轮廓光（按镜头开关，已打关键帧） |
| Atmosphere | 体积雾（Principled Volume） |
| Crowd / CrowdVariants | 通用人台的集合实例：12 种变体（垂手 / 举手 / 坐姿 × 不同节拍相位），按节拍上下律动；颜色由 Object Info › Random 从调色板取 |
| Cameras | `CAM_Shot1/2/3`，位置、朝向、滚转、焦距、对焦距离逐关键帧 |
| MMD anchors | `MMD_DS_Root`、`MMD_CL_Root`（脚底落位点，已朝向目标）与头部参考点 |
| Stand-ins | 中性灰色替身，导入 MMD 后隐藏 |
| Pose reference | `POSE_<角色>_<关节>` 动画空物体，仅视口可见，不参与渲染 |

## 导入 MMD 模型

1. 安装 MMD Tools 扩展（Blender 4.2+：编辑 › 偏好设置 › 获取扩展，搜索 “MMD Tools”）。
2. 文件 › 导入 › MikuMikuDance Model (.pmx)，缩放保持 0.08，使模型身高约为 1.6 m。
3. 选中 MMD Tools 生成的模型根物体，再加选 `MMD_DS_Root`，执行 物体 › 父级 › 物体（无反向）。然后把模型根物体的位置和旋转清零，模型就站在落位点上并朝向正确。MMD 模型导入后默认面向 −Y，落位点已按此旋转。
4. CL 的模型同样处理，对 `MMD_CL_Root` 操作。
5. 隐藏 `Stand-ins` 集合。
6. 动作有两种做法：
   - 导入 VMD 动作。
   - 对照 `Pose reference` 里的关节点手动摆姿势。参考点在画面里与原片逐帧重合，深度方向是近似值，落在通过角色根部、正对镜头的竖直平面上。

### 镜头里的角色调度

- 镜头 1（f1–148）：DS 站在包厢栏杆后，面向摄影机，双前臂交叠搭在扶手上，身体略前倾。摄影机从舞池一侧的半空推近（dolly，不是变焦）。
- 镜头 2（f149–303）：摄影机在 DS 身后偏上，越过她的肩看向舞池。CL 在舞台中央，面向包厢方向随节拍扭胯。
- 镜头 3（f304–452）：摄影机在 CL 前方、略高于她的视线，向下看，手持式左右摇摆。

## 渲染

- 默认使用 EEVEE，已开启体积阴影和光线追踪；也可切换到 Cycles。
- 色彩管理为 AgX，曝光值见 `scene_spec.json` 的 `world.exposure`。
- 对位检查：

```bash
python render_checks.py BV1ZnpG6dE8g_set.blend <原片帧目录> checks 1,74,148,200,260,303,304,380,452
```

<!-- MEASURED-SECTION -->
