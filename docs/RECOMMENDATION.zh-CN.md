# UST Course Vibe Match 运行与评分说明

正式实验使用 **2026 年春季（2025–26 Spring，学期代码 2530）CC25 的 15 门课**，纳入了 74 条与学期及授课教师匹配的评论。候选池、4 个开发档案、4 个测试档案和评分权重已冻结。演示、盲评材料和评分脚本已就绪，人工评分完成后才能产生推荐质量指标。

## 新版全量 CC 工作台

```bash
python3 src/build_test_preview.py --catalog recommendation/catalog.json --catalog-design workspace --output UST-Course-Vibe-Match-Workspace.html
```

打开新版时，推荐区提示设置偏好。选择工作量、兴趣、考核软偏好或硬条件后，页面即时更新推荐。切换学期和课程体系只调整候选池，清空所有偏好或按 `Reset` 会回到初始状态。课程目录入口随时可用。

兴趣区默认展示全部 14 个主题。页面上方的评论覆盖数统计的是至少有一条 USTSPACE 评论能对上完整课号、所选学期和当期授课教师的课程数。

工作台支持期中考试、期末考试、计分展示和小组作业。期中软偏好可参考评论中的勾选项。期中硬条件需要对应该学期和教师的已核实大纲。

<details>
<summary>工作台概念稿与插画提示词</summary>

完整概念稿和独立空状态插画由内置 ImageGen 生成。打包使用 `preview/workspace-sheets.png`。

> Full-screen desktop product design concept, 1440×900, for UST Vibe Match, a usable HKUST Common Core course-matching tool for students. This is the real first-visit finder screen. Design an airy, sharp editorial workspace with a near-white cool blue background, white surfaces, midnight navy text, and disciplined saturated cobalt accent. Top slim header: simple blue three-leaf/course-sheet mark, 'UST Vibe Match', and right tabs 'Find courses' and 'Course catalog'. Below, a left-aligned 42px title 'Find your Common Core' and concise 'Choose a term and tell us what you prefer.' No giant hero. Under that a slim scope row: 'Academic term' with '2026 Fall', 'Common Core curriculum' with 'All curricula', '138 courses · 9 with matching reviews'. Work area: a 350px left preference panel with 'Preferences' and 'Reset', 'Maximum workload' has Any, Low, Medium, High segments with small bar glyphs, 'Interests' with a 'Select all' link, and three concise dropdowns for 'Final exam or final test', 'Required graded presentation', 'Required group work', initially 'No preference'. Right larger workspace heading 'Your matches'. Its main element is a substantial empty state on a very pale icy-blue surface with one small centered distinctive flat geometric white stacked-course-sheet illustration with 2 thin orbit lines, blue outlines and a tiny warm amber spot. Text 'Add a preference to see matches', 'Choose a workload, interest, or assessment preference to get up to three courses.', and secondary button 'Browse the catalog'. Absolutely zero course recommendations or visible course names in this initial state. Don't add sample listings, progress steps, fake metrics, marketing copy, large imagery, or extra panels. Think contemporary independent university publication typography meets a focused course planning tool. Intentional grid, generous but efficient spacing, subtle outlines, practical native HTML/CSS/JS controls. Show full screen, crisp readable text, straight-on no perspective.

> Create a standalone small empty-state illustration that precisely matches the one in the right-hand pale-blue panel of the reference interface. Output ONLY the illustration, centered, on genuine transparent background. Three simple stacked sheets of paper in gentle isometric perspective, clean white/lavender-blue fills, 2px vivid cobalt outlines, three short pale blue lines on top paper (no real text). One thin cobalt oval orbit and one small amber dot. Compact generous margins, flat editorial geometric look, illustration occupies ~85% horizontal width; crisp on a pale ice blue #e6f0fc product interface. No grain, no gradient background, no people, no dashboard/UI, no badges or words. Horizontal landscape aspect around 2:1.

</details>

## 全量 CC 选课应用

