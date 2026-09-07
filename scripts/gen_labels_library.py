"""Generate a self-authored skill label library (data/all_labels.csv).

Replaces the previous scraped dataset with original content written from
scratch. Same schema: level_3rd, skill_type, tags (|_-joined). This is a
reference starting set, not an exhaustive taxonomy; extend per domain needs.
"""

import csv
from pathlib import Path

# (level_3rd role, skill_type, [tags])
ROWS = [
    # Backend
    ("后端工程师", "编程语言", ["Java", "Python", "Go", "C++", "Node.js", "Kotlin", "Rust", "Scala"]),
    ("后端工程师", "框架", ["Spring", "Spring Boot", "Django", "Flask", "FastAPI", "Gin", "Express", "NestJS"]),
    ("后端工程师", "数据库", ["MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "ClickHouse", "SQLite", "TiDB"]),
    ("后端工程师", "中间件", ["Kafka", "RabbitMQ", "RocketMQ", "gRPC", "Nginx", "etcd", "ZooKeeper", "Consul"]),
    ("后端工程师", "系统能力", ["分布式系统", "微服务", "高并发", "缓存设计", "消息队列", "服务治理", "API 设计", "事务与一致性"]),
    # Frontend
    ("前端工程师", "编程语言", ["JavaScript", "TypeScript", "HTML", "CSS"]),
    ("前端工程师", "框架", ["React", "Vue", "Angular", "Svelte", "Next.js", "Nuxt", "Vite", "Webpack"]),
    ("前端工程师", "工程能力", ["组件化", "状态管理", "响应式布局", "前端性能优化", "跨端兼容", "可访问性", "SSR"]),
    # Mobile
    ("移动开发工程师", "编程语言", ["Swift", "Kotlin", "Dart", "Objective-C", "Java"]),
    ("移动开发工程师", "平台框架", ["iOS", "Android", "Flutter", "React Native", "SwiftUI", "Jetpack Compose"]),
    # Algorithm / AI
    ("算法工程师", "大模型", ["LLM 微调", "提示工程", "RAG", "Agent 框架", "模型蒸馏", "对齐与 RLHF", "推理优化", "多模态"]),
    ("算法工程师", "机器学习", ["PyTorch", "TensorFlow", "scikit-learn", "XGBoost", "特征工程", "模型评估", "强化学习", "图神经网络"]),
    ("算法工程师", "视觉语音", ["OpenCV", "目标检测", "图像分割", "OCR", "语音识别", "TTS"]),
    ("算法工程师", "推荐搜索", ["召回排序", "向量检索", "FAISS", "用户画像", "点击率预估", "搜索引擎"]),
    # Data
    ("数据工程师", "数据平台", ["Hadoop", "Spark", "Flink", "Hive", "Doris", "Druid", "Presto", "dbt"]),
    ("数据工程师", "数据建模", ["数仓分层", "维度建模", "数据血缘", "数据质量", "ETL 设计", "指标体系"]),
    ("数据分析师", "分析工具", ["SQL", "Python", "Pandas", "NumPy", "Tableau", "Power BI", "Excel"]),
    # Infra / SRE
    ("运维工程师", "云原生", ["Kubernetes", "Docker", "Helm", "Service Mesh", "Istio", "Knative", "容器网络"]),
    ("运维工程师", "CI/CD", ["GitHub Actions", "Jenkins", "GitLab CI", "ArgoCD", "Terraform", "Ansible"]),
    ("运维工程师", "可观测", ["Prometheus", "Grafana", "OpenTelemetry", "Jaeger", "ELK", "告警体系"]),
    ("SRE", "稳定性", ["容量规划", "故障演练", "应急预案", "SLA 管理", "灰度发布", "熔断限流"]),
    # Security
    ("安全工程师", "应用安全", ["OWASP Top 10", "渗透测试", "代码审计", "依赖漏洞", "WAF", "加解密"]),
    # Testing
    ("测试工程师", "自动化", ["pytest", "JUnit", "Selenium", "Playwright", "Postman", "接口测试", "性能测试"]),
    ("测试工程师", "质量保障", ["测试用例设计", "覆盖率分析", "混沌工程", "A/B 测试", "回归体系"]),
    # Product / Design
    ("产品经理", "方法论", ["需求分析", "用户调研", "原型设计", "PRD 撰写", "数据驱动", "A/B 实验", "竞品分析"]),
    ("产品经理", "工具", ["Figma", "Axure", "Notion", "Jira", "飞书", "SQL 基础"]),
    ("交互设计师", "设计能力", ["用户旅程", "信息架构", "交互规范", "可用性测试", "设计系统"]),
    ("视觉设计师", "工具", ["Figma", "Photoshop", "Illustrator", "Sketch", "After Effects", "Blender"]),
    # Domain-specific tech
    ("量化研究员", "金融工程", ["回测框架", "因子挖掘", "风险管理", "时间序列分析", "统计套利", "高频交易"]),
    ("量化研究员", "编程", ["Python", "NumPy", "Pandas", "C++", "机器学习", "深度学习"]),
    ("嵌入式工程师", "底层", ["C", "RTOS", "ARM", "驱动开发", "交叉编译", "调试器", "总线协议"]),
    ("游戏开发工程师", "引擎", ["Unity", "Unreal", "Cocos", "Godot", "图形学基础", "物理引擎", "网络同步"]),
]

def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "all_labels.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["level_3rd", "skill_type", "tags"])
        for level, skill_type, tags in ROWS:
            writer.writerow([level, skill_type, "|_|".join(tags)])
    print(f"wrote {len(ROWS)} rows to {out}")

if __name__ == "__main__":
    main()
