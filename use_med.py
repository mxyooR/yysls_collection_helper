import cv2
import numpy as np
import time
import keyboard
import pyautogui
import os
from find import FindGoods
from logger import logger
import pyuac

class AutoMed:
    def __init__(self, window_name="燕云十六声", med_choice="med1"):
        self.finder = FindGoods(window_name=window_name)
        self.med_choice = med_choice  # 用户选择药物1或药物2 ("med1" 或 "med2")
        # 尝试加载 OCR 模型（延迟加载在 finder 中）
        _ = self.finder.ocr(self.finder.capture_game_screen())

    def multi_scale_template_match(self, img, template, threshold=0.8):
        """在不同缩放比例下匹配模板，返回最佳匹配的 (max_val, best_loc, best_template)"""
        best_max_val = 0
        best_loc = None
        best_template = None
        scales = [0.8, 0.9, 1.0, 1.1, 1.2]
        for scale in scales:
            resized = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if resized.shape[0] > img.shape[0] or resized.shape[1] > img.shape[1]:
                continue
            res = cv2.matchTemplate(img, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > best_max_val:
                best_max_val = max_val
                best_loc = max_loc
                best_template = resized
        if best_max_val >= threshold:
            return best_max_val, best_loc, best_template
        else:
            return None, None, None

    def start_med(self):
        logger.info("开始执行自动服药")
        keyboard.press_and_release('b')
        time.sleep(0.5)

        # 获取图像及窗口左上角偏移
        img, win_left, win_top = self.finder.capture_total_screen()
        #cv2.imwrite('screenshot.png', img)
        if img is None:
            logger.warning("未能截取窗口")
            return

        # 3. 对图片1进行匹配，尝试tool.png和tool2.png
        for template_path in ["image/tool.png", "image/tool2.png"]:
            if not os.path.exists(template_path):
                logger.warning(f"模板不存在: {template_path}")
                continue
            template = cv2.imread(template_path, cv2.IMREAD_COLOR)
            max_val, best_loc, best_temp = self.multi_scale_template_match(img, template, threshold=0.8)
            if best_loc is not None:
                click_x = win_left + best_loc[0] + best_temp.shape[1] // 2
                click_y = win_top + best_loc[1] + best_temp.shape[0] // 2
                logger.info(f"匹配到模板 {template_path}，位置：{best_loc}，匹配分数：{max_val}")
                pyautogui.click(click_x, click_y)
                time.sleep(0.5)
                break  # 若有一个匹配成功，则跳出循环
        else:
            logger.warning("未匹配到任何工具模板")


        img, win_left, win_top = self.finder.capture_total_screen()


        a=False
        # 4. OCR识别“消耗物”，定位并点击
        if self.finder.ocr_model is None:
            _ = self.finder.ocr(img)
        results = self.finder.ocr_model.readtext(img, detail=1) if self.finder.ocr_model else []
        for (bbox, text, conf) in results:
            words = text.strip().split()
            indices = [i for i, w in enumerate(words) if w == "消耗品"]
            if indices:
                idx = indices[1] if len(indices) >= 2 else indices[0]
                logger.info(f"识别到目标词‘消耗品’，文本：{words}，选择第{idx+1}个")
                pts = np.array(bbox, dtype=np.int32)
                min_x = np.min(pts[:, 0])
                max_x = np.max(pts[:, 0])
                min_y = np.min(pts[:, 1])
                max_y = np.max(pts[:, 1])
                total_width = max_x - min_x
                word_width = total_width / len(words) if words else total_width
                target_cx = min_x + word_width * (idx + 0.5)
                target_cy = (min_y + max_y) / 2
                pyautogui.click(win_left + int(target_cx), win_top + int(target_cy))
                time.sleep(0.5)
                a=True
                break
        
        if not a:
            logger.warning("未找到消耗品")
            return
        
        time.sleep(1)
        img, win_left, win_top = self.finder.capture_total_screen()
        #cv2.imwrite('screenshot.png', img)
        # 5. 根据用户选择，使用多尺度匹配匹配对应药物模板并点击
        logger.info(f"用户选择的药物：{self.med_choice}")
        if self.med_choice == "med1":
            template2_path = "image/med_template_med1.png"
        elif self.med_choice == "med2":
            template2_path = "image/med_template_med2.png"
        else:
            logger.warning("无效的药物选择，默认采用药物1模板")
            template2_path = "image/med_template_med1.png"
        
        if not os.path.exists(template2_path):
            logger.warning(f"模板图片2不存在: {template2_path}")
            return
        else:
            template2 = cv2.imread(template2_path, cv2.IMREAD_COLOR)
            max_val2, best_loc2, best_temp2 = self.multi_scale_template_match(img, template2, threshold=0.6)
            if best_loc2 is not None:
                click_x2 = win_left + best_loc2[0] + best_temp2.shape[1] // 2
                click_y2 = win_top + best_loc2[1] + best_temp2.shape[0] // 2
                logger.info(f"匹配到模板图片2，位置：{best_loc2}，匹配分数：{max_val2}")
                pyautogui.click(click_x2, click_y2)
                time.sleep(0.5)
            else:
                logger.warning("未匹配到模板图片2")


        # 6. 按下f键
        logger.info("按下f键食用")
        keyboard.press_and_release('f')
        time.sleep(0.5)

        # 7. 按下b键退出
        logger.info("按下b键退出")
        keyboard.press_and_release('b')

# 对外接口
def start_med(med):
    automed = AutoMed(med_choice=med)
    automed.start_med()

if __name__ == "__main__":
    if not pyuac.isUserAdmin():
        pyuac.runAsAdmin()
    else:
        start_med(med="med1")
