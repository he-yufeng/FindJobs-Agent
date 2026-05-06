#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
魔搭创空间部署入口
Flask 同时提供 API 服务和前端静态文件
"""
from __future__ import annotations

import os
import sys

# 确保项目根目录在 sys.path 中
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api_server import app
from flask import send_from_directory

# 前端静态文件目录
FRONTEND_DIST = os.path.join(ROOT_DIR, 'FrontEnd', 'dist')


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """提供前端静态文件，API 路由优先"""
    # 如果是 API 路由，跳过（已在 api_server.py 中注册）
    if path.startswith('api/'):
        return app.send_static_file(path)

    # 尝试提供静态文件
    file_path = os.path.join(FRONTEND_DIST, path)
    if path and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIST, path)

    # 所有其他路由返回 index.html（SPA 路由）
    return send_from_directory(FRONTEND_DIST, 'index.html')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    print(f"Starting FindBestCareers on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=debug)
