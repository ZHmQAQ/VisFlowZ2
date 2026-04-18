"""
信捷 PLC 手册向量化知识库

将 PDF 手册分块、生成摘要，存储为可检索的知识库。
用于开发时快速查阅信捷 PLC 指令、软元件、通讯格式等。
"""

import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger("vmodule.knowledge")

KNOWLEDGE_DIR = Path(__file__).parent.parent.parent / "knowledge"


def extract_pdf_chunks(pdf_path: str, chunk_size: int = 1500) -> List[Dict]:
    """从 PDF 提取文本并分块

    Args:
        pdf_path: PDF 文件路径
        chunk_size: 每块最大字符数

    Returns:
        [{"page": int, "title": str, "content": str, "chunk_id": str}, ...]
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    chunks = []
    current_chapter = "未知章节"

    for page_num in range(doc.page_count):
        page = doc[page_num]
        text = page.get_text().strip()
        if not text:
            continue

        # 检测章节标题
        lines = text.split("\n")
        for line in lines[:5]:
            line = line.strip()
            # 匹配 "1 编程方式概述", "6-2-3．Modbus 通讯地址" 等
            if any(c.isdigit() for c in line[:3]) and len(line) > 3:
                if any(kw in line for kw in ["编程", "软元件", "指令", "通讯", "计数",
                                              "PID", "功能", "BLOCK", "附录", "概述"]):
                    current_chapter = line

        # 分块
        if len(text) <= chunk_size:
            chunk_id = hashlib.md5(f"p{page_num}_{text[:50]}".encode()).hexdigest()[:12]
            chunks.append({
                "page": page_num + 1,
                "title": current_chapter,
                "content": text,
                "chunk_id": chunk_id,
            })
        else:
            # 按段落分割
            paragraphs = text.split("\n\n")
            buffer = ""
            for para in paragraphs:
                if len(buffer) + len(para) > chunk_size and buffer:
                    chunk_id = hashlib.md5(f"p{page_num}_{buffer[:50]}".encode()).hexdigest()[:12]
                    chunks.append({
                        "page": page_num + 1,
                        "title": current_chapter,
                        "content": buffer.strip(),
                        "chunk_id": chunk_id,
                    })
                    buffer = para
                else:
                    buffer += "\n\n" + para if buffer else para

            if buffer.strip():
                chunk_id = hashlib.md5(f"p{page_num}_{buffer[:50]}".encode()).hexdigest()[:12]
                chunks.append({
                    "page": page_num + 1,
                    "title": current_chapter,
                    "content": buffer.strip(),
                    "chunk_id": chunk_id,
                })

    doc.close()
    return chunks


def build_knowledge_base(pdf_path: str, output_name: str = "xinje_xg_manual"):
    """构建知识库 JSON 文件

    输出结构:
      {
        "source": "2022060907404880.pdf",
        "total_chunks": 200,
        "chapters": ["1 编程方式概述", ...],
        "chunks": [
          {"chunk_id": "abc123", "page": 15, "title": "...", "content": "..."},
          ...
        ],
        "index": {
          "软元件": [chunk_ids...],
          "Modbus": [chunk_ids...],
          "寄存器": [chunk_ids...],
          ...
        }
      }
    """
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(f"开始提取 PDF: {pdf_path}")
    chunks = extract_pdf_chunks(pdf_path)
    logger.info(f"共提取 {len(chunks)} 个文本块")

    # 构建关键词索引
    keywords = [
        "软元件", "寄存器", "线圈", "继电器", "定时器", "计数器",
        "Modbus", "通讯", "通信", "串口", "地址",
        "输入", "输出", "触点", "梯形图",
        "MOV", "SET", "RST", "CMP", "AND", "OR", "LD",
        "REGR", "REGW", "COLR", "COLW", "MRGW", "MCLW",
        "功能码", "FC", "RTU", "ASCII", "TCP",
        "偏移", "保持", "八进制", "十六进制",
        "高速计数", "中断", "PID",
    ]

    index: Dict[str, List[str]] = {}
    for kw in keywords:
        matched = [c["chunk_id"] for c in chunks if kw.lower() in c["content"].lower()]
        if matched:
            index[kw] = matched

    # 收集章节
    chapters = list(dict.fromkeys(c["title"] for c in chunks))

    knowledge = {
        "source": Path(pdf_path).name,
        "total_chunks": len(chunks),
        "chapters": chapters,
        "chunks": chunks,
        "index": index,
    }

    output_path = KNOWLEDGE_DIR / f"{output_name}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(knowledge, f, ensure_ascii=False, indent=2)

    logger.info(f"知识库已保存: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")
    logger.info(f"索引关键词: {len(index)} 个，覆盖 {sum(len(v) for v in index.values())} 条引用")

    return output_path


def search_knowledge(query: str, output_name: str = "xinje_xg_manual",
                     max_results: int = 10) -> List[Dict]:
    """搜索知识库

    简单的关键词匹配搜索。后续可替换为向量检索。

    Args:
        query: 搜索关键词
        max_results: 最大返回数量

    Returns:
        匹配的文本块列表
    """
    kb_path = KNOWLEDGE_DIR / f"{output_name}.json"
    if not kb_path.exists():
        logger.warning(f"知识库不存在: {kb_path}")
        return []

    with open(kb_path, "r", encoding="utf-8") as f:
        kb = json.load(f)

    query_terms = query.lower().split()
    results = []

    for chunk in kb["chunks"]:
        content_lower = chunk["content"].lower()
        score = sum(1 for term in query_terms if term in content_lower)
        if score > 0:
            results.append({**chunk, "_score": score})

    results.sort(key=lambda x: -x["_score"])
    return results[:max_results]


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else r"D:\agentzone\2022060907404880.pdf"
    build_knowledge_base(pdf_path)
