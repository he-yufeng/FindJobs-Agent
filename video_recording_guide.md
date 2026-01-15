# Video Recording Guide: 1-Minute Demo (凸显科研能力与项目努力)

## 🎯 **核心目标**
展示系统的**智能性**和**技术深度**，而非普通的界面操作。让观众感受到"这不是一个玩具项目，这是生产级的研究系统"。

---

## 📹 **录制设置**

### **工具推荐：**
1. **屏幕录制**: OBS Studio (免费) 或 Camtasia (付费)
2. **音频**: 高质量麦克风 或 AirPods Pro（降噪模式）
3. **分辨率**: 1920x1080, 60fps
4. **后期**: DaVinci Resolve (免费) 或 Premiere Pro

### **环境准备：**
- ✅ 关闭所有通知（勿扰模式）
- ✅ 清理桌面和浏览器标签页
- ✅ 准备好测试数据（你的真实简历PDF）
- ✅ 确保网络稳定（API调用不能卡顿）

---

## 🎬 **分镜脚本（60秒精确卡点）**

### **Scene 1: 开场 + 简历上传 (0-15秒)**

**画面操作：**
1. 打开浏览器，进入 `http://localhost:5173`
2. 点击 "Resume" 标签
3. 拖拽你的简历PDF（`HE_Yufeng_English_-_Chinese.pdf`）到上传区域
4. 显示上传进度条（如果有）

**画外音（边录边说）：**
> "Here's our system in action. I'm uploading my actual resume from Tsinghua University with ByteDance internship experience. Watch what happens next..."

**技术亮点标注（后期加字幕/箭头）：**
- 🔍 "PDF parsing with PyPDF2"
- 🧠 "LLM extraction pipeline"

---

### **Scene 2: 技能评分展示 - 凸显智能分析 (15-30秒)**

**画面操作：**
1. 等待解析完成（如果超过3秒，后期加速）
2. **慢镜头/特写**展示技能评分卡片：
   - **Python: 4/5** ⭐⭐⭐⭐ 
   - **Machine Learning: 4/5** ⭐⭐⭐⭐
   - **TensorFlow: 3/5** ⭐⭐⭐
   - **Docker: 3/5** ⭐⭐⭐
3. 鼠标悬停在某个技能上（如果有tooltip，展示evidence）

**画外音：**
> "Notice how the system doesn't just extract skills—it EVALUATES them. Python gets a 4 because I have production projects at ByteDance. TensorFlow gets a 3 because the AI detected it's mostly from coursework. This is our V4 scoring framework with evidence-based grading."

**技术亮点标注（后期字幕）：**
- ✅ "Evidence-based scoring"
- ✅ "1000+ skill taxonomy validation"
- ✅ "Mandatory downgrade rules"
- 📊 侧边显示伪代码片段（可选）：
  ```json
  {
    "Python": {
      "score": 4,
      "evidence": "Led team of 5 in microservices development"
    }
  }
  ```

---

### **Scene 3: 岗位匹配 - 展示智能推荐 (30-45秒)**

**画面操作：**
1. 点击 "Jobs" 标签
2. 显示岗位列表加载
3. **高光时刻：** 展示排序后的岗位，重点展示Top 1：
   - **Job Title**: "LLM Agent Researcher (Top Seed Program)"
   - **Match Score**: 87% 🎯 (绿色高亮)
   - **Matched Skills**: Python, PyTorch, NLP, Reinforcement Learning
4. 点击展开一个岗位，显示详细匹配原因（如果有）

**画外音：**
> "Now the magic—job matching with semantic understanding. See this Top Seed Program position with 87% match? The system detected 'PhD required' and 'NeurIPS publications' as intensity signals and automatically adjusted expectations. This isn't keyword matching from 2010—this is intelligent alignment."

**技术亮点标注：**
- 🔥 "Signal detection: PhD + Top conferences"
- 🎯 "Dynamic score calibration"
- 📈 "Match score = 60% coverage + 40% proficiency"

---

### **Scene 4: AI面试 - 展示自适应能力 (45-60秒)**

**画面操作：**
1. 点击某个岗位的 "Start Interview" 按钮
2. 显示AI欢迎语（快速略过）
3. **核心展示：** 输入一段自我介绍（提前准备好，10秒内打完或粘贴）：
   ```
   I'm a master's student specializing in NLP and multi-agent systems. 
   I've built production LLM applications at ByteDance.
   ```
4. AI返回第一个技术问题（**停留2秒让观众看清问题**）：
   > "Question 1: Design a document Q&A agent with retrieval, LLM reasoning, tool calls, and short-term memory. Explain the architecture and key interfaces."
5. 显示打字动画（输入答案，**加速2x**），输入示例：
   ```
   The agent uses a retrieval module with vector search, 
   an LLM reasoner for planning, a tool manager for external APIs, 
   and a memory buffer for context...
   ```
6. AI返回评分（**高光时刻，慢镜头**）：
   - **Score: 4/5** ⭐⭐⭐⭐
   - **Feedback**: "Solid architecture. Consider adding error handling and concurrency strategies."
   - **Strengths**: Clear module separation
   - **Improvements**: Missing retry mechanisms

**画外音：**
> "And here's the interview agent—fully adaptive. I give my introduction, it generates a technical question tailored to MY background. I answer, and boom—real-time evaluation with specific feedback. If I'm doing well, the next question gets harder. This is a 3-phase state machine with context-aware dialogue management."

**技术亮点标注：**
- 🤖 "3-phase state machine"
- 🎚️ "Dynamic difficulty adjustment"
- 📝 "5-dimension evaluation"
- 💬 "Context-aware follow-ups"

