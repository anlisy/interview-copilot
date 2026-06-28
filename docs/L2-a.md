# L2-a：多 Agent 架构 + Supervisor 调度

## 一、目标
把 L1 的三个裸函数（出题/评分/复盘）重构成三个独立 Agent + 一个 Supervisor 调度层，
体现 Harness 的**上下文隔离 + 评估隔离**。

## 二、架构

前端 (Streamlit) ──HTTP──> 后端 (FastAPI) ├─ SessionManager (按 session_id 保活 Supervisor) └─ Supervisor (状态机调度) ├─ InterviewerAgent (出题，独立上下文) ├─ ScorerAgent (评分，与出题物理隔离) └─ ReviewerAgent (复盘)                                       ## 三、核心设计

| 设计 | 实现 |
|------|------|
| 多 Agent 隔离 | 3 个 Agent 各持独立 model + 上下文 |
| 评估隔离 | 出题者看不到评分逻辑，避免"自己评估自己" |
| 状态机调度 | core/state.py 定义合法流转 INIT→GENERATING→ASKING→SCORING→REVIEWING→FINISHED，非法跳转报错 |
| 前后端分离 | FastAPI 后端 + Streamlit 纯前端 |
| 状态跨请求保活 | SessionManager 用 session_id 常驻 Supervisor（内存字典，L2-b 换 Redis） |
| 错误码语义化 | 非法流转返回 409 / 会话不存在返回 404 |
| 出题去重 | 两步出题（规划考点→逐题生成）+ 双层去重（字符串相似度 + 技术关键词） |

## 四、踩坑记录

| 现象 | 真因 | 解决 |
|------|------|------|
| 三种题型问同一个 rerank | prompt 约束弱，模型扎堆在简历最显眼技术点 | 改两步出题法，从源头杜绝重复 |
| 同回答不同题型评分不同 | 不是 bug，是评估隔离生效（题型不同评分标准不同） | 保留，是亮点 |
| 关键词去重对 BGE 失效 | 关键词表写死，BGE 不在表内 | 改两步出题（先规划N个不同考点） |
| 前端三题显示一样 | 浏览器翻译插件把不同题翻译成相似中文 | 关闭翻译插件/无痕窗口 |
| 答题状态错乱 | 提交后用 st.button 无 rerun | 重写为标准状态机（待答态/已评分态 + st.rerun）|

## 五、关键方法论
1. **不信任模型自觉，用确定性代码兜底**：prompt 约束去重不可靠 → 两步出题。
2. **直测下游隔离边界**：前端异常时 curl 直测后端，确认后端正常，把问题锁定在前端。
3. **用调试输出代替猜测**：反复"还是一样"后加调试输出，发现是翻译插件假象。

## 六、测试覆盖
- tests/test_questions.py：去重逻辑 4 个用例
- tests/test_api.py：FastAPI 接口 + 状态机 6 个用例（mock 掉 LLM，1秒跑完）

## 七、电梯陈述
> 我把 L1 的三个裸函数重构成三个独立 Agent，每个持有自己的 model 和上下文，实现生成与评估的物理隔离——面试官出题时看不到评分逻辑，避免 Agent 自己评估自己。上层用 Supervisor 状态机约束面试流转。架构做了前后端分离，FastAPI 后端用 SessionManager 解决状态机跨无状态请求的保活，非法流转返回 409、会话不存在返回 404。出题质量上用两步法（规划考点→逐题生成）+ 双层去重保证多样性。整套有 10 个自动化测试覆盖。

## 八、下一步
- L2-b：SessionManager 内存字典 → Redis 带 TTL；配额管理
- L2-c：模型路由（不同 Agent 用不同模型）