全量版读取 2026 年 11 月 18 日收集的港科大主校区本科课程档案，覆盖 2023 Fall 至 2026 Fall 的 7 个秋春学期。280 个不同课号合并索引，保留 851 条分学期开课记录和 5,106 项按学期保存的 USTRankings 分数。

```bash
python3 src/build_test_preview.py --catalog recommendation/catalog.json --output UST-Course-Vibe-Match-All-CC.html
```

将 HTML 保存到本机，用 Chrome 或 Safari 直接打开。先选学期和自己适用的 Common Core 课程体系。在 `Find courses` 调整偏好时，推荐会即时更新。在 `Course catalog` 可按课号、课名或 CC 类别搜索，展开查看当学期的教师、资格分类、评论匹配数量和参考评分。早期学期的目录来自历史归档。USTRankings 是课程层面的标准化分数，供查阅，可能为负值，先验分数会标记 `prior only`。

兴趣区可以用 `Select all` 一次勾选全部主题，也可以用 `Clear all` 清空兴趣。两项操作都会即时更新推荐。

工作量使用分段选择。推荐卡可直接查看工作量、教学清晰度、匹配评论数和兴趣标签，展开 `Match details & sources` 查看原因和证据。

<details>
<summary>封面图与生成提示词</summary>

封面使用内置 ImageGen 生成的原创图形，构建时从 `preview/course-orbit.jpg` 嵌入离线 HTML。

