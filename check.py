import time
import psutil
import win32gui
import pygetwindow as gw
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class GameWindowChecker:
    def __init__(self, game_title="燕云十六声", game_process="yysls.exe"):
        self.game_title = game_title
        self.game_process = game_process
        self.wait_time = 1  # 检查间隔（秒）
        self.max_wait = 1200  # 最大等待次数（10 分钟）

    def is_game_running(self):
        """检查游戏进程是否运行"""
        for process in psutil.process_iter(attrs=['name']):
            if process.info['name'] == self.game_process:
                return True
        return False

    def is_game_window_foreground(self):
        """检查游戏窗口是否在前台"""
        hwnd = win32gui.GetForegroundWindow()
        Text = win32gui.GetWindowText(hwnd)
        return Text == self.game_title  # 返回是否在前台

    def wait_for_game_window(self):
        """等待游戏窗口在前台"""
        if not self.is_game_running():
            log.warning("游戏未运行！")
            return False

        warn_game = False
        cnt = 0
        while not self.is_game_window_foreground():
            if not warn_game:
                warn_game = True
                log.warning("等待游戏窗口，当前窗口不是 yysls.exe")
            
            time.sleep(self.wait_time)
            cnt += 1

            if cnt == self.max_wait:
                log.warning("等待超时，请手动切换到游戏窗口！")
                return False  # 超时退出

        return True
