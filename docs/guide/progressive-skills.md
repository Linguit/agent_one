# Prompt 与渐进 Skill

P16 提供用户个人资产 API 和前端配置 store，最终管理侧栏由 P19 接入。

`GET /chat/configuration` 返回 `prompts`、`skills`、`selectedPromptId` 与 `selectedSkillIds`。
`PUT /chat/configuration` 仅提交后两个字段；Prompt 可选一个或为 null，Skill 可多选。
`POST /chat/prompts` 和 `PUT /chat/prompts/{id}` 提交 `label`、`content`，删除使用 `DELETE`。
删除当前 Prompt 后回退至无自定义 Prompt，平台规则继续生效；删除已选 Skill 后自动取消该选择。

Skill 通过 `POST /chat/skills` 的 multipart `file` 字段上传，文件名必须严格为 `SKILL.md`。
概念目录和标准示例为 `examples/skills/<skill-name>/SKILL.md`；上传时只选择该文件，不能将目录路径作为文件名。
文件须为 UTF-8、不超过 256 KiB，包含 YAML frontmatter 的字符串 `name`、`description` 与非空 Markdown 正文。
name 去除首尾空白并转小写，限 1–64 位字母数字及单连字符，用户内唯一；description 限 1024 字符。
拒绝重复 YAML 键、锚点、别名和非 JSON 元数据。其他 JSON 元数据会保留。
Skill 删除使用 `DELETE /chat/skills/{id}`；修改可先删除后重新上传，再显式重新选择。

每次请求由服务端组合平台安全规则、当前 Prompt 与仅含已选 Skill 名称及描述的 catalog。
模型需要正文时调用请求级 `load_skill(name)`；未选择、其他用户、已撤销或已删除 Skill 均不能加载。
示例文件不会自动注册、选中或注入正文。Prompt 和 Skill 不能改变可信 owner/tenant 或工具授权。
reasoning 仍只展示模型实际返回的内容，加载状态属于工具事件。

部署前在后端执行 Alembic 升级至 head；新增 0008 三张用户表，不自动修改本机配置或迁移开发数据库。