> Use case: stylized-concept. Create an original wide editorial illustration for the right side of a modern university course explorer. One sculptural open book in lilac ceramic, with clean folded pages and thin brushed-chrome orbital rings passing around it, plus a few small acid-lime accents. Use a nearly black indigo studio backdrop (#151126), soft violet rim lighting, and clear silhouettes. Aim for a refined, tactile 3D design with generous negative space. Keep the main sculpture in the horizontal middle band so it works when cropped into a wide, shallow header. Landscape. No text, letters, logos, people, UI elements, or watermark.

</details>

| 学期 | 目录课程数 | 有同学期、同教师匹配评论的课程数 |
| --- | ---: | ---: |
| 2023 Fall | 114 | 64 |
| 2024 Spring | 108 | 48 |
| 2024 Fall | 115 | 62 |
| 2025 Spring | 124 | 58 |
| 2025 Fall | 111 | 51 |
| 2026 Spring | 141 | 47 |
| 2026 Fall | 138 | 9 |

学期选择器按日历年份显示，例如 `2024 Spring` 是 2023–24 学年的春季。CC25 从 2025 Fall 开始有记录，早期学期可选 `All curricula`、`4Y` 或 `CC22`。

每个学期按所有课程体系的课号并集计数。即使没有同学期、同教师的评论，课程也仍可查阅。推荐按教师分别评分，同一课号最多出现一次，并显示该次推荐对应的教师。考核硬要求需要已核实的课程大纲，证据缺失会有提示。全量应用默认使用 C 排序。下文的盲评和选版对应独立的 15 门课实验池。

如果更新了归档或评论标签，可先运行 `python3 src/build_catalog.py --archive /path/to/cc_courses_merged.json` 重建目录数据，再重新打包 HTML。

## 1. 运行演示

**发给组员或同学试用。** 把生成的 HTML 文件发过去。对方用浏览器打开文件，选一个示例或填自己的偏好，就能查看推荐。体验完点击 `Save feedback file` 下载 JSON 并发回组里。页面不会自动提交反馈。体验反馈用于检查界面和解释是否好用，正式适配评估继续使用第 3 节的盲评包。

```bash
python3 src/build_test_preview.py --output UST-Course-Vibe-Match-Test.html
```

生成的体验版默认展示 C。开发集已选出版本时，可以加 `--selection /path/to/selection.json` 生成对应版本。

**在本机运行 Python 界面。**

准备 Python 3.11 或更新版本，打开终端并进入 `1945GroupProject` 仓库根目录。推荐演示和推荐评分使用 Python 标准库。

```bash
python3 src/demo.py --pool recommendation/pool.json --version C
```

在浏览器打开 [本地演示](http://127.0.0.1:8000)。表单可以设置是否接受期末考试或期末测试、必做计分展示、必做小组作业、最大可接受工作量及感兴趣的主题。提交后显示最多三门课，展开结果卡可查看对应学期、教师和证据。运行期间保留终端窗口，用 Ctrl+C 停止。端口被占用时可在命令末尾加 `--port 8001`，再打开对应端口。

建议先选一个感兴趣的主题，看三张结果卡。再把「期末考试或期末测试」设为「必须没有」，检查当候选池里缺少证据时，页面如何解释空结果。可以把参数改成 `--version A` 或 `--version B` 查看其他方法。C 只是此处启动演示所用的版本，正式选版由开发集评分决定。

## 2. 排序怎么打分

三版先检查同一套硬条件。只有同学期、同教师的已核实考核证据能让课程通过硬条件。评论没提到某项考核时，该项保持未知。如果通过的课程不足三门，结果会少于三门。

| 版本 | 评分公式 |
| --- | --- |
| A | `E` |
| B | `0.60E + 0.30W + 0.10Q` |
| C | `0.45E + 0.225W + 0.075Q + 0.25T` |

- **E｜考核匹配。** 对用户表达的考核软偏好取平均。匹配记 1，明确不匹配记 0，未知记 0.5。
- **W｜工作量匹配。** 低、中、高分别映射到 0、0.5、1。工作量在用户可接受范围内得 1，超出时用 1 减去超出的幅度。例如可接受中等工作量，观察到高工作量，得 0.5。
- **Q｜教学清晰度。** 不清晰、评价混合、清晰分别记 0、0.5、1。没有明确证据也记 0.5，同时标为缺失。B 和 C 都使用这一项，无需额外填一个问卷问题。
- **T｜主题匹配。** 对课程主题标签和用户勾选的主题计算余弦相似度。没有选主题或课程缺少主题标签时记 0.5。

考核软偏好未填写或工作量无法判断时，对应项使用 0.5。总分并列时，先选有效偏好中缺失信息较少的课，再按完整课号排序。评论工作量与教学清晰度按同一开课记录的已知标签取众数，票数相同或工作量的众数为条件性／混合时，该项保留为未知。

## 3. 开始人工盲评

解压正式盲评包，将 `Spring2026_CC25_Blind_Review` 文件夹放在仓库旁边。也可以放在别处，并在下面的命令里指定路径。包里有 `development/` 和 `test/` 两个目录，每个目录有一份证据文档和三张表。

1. **先做开发集。** 两位组员各自打开 `development/evidence.md`，分别填写 `judgments_a.csv` 和 `judgments_b.csv`。给每个偏好档案评完池内 15 门课，包括未来可能排在前三之外的课。每位组员这个阶段评 **4 × 15 = 60** 个组合。
2. **先裁决，再看榜单。** 第三位组员将一致意见录入 `judgments_adjudicated.csv`，对分歧看原始证据并留下裁决依据。三张表都要完整，评分脚本会保留两位组员在裁决前的一致性结果。
3. **用开发集选定版本。** 运行第 4 节第一条评分命令后，保留生成的 `selection.json`。再处理测试集的两份独立评审和裁决。测试评分前保持测试榜单隐藏，并使用同一个候选池、档案、排序代码和评分方案。

| 字段 | 怎么填 |
| --- | --- |
| `profile_id`、`course_code` | 保留原值。每个组合只填一行。 |
| `hard_status` | `pass` 表示所有硬条件均已满足，或档案没有硬条件。确认不满足填 `fail`，证据不足以判断填 `unresolved`。 |
| `fit` | 通过硬条件后，所有软偏好有证据支持填 `2`，部分支持填 `1`，均不支持填 `0`。确认违反硬条件也填 `0`。缺失或冲突的证据使整体适配度无法判断时，填 `unresolved`。 |
| `notes` | 写证据不足的原因或裁决理由。`unresolved` 必须有备注。 |

请以当学期对应教师的大纲和评论原文为依据。空白是尚未评分，`unresolved` 是评过之后仍无法判断。正式盲评包已生成，直接使用即可。

若需要为同一冻结方案生成一份新的空白表，在仓库根目录运行以下命令。用新目录保存，避免覆盖已填资料。

```bash
python3 src/evaluate.py \
  --pool recommendation/pool.json \
  --profiles recommendation/profiles.json \
  --protocol recommendation/study_protocol.json \
  prepare --split development --output /tmp/vibe-development-new
```

生成测试集时将 `--split development` 改为 `--split test`，并指定不同的输出目录。

## 4. 运行推荐评分

在仓库根目录执行。若盲评包解压到其他位置，把 `packet` 改为实际目录。开发集三张表填完后，先运行开发集评分。

```bash
packet="../Spring2026_CC25_Blind_Review"
results="$packet/results"

python3 src/evaluate.py \
  --pool recommendation/pool.json \
  --profiles recommendation/profiles.json \
  --protocol recommendation/study_protocol.json \
  develop \
  --rater-a "$packet/development/judgments_a.csv" \
  --rater-b "$packet/development/judgments_b.csv" \
  --judgments "$packet/development/judgments_adjudicated.csv" \
  --selection "$results/selection.json" \
  --output "$results/development_results.json"
```

脚本先排除出现已确认硬条件违规的版本，再按开发集平均 Precision@3 选版。同分时优先选更简单的版本。测试集三张表填完后，在同一个终端用已保存的 `selection.json` 运行：

```bash
python3 src/evaluate.py \
  --pool recommendation/pool.json \
  --profiles recommendation/profiles.json \
  --protocol recommendation/study_protocol.json \
  test \
  --rater-a "$packet/test/judgments_a.csv" \
  --rater-b "$packet/test/judgments_b.csv" \
  --judgments "$packet/test/judgments_adjudicated.csv" \
  --selection "$results/selection.json" \
  --output "$results/test_results.json"
```

评分会核对冻结文件，拒绝缺行、重复行、空白或非法判分。脚本会拒绝覆盖已有结果。如果是在新的终端窗口运行测试命令，先重新设置上面的 `packet` 和 `results`。演示时可以载入开发集选出的版本：

```bash
python3 src/demo.py \
  --pool recommendation/pool.json \
  --selection "$results/selection.json"
```

## 5. 看结果和准备汇报

在 `test_results.json` 中查看每个版本的 `profiles` 和 `summary`。三版使用同一套人工裁决结果。

| 指标或字段 | 含义 |
| --- | --- |
| `precision_at_3` | 推荐到的 2 分课程数 ÷ 3。少于三门时，空位算作未命中。 |
| `recall_at_3` | 推荐到的 2 分课程数 ÷ 池中所有 2 分课程数。池内没有 2 分课时显示 `null`。 |
| `hard_violations` | 推出的课程中，被人工确认违反硬条件的数量。 |
| `missed_suitable` | 未进入前三的 2 分课程。标注它被硬筛排除（`filter`）还是排名未进前三（`rank`）。 |
| `lower_fit_recommendations` | 进入前三、但人工适配度为 0 或 1 的课程。结合漏排名单，可分析有没有较低适配的推荐挤掉更合适的课。 |
| `unresolved_in_pool`、`unresolved_recommendations` | 全池和推荐结果中证据不足、无法判定的数量。 |
| `human_agreement_before_adjudication` | 裁决前两位组员的适配度判分一致率和 Cohen’s κ。 |

汇报可展示一个成功匹配的例子和一个漏排例子。报告测试结果时说明，评估范围是冻结的 15 门课和 4 个测试档案。

评论标签的 80 条人工抽检是另一项工作。它评估 LLM 对评论的标签，两名组员分别填写 `spot_check/sheet_annotator_A.xlsx` 和 `spot_check/sheet_annotator_B.xlsx`。评分脚本也兼容已填写的 CSV。操作步骤见 [评论抽检说明](../spot_check/README.md)。

[English guide](RECOMMENDATION.md) · [冻结方案](../recommendation/study_protocol.json)
