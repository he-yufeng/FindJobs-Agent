#!/usr/bin/env python3
"""
将 Markdown 文件转换为 PDF
使用方法: python3 md_to_pdf.py <input.md> [output.pdf]
"""

import sys
import os
from pathlib import Path

try:
    import markdown
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import re
except ImportError:
    print("Error: Required libraries not installed.")
    print("Please run: pip install markdown reportlab")
    sys.exit(1)


def markdown_to_reportlab(text):
    """将 Markdown 格式转换为 ReportLab 格式"""
    # 转义特殊字符
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # 处理粗体 **text** 或 __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    
    # 处理斜体 *text* 或 _text_
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<i>\1</i>', text)
    
    # 处理代码 `code`
    text = re.sub(r'`(.+?)`', r'<font name="Courier">\1</font>', text)
    
    return text

def md_to_pdf(md_file, pdf_file=None):
    """将 Markdown 文件转换为 PDF"""
    # 读取 Markdown 文件
    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 创建 PDF 文档
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # 创建样式
    styles = getSampleStyleSheet()
    
    # 自定义样式
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor='#2c3e50',
        spaceAfter=12,
        alignment=TA_LEFT
    )
    
    heading2_style = ParagraphStyle(
        'CustomHeading2',
        parent=styles['Heading2'],
        fontSize=18,
        textColor='#34495e',
        spaceAfter=10,
        spaceBefore=16
    )
    
    heading3_style = ParagraphStyle(
        'CustomHeading3',
        parent=styles['Heading3'],
        fontSize=14,
        textColor='#555555',
        spaceAfter=8,
        spaceBefore=12
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        spaceAfter=10
    )
    
    # 构建内容
    story = []
    lines = md_content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 跳过空行
        if not line:
            story.append(Spacer(1, 6))
            i += 1
            continue
        
        # 处理标题
        if line.startswith('# '):
            text = markdown_to_reportlab(line[2:])
            story.append(Paragraph(text, title_style))
            story.append(Spacer(1, 12))
        elif line.startswith('## '):
            text = markdown_to_reportlab(line[3:])
            story.append(Paragraph(text, heading2_style))
            story.append(Spacer(1, 10))
        elif line.startswith('### '):
            text = markdown_to_reportlab(line[4:])
            story.append(Paragraph(text, heading3_style))
            story.append(Spacer(1, 8))
        elif line.startswith('---'):
            story.append(Spacer(1, 12))
        else:
            # 普通段落（处理 Markdown 格式）
            text = markdown_to_reportlab(line)
            if text:
                story.append(Paragraph(text, normal_style))
        
        i += 1
    
    # 构建 PDF
    doc.build(story)
    print(f"Successfully converted {md_file} to {pdf_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 md_to_pdf.py <input.md> [output.pdf]")
        sys.exit(1)
    
    md_file = sys.argv[1]
    if not os.path.exists(md_file):
        print(f"Error: File {md_file} does not exist")
        sys.exit(1)
    
    # 如果没有指定输出文件，使用相同的文件名但扩展名为 .pdf
    if len(sys.argv) >= 3:
        pdf_file = sys.argv[2]
    else:
        pdf_file = os.path.splitext(md_file)[0] + ".pdf"
    
    try:
        md_to_pdf(md_file, pdf_file)
    except Exception as e:
        print(f"Conversion failed: {e}")
        print("\nHint: If you have dependency issues, please run: pip install markdown reportlab")
        sys.exit(1)
