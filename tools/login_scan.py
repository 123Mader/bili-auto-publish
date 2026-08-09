"""扫码登录 B站（bilitool 内核），登录态由 bilitool 持久化。"""

import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bilitool import LoginController

LoginController().login_bilibili(export=True)   # 二维码打印于终端；export 生成 cookie.json 备份
print("登录完成。可用 check_bilibili_login() 复核登录态。")
