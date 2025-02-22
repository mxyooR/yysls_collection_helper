import cv2
import mss
import numpy as np
import win32gui
from logger import logger
import keyboard
import time
import os
import easyocr  # 添加 easyocr 导入

class FindGoods:
    def __init__(self, window_name="燕云十六声"):
        self.window_name = window_name
        self.ocr_model = None  # 延迟加载
        self.goods_name = None
        self.client_area_rect = None
        self.ocr_area = None
        self.counter_area = None


    def get_window_rect(self, hwnd):
        """
        获取窗口的绝对屏幕坐标。
        返回 (left, top, right, bottom)
        """
        # 获取客户端相对坐标
        client_rect = win32gui.GetClientRect(hwnd)

        # 将 (0,0) 客户端坐标转换为屏幕绝对坐标
        client_pos_screen = win32gui.ClientToScreen(hwnd, (0, 0))
        left = client_pos_screen[0]
        top = client_pos_screen[1]

        # 客户端右下角相对坐标
        width = client_rect[2] - client_rect[0]
        height = client_rect[3] - client_rect[1]
        right = left + width
        bottom = top + height

        self.client_area_rect = (left, top, right, bottom)
        #logger.debug(f"客户端区域：{self.client_area_rect}")
        return self.client_area_rect

    def get_ocr_rect(self, hwnd):
        """
        获取窗口的客户端ocr区域、计数区域和总的客户端区域（不包括标题栏和边框）的绝对屏幕坐标。
        返回 (left, top, right, bottom)
        """

        # 获取客户端相对坐标
        client_rect = win32gui.GetClientRect(hwnd)

        # 将 (0,0) 客户端坐标转换为屏幕绝对坐标
        client_pos_screen = win32gui.ClientToScreen(hwnd, (0, 0))
        left = client_pos_screen[0]
        top = client_pos_screen[1]

        # 客户端右下角相对坐标
        width = client_rect[2] - client_rect[0]
        height = client_rect[3] - client_rect[1]
        right = left + width
        bottom = top + height

        self.client_area_rect = (left, top, right, bottom)
        # OCR 识别区域 右边一半，上下取中间三分之一
        left1 = left + width // 2
        right1 = right-width //4
        top1 = top + height // 3
        bottom1 = bottom - height // 3

        self.ocr_area = (left1, top1, right1, bottom1)
        # 计数区域 屏幕左侧三分之一
        left2 = left
        right2 =  left + width // 3
        top2 = top
        bottom2 = bottom
        self.counter_area = (left2 ,top2, right2, bottom2)
        #logger.debug(f"客户端区域：{self.client_area_rect}")
        #logger.debug(f"OCR 识别区域：{self.ocr_area}")
        #logger.debug(f"计数区域：{self.counter_area}")

        """
        logger.debug(f"客户端区域：{self.client_area_rect}")
        logger.debug(f"OCR 识别区域：{self.ocr_area}")
        """
        return self.ocr_area
    


    def capture_total_screen(self):
        """
        使用 mss 截取游戏窗口的客户端区域（不含标题栏）。
        返回：截取到的图像、左上角X、左上角Y
        """
        hwnd = win32gui.FindWindow(None, self.window_name)  # 用游戏窗口标题获取 hwnd
        #logger.debug(f"游戏窗口句柄：{hwnd}")
        if not hwnd:
            print("未找到游戏窗口")
            return None, None, None

        # 获取游戏窗口的客户端区域（不包括标题栏）
        left, top, right, bottom = self.get_window_rect(hwnd)
        width = right - left
        height = bottom - top

        with mss.mss() as sct:
            monitor = {"top": top, "left": left, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            # 转换颜色格式 BGRA -> BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            return img, left, top









    def capture_game_screen(self):
        """
        使用 mss 截取游戏窗口的采集区域（不含标题栏）。
        返回：截取到的图像、左上角X、左上角Y
        """
        hwnd = win32gui.FindWindow(None, self.window_name)  # 用游戏窗口标题获取 hwnd
        #logger.debug(f"游戏窗口句柄：{hwnd}")
        if not hwnd:
            print("未找到游戏窗口")
            return None, None, None

        # 获取游戏窗口的客户端区域（不包括标题栏）
        left, top, right, bottom = self.get_ocr_rect(hwnd)
        width = right - left
        height = bottom - top

        with mss.mss() as sct:
            monitor = {"top": top, "left": left, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            # 转换颜色格式 BGRA -> BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            return img
        

    def capture_counter(self):
        """
        使用 mss 截取游戏窗口的计数区域。
        返回：截取到的图像
        """
        left, top, right, bottom = self.counter_area
        width = right - left
        height = bottom - top

        with mss.mss() as sct:
            monitor = {"top": top, "left": left, "width": width, "height": height}
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            # 转换颜色格式 BGRA -> BGR
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            #cv2.imwrite('counter_debug.png', img)
            return img

    def collect_item(self):
        """按下 F 键采集"""
        keyboard.press("f")
        time.sleep(1)  # 采集等待时间
        keyboard.release("f")

    def go_away(self):
        """
        离开点赞人物
        """
        for _ in range(3):
            keyboard.press("d")
            time.sleep(0.5)
            keyboard.release("d")
            time.sleep(0.5)
            keyboard.press("a")
            time.sleep(0.1)
            keyboard.release("a")
            if self.find_collectible(self.goods_name,False,1) != 4:
                logger.info("已离开点赞人物，继续采集")
                break
        else:
            logger.error("仍在点赞人物附近，已尝试3次")

    def ocr(self, img):
        """
        使用 OCR 识别图像中的文字。
        返回识别到的文字
        """
        if self.ocr_model is None:
            if os.path.isdir("models") and os.listdir("models"):
                try:
                    self.ocr_model = easyocr.Reader(['ch_sim', 'en'], model_storage_directory="models/")
                except Exception as e:
                    logger.error(f"加载 models 目录下的模型失败，使用默认模型。错误: {e}")
                    self.ocr_model = easyocr.Reader(['ch_sim', 'en'])
            else:
                self.ocr_model = easyocr.Reader(['ch_sim', 'en'])
        results = self.ocr_model.readtext(img, detail=0)
        return " ".join(results)

    def find_collectible(self, goods_name: str, debug=False,like_operation=1):
        """
        查找是否有可采集物品
        返回：
        1 - 采集成功
        2 - 采集失败
        3 - 未找到采集物品
        4 - 识别到点赞
        """
        #a=time.time()

        self.goods_name = goods_name 
        img = self.capture_game_screen()
        if img is None:
            return None
        
        # 保存截图
        
        
        all_text = self.ocr(img)
        
        if debug:
            logger.debug(all_text)
            cv2.imwrite('screenshot.png', img)
        
        if '点赞' in all_text and like_operation == 2:  # 识别到点赞并且要求走开
            return 4, None
        elif all(char in all_text for char in goods_name):
            #logger.info(f"找到{goods_name}，开始采集...")
            for attempt in range(3):  # 尝试采集3次
                self.collect_item()
                img = self.capture_game_screen()  # 再次截屏检查
                all_text = self.ocr(img)
                if goods_name not in all_text:
                    logger.info(f"{goods_name} 采集完毕")
                    collected_goods = self.ocr(self.capture_counter())  # 采集完毕后读取计数区域
                    logger.debug(f"识别到的收获物信息：{collected_goods}")
                    return 1, collected_goods  # 返回采集结果和识别到的物品数量
                else:
                    logger.warning(f"{goods_name} 采集未完成，重试 {attempt + 1}/3")
            logger.warning(f"{goods_name} 采集失败")
            return 2, None
        else:
            #logger.info("未找到可采集物品")
            return 3, None



