"""批量导入知识库：扫描 data/knowledge/ 下各分类文件夹，自动入库。
约定：文件夹名 = category，文件夹内所有 .md 都导入该 category。

用法: python tools/import_knowledge.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import ROOT
from tools.knowledge_tools import import_markdown

KNOWLEDGE_DIR = ROOT / "data" / "knowledge"

# 各分类的问题标题层级（飞书导出层级不同）
CATEGORY_LEVEL = {
    "八股": 4,    # #### 问题
    "面经": 3,    # ### 问题
    "实习": 2,    # ## 问题（你自己整理，统一用 ##）
    "项目": 2,    # ## 问题
}


def import_all():
    """扫描所有分类文件夹，批量入库。"""
    if not KNOWLEDGE_DIR.exists():
        print(f"❌ 知识库目录不存在: {KNOWLEDGE_DIR}")
        return

    total = 0
    for category_dir in KNOWLEDGE_DIR.iterdir():
        if not category_dir.is_dir():
            continue   # 跳过非文件夹（如散落的 md）
        category = category_dir.name
        q_level = CATEGORY_LEVEL.get(category, 3)   # 默认3级
        mds = list(category_dir.glob("*.md"))
        if not mds:
            print(f"  （{category} 文件夹为空，跳过）")
            continue
        print(f"\n📂 分类 [{category}]（标题层级 {q_level}）:")
        for md in mds:
            n = import_markdown(md, category=category, q_level=q_level)
            total += n
    print(f"\n✅ 全部导入完成，共 {total} 条")


if __name__ == "__main__":
    import_all()
