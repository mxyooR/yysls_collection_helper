import time
import configparser
import pyuac
import sys
import logging
from check import GameWindowChecker
from find import FindGoods
from logger import logger
import urllib
import sys
import globals  # 新增导入



# 读取配置
config = configparser.ConfigParser()
with open("config.ini", "r", encoding="utf-8") as config_file:
    config.read_file(config_file)
COLLECTIBLE_NAME = config["Settings"]["collectible_name"]
LIKE_OPERATION = int(config["Settings"]["like_operation"])
GOODS_NAME_1 = config["Settings"]["goods_name_1"]
GOODS_NAME_2 = config["Settings"]["goods_name_2"]
NEED_PUSH = config["Settings"]["need_push"]
if NEED_PUSH == "1":
    PUSH_DEVICECODE = config["Settings"]["push_devicecode"]  # 修改：从config读取 devicecode


# 采集次数及状态初始值
cnt = 0

goods1 = 0
goods2 = 0
last_collect_time = None  # 新增初始化 last_collect_time

# 删除原有collector_running定义
# collector_running = True

def get_openssl_version() -> int:
    """
    获取openssl版本号
    :return: OpenSSL 的版本号。
    """
    try:
        import ssl
    except ImportError:
        sys.exit("Openssl Lib Error !!")
        # return -99
        # 建议直接更新Python的版本，有特殊情况请提交issues
    temp_list = ssl.OPENSSL_VERSION_INFO
    return int(f"{str(temp_list[0])}{str(temp_list[1])}{str(temp_list[2])}")
def get_new_session(**kwargs):
    try:
        # 优先使用httpx，在httpx无法使用的环境下使用requests
        import httpx

        http_client = httpx.Client(timeout=20, transport=httpx.HTTPTransport(retries=10), follow_redirects=True,
                                   **kwargs)
        # 当openssl版本小于1.0.2的时候直接进行一个空请求让httpx报错

        if get_openssl_version() < 102:
            httpx.get()
    except (TypeError, ModuleNotFoundError) as e:
        import requests
        from requests.adapters import HTTPAdapter

        http_client = requests.Session()
        http_client.mount('http://', HTTPAdapter(max_retries=10))
        http_client.mount('https://', HTTPAdapter(max_retries=10))
    return http_client


http = get_new_session()
# Bark
# 修改 sc_send 函数，不再需要 devicecode 参数，直接使用全局 PUSH_DEVICECODE
def sc_send(send_title, push_message):
    # make send_title and push_message to url encode
    send_title = urllib.parse.quote_plus(send_title)
    push_message = urllib.parse.quote_plus(push_message)
    rep = http.get(
        url=f'https://api.day.app/{PUSH_DEVICECODE}/{send_title}/{push_message}'
    ).json()
    logger.info(f"推送结果：{rep.get('message')}")


class AutoCollector:
    def __init__(self, debug=False):
        self.checker = GameWindowChecker()
        self.finder = FindGoods()
        self.logged_no_collectible = False  # 只记录一次“未找到可采集物品”
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

    def start(self, debug):
        """启动自动采集"""
        global cnt, last_collect_time, goods1, goods2  # 移除collector_running的引用
        
        is_running = False
        while globals.collector_running:  # 使用globals中的采集控制变量
            if not is_running:
                if self.checker.wait_for_game_window() == True:
                    #self.finder.get_hwnd()
                    is_running = True
                    logger.info("游戏窗口在前台，开始执行任务")
                time.sleep(3)
                continue    
            result, collected_goods = self.finder.find_collectible(COLLECTIBLE_NAME, debug, LIKE_OPERATION)
            if result == 1:
                cnt += 1
                last_collect_time = time.time()
                logger.info(f"当前采集{cnt}个{COLLECTIBLE_NAME}，等待280秒（5分钟前）再次检查")
                # 更新 goods1 和 goods2
                if f"{GOODS_NAME_1}" in collected_goods:
                    goods1 += 1
                    logger.info(f"已经成功采集{GOODS_NAME_1}{goods1}次")
                if f"{GOODS_NAME_2}" in collected_goods:
                    goods2 += 1
                    logger.info(f"已经成功采集{GOODS_NAME_2}{goods2}次")
                self.logged_no_collectible = False  # 重置标记
                time.sleep(280)  # 如果采集成功，等待5分钟左右后再次检查
            elif result == 2:  # 采集失败
                time.sleep(1)
                self.finder.collect_item()
                self.logged_no_collectible = False  # 重置标记
                time.sleep(1)
            elif result == 3:  # 未找到可采集物品
                if not self.logged_no_collectible:
                    logger.info("未找到可采集物品，继续等待")
                    self.logged_no_collectible = True
                time.sleep(1)

            elif result == 4:
                logger.info(f"识别到点赞，开始执行离开操作")
                self.logged_no_collectible = False  # 重置标记
                time.sleep(1)
                if LIKE_OPERATION == 2:
                    self.finder.go_away()



# 修改 get_collect_stats 函数，返回 last_collect_time
def get_collect_stats():
    global cnt, goods1, goods2, last_collect_time
    return cnt, goods1, goods2, last_collect_time

# 修改停止采集接口，使用globals变量
def stop_collector():
    import globals
    globals.collector_running = False
    logger.info("停止采集")


def main(debug=False):
    
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    bot = AutoCollector(debug=debug)
    bot.start(debug=debug)

if __name__ == "__main__":
    debug = '--debug' in sys.argv
    # 检查是否有管理员权限
    if not pyuac.isUserAdmin():
        pyuac.runAsAdmin()
    else:
        main(debug=debug)