**结束画面（最后2秒）：**
- 淡出回到主界面
- 显示 Logo: **FindBestCareers** 
- Subtitle: "AI-Powered Career Intelligence"

---

## 🎨 **后期制作技巧（凸显科研深度）**

### **1. 动画标注（After Effects风格）**
在关键时刻添加：
- **箭头指向**技能评分："Evidence-based scoring ✓"
- **高亮框**围绕匹配分数："87% - Signal-adjusted"
- **代码片段悬浮**显示（半透明背景）：
  ```python
  if signal_score >= 9:
      base_score = 5  # Flagship research
  ```

### **2. 分屏对比（画中画）**
在技能评分环节，可以画中画显示：
- 左侧：你的简历原文（高亮关键句）
- 右侧：系统提取的结果
- 用箭头/动画连接两者

### **3. 数据流动画（可选）**
在简历上传后，短暂显示数据流动：
```
Resume PDF → PyPDF2 Parser → LLM Extraction → Skill Scoring → Frontend Display
     └─(1s)─┘      └─(2s)─┘           └─(3s)─┘          └─(0.5s)─┘
```

### **4. 背景音乐（轻微）**
- 选择科技感、现代感的BGM（如 "Tech Corporate" 风格）
- 音量：-20dB（不能盖过讲解）
- 在展示技能评分和匹配时音乐渐强，营造"高潮"

### **5. 转场效果**
- 简历→岗位：滑动转场
- 岗位→面试：缩放转场
- 避免花哨特效，保持专业感

---

## 📊 **凸显"科研能力"的具体手法**

### **方法1: 技术术语可视化**
在画面侧边或底部实时显示技术栈：
```
Current Process:
├─ LLM Provider: OpenAI GPT-5-mini
├─ Parsing: PyPDF2 + Regex
├─ Scoring: V4 Framework (5 iterations)
└─ API Latency: 2.3s
```

### **方法2: 对比传统方法**
在技能评分环节，快速插入对比画面：
| Traditional (❌) | FindBestCareers (✅) |
|------------------|----------------------|
| Keyword "Python" found → Yes | Python: 4/5 (Led team, production code) |
| Match = Yes/No | Match = 87% with reasoning |

### **方法3: 展示Edge Cases处理**
快速flash一些代码片段（0.5秒即可）：
```python
# Robust JSON parsing
try:
    result = json.loads(response)
except JSONDecodeError:
    result = extract_json_from_markdown(response)
    if not result:
        result = fallback_defaults()
```

### **方法4: 引用论文/框架（可选）**
在某个技术点加注释：
- "Grounded in AAAI'23 skill taxonomy"
- "Inspired by ReAct (Reasoning + Acting)"

---

## 🎤 **配音技巧（诙谐但专业）**

### **语气建议：**
- ✅ **自信但不傲慢**："Watch what happens..." (不是 "Look how amazing...")
- ✅ **略带惊叹**："Boom—real-time evaluation!" (增加感染力)
- ✅ **适度幽默**："This isn't keyword matching from 2010" (讽刺传统方法)
- ✅ **强调数字**："FOUR out of five" (加重读音)

### **停顿节奏：**
- 技能显示时：停顿1秒让观众看清
- 匹配分数出现：停顿0.5秒制造悬念
- AI评分返回：放慢语速，"Score... FOUR out of five."

---

## ✅ **最终检查清单**

录制前确认：
- [ ] 系统运行流畅（backend + frontend都启动）
- [ ] 测试一遍完整流程（确保不卡顿）
- [ ] 准备好要说的话（可以列提词卡）
- [ ] 环境安静（无背景噪音）
- [ ] 屏幕分辨率设置正确（1080p）

录制后检查：
- [ ] 画面清晰，字体可读
- [ ] 声音清晰，无杂音
- [ ] 时长控制在58-62秒（留2秒缓冲）
- [ ] 关键技术点都有展示
- [ ] 添加了必要的标注和字幕

---

## 🚀 **Pro Tip: 录制2-3个版本**

1. **Version A**: 稳重专业版（适合正式答辩）
2. **Version B**: 诙谐活泼版（适合Demo Day）
3. **Version C**: 纯技术深度版（适合技术评审）

**最终选择**时考虑你的观众是谁！

---

## 📥 **示例时间轴（精确到秒）**

```
00:00 - 00:03  开场 + 导航到Resume页面
00:03 - 00:05  上传简历文件
00:05 - 00:07  加载动画/进度条
00:07 - 00:15  展示技能评分（重点！）
00:15 - 00:17  切换到Jobs页面
00:17 - 00:22  展示匹配结果（重点！）
00:22 - 00:25  点击某个岗位详情
00:25 - 00:28  点击Start Interview
00:28 - 00:32  输入自我介绍（加速播放）
00:32 - 00:38  AI生成问题（停留展示）
00:38 - 00:45  输入答案（加速播放）
00:45 - 00:55  AI评分+反馈（重点！慢镜头）
00:55 - 00:58  淡出，显示Logo
00:58 - 01:00  结束
```

---

## 🎓 **最后的最后：展现"巨大努力"的细节**

在视频中或PPT中提及：
- ✅ "V4 scoring framework—**5 iterations** over 3 weeks"
- ✅ "Tested with **real ByteDance job postings**"
- ✅ "**80+ hours** of development and testing"
- ✅ "Handled **10+ edge cases** in JSON parsing"
- ✅ "Stress-tested with **10 concurrent API keys**"

用数字说话，让评委感受到你们的投入！💪

---

**Good luck! You've got this! 🚀**

