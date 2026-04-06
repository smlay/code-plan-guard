"""Appendix D message templates."""

B01 = "计划 Schema 校验失败：{details}"
B02 = "变更文件不存在或非普通文件：{file}"
B03 = "1-hop 影响面未覆盖（共 {missing_count} 个目标）：{missing_files}"
B04 = "计划中 changes 数组为空，无效计划"
B05 = "风格规则阻断：{kind} 超过阈值（{actual}/{limit}）：{file}:{name}"
MD01 = "Markdown 计划中未找到 yaml/yml 代码块"
MD02 = "Markdown 计划包含多个 yaml/yml 代码块，仅允许一个"
