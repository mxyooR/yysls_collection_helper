import flet as ft
import configparser
from datetime import datetime, timedelta
import time
import threading
from main import main as start_collector
from main import get_collect_stats, COLLECTIBLE_NAME, LIKE_OPERATION, GOODS_NAME_1, GOODS_NAME_2, NEED_PUSH
import asyncio  # 新增导入
import queue   # 新增导入
import logging
import pyuac
from main import sc_send  # 新增：从main导入sc_send
from use_med import start_med as auto_med_start  # 新增导入自动服药接口

# 新增自定义日志处理器
class GUIHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class ConfigEditor(ft.Container):
    def __init__(self, close_dialog):
        super().__init__()
        self.close_dialog = close_dialog
        self.config = configparser.ConfigParser()
        self.config.read("config.ini", encoding="utf-8")
        
        self.collectible_name = ft.TextField(
            label="采集物名称",
            value=self.config["Settings"]["collectible_name"]
        )
        self.like_operation = ft.Dropdown(
            label="点赞操作模式",
            options=[
                ft.dropdown.Option("0", "不管点赞继续采集"),
                ft.dropdown.Option("1", "离开点赞人物")
            ],
            value=self.config["Settings"]["like_operation"]
        )
        self.goods_name_1 = ft.TextField(
            label="物品名称1",
            value=self.config["Settings"]["goods_name_1"]
        )
        self.goods_name_2 = ft.TextField(
            label="物品名称2",
            value=self.config["Settings"]["goods_name_2"]
        )
        self.need_push = ft.Dropdown(
            label="是否需要推送",
            options=[
                ft.dropdown.Option("0", "不需要"),
                ft.dropdown.Option("1", "需要")
            ],
            value=self.config["Settings"]["need_push"]
        )
        # 新增推送设备码字段
        self.push_devicecode = ft.TextField(
            label="推送设备码",
            value=self.config["Settings"].get("push_devicecode", "")
        )

    def save_config(self, e):
        self.config["Settings"]["collectible_name"] = self.collectible_name.value
        self.config["Settings"]["like_operation"] = self.like_operation.value
        self.config["Settings"]["goods_name_1"] = self.goods_name_1.value
        self.config["Settings"]["goods_name_2"] = self.goods_name_2.value
        self.config["Settings"]["need_push"] = self.need_push.value
        # 保存新增的推送设备码
        self.config["Settings"]["push_devicecode"] = self.push_devicecode.value
        with open("config.ini", "w", encoding="utf-8") as configfile:
            self.config.write(configfile)
        self.close_dialog(e)

    def build(self):
        # 移除原有“保存配置”按钮
        return ft.Column(
            width=400,
            controls=[
                self.collectible_name,
                self.like_operation,
                self.goods_name_1,
                self.goods_name_2,
                self.need_push,
                self.push_devicecode,
                # 已移除 ft.ElevatedButton("保存配置", on_click=self.save_config)
            ]
        )

# 修改 StopSettingsEditor，实现分开两个采集阈值
class StopSettingsEditor(ft.Container):
    def __init__(self, close_dialog):
        super().__init__()
        self.close_dialog = close_dialog
        self.config = configparser.ConfigParser()
        self.config.read("config.ini", encoding="utf-8")
        if "StopSettings" not in self.config:
            self.config["StopSettings"] = {
                "stop_after_minutes": "0",
                "goods1_threshold": "0",
                "goods2_threshold": "0"
            }
        self.stop_minutes = ft.TextField(
            label="定时停止（分钟，0表示不启用）",
            value=self.config["StopSettings"].get("stop_after_minutes", "0")
        )
        self.goods1_threshold = ft.TextField(
            label=f"{GOODS_NAME_1}采集阈值（0表示不启用）",
            value=self.config["StopSettings"].get("goods1_threshold", "0")
        )
        self.goods2_threshold = ft.TextField(
            label=f"{GOODS_NAME_2}采集阈值（0表示不启用）",
            value=self.config["StopSettings"].get("goods2_threshold", "0")
        )

    def save_stop_settings(self, e):
        self.config["StopSettings"]["stop_after_minutes"] = self.stop_minutes.value
        self.config["StopSettings"]["goods1_threshold"] = self.goods1_threshold.value
        self.config["StopSettings"]["goods2_threshold"] = self.goods2_threshold.value
        with open("config.ini", "w", encoding="utf-8") as configfile:
            self.config.write(configfile)
        self.close_dialog(e)

    def build(self):
        return ft.Column(
            width=400,
            controls=[
                self.stop_minutes,
                self.goods1_threshold,
                self.goods2_threshold,
                # 已移除其他按钮，使用下面的行内按钮
            ]
        )

class CollectorGUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "燕云十六声自动采集器"
        self.page.window.width = 600
        self.page.window.height = 900
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.last_collect_time = None
        self.alert_sent = False  # 新增：用于防止重复发送推送通知
        self.start_time = None  # 新增：采集开始时间

        # 初始化统计信息
        self.collect_count = 0
        self.goods1_count = 0
        self.goods2_count = 0
        
        # 状态显示组件：合并采集统计与距离上次采集时间
        self.stats_display = ft.Column()
        
        # 启动采集线程
        self.running = False
        self.collector_thread = None
        
        # 新增日志队列及日志显示框
        self.log_queue = queue.Queue()
        self.log_box = ft.TextField(multiline=True, read_only=True, height=200)
        # 添加日志处理器到根日志
        gui_handler = GUIHandler(self.log_queue)
        gui_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s - %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(gui_handler)
        # 启动日志更新线程
        threading.Thread(target=self.update_logs, daemon=True).start()

        # 新增：存储当前配置显示控件
        config = configparser.ConfigParser()
        config.read("config.ini", encoding="utf-8")
        self.config_info = ft.Text(
            f"采集物: {config['Settings']['collectible_name']}\n"
            f"操作模式: {['不管点赞继续采集', '离开点赞人物'][int(config['Settings']['like_operation'])-1]}\n"
            f"监控物品: {config['Settings']['goods_name_1']}, {config['Settings']['goods_name_2']}\n"
            f"是否推送: {['否', '是'][int(config['Settings']['need_push'])]}"
        )

        # 在主页面增加定时停止配置按钮
        self.stop_settings_button = ft.ElevatedButton("定时停止设置", on_click=self.open_stop_settings_editor)

        # 新增自动服药相关控件和变量
        self.auto_med_switch = ft.Switch(label="自动服药", value=False, on_change=self.toggle_auto_med)
        self.auto_med_dropdown = ft.Dropdown(
            label="选择药品",
            options=[
                ft.dropdown.Option("med1", "螺蛳肉"),
                ft.dropdown.Option("med2", "酱炒田螺")
            ],
            value="med1"
        )
        self.auto_med_thread = None

        self.setup_ui()

    # 新增方法：刷新配置显示
    def refresh_config(self):
        config = configparser.ConfigParser()
        config.read("config.ini", encoding="utf-8")
        self.config_info.value = (
            f"采集物: {config['Settings']['collectible_name']}\n"
            f"操作模式: {['不管点赞继续采集', '离开点赞人物'][int(config['Settings']['like_operation'])-1]}\n"
            f"监控物品: {config['Settings']['goods_name_1']}, {config['Settings']['goods_name_2']}\n"
            f"是否推送: {['否', '是'][int(config['Settings']['need_push'])]}"
        )
        self.page.update()

    def setup_ui(self):
        # 配置信息卡片
        config_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.ListTile(
                    title=ft.Text("当前配置"),
                    subtitle=self.config_info
                    ),
                    ft.Row([
                        ft.ElevatedButton(
                            "修改配置",
                            on_click=self.open_config_editor  # 直接传入方法
                        )
                    ], alignment=ft.MainAxisAlignment.END)
                ]),
                padding=10
            )
        )

        # 统计信息卡片
        stats_card = ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.ListTile(
                        title=ft.Text("采集统计"),
                        subtitle=self.stats_display
                    )
                ]),
                padding=10
            )
        )
        log_title = ft.Text("日志") # 新增日志标题
        # 控制按钮
        control_buttons = ft.Row([
            ft.ElevatedButton("开始采集", on_click=self.start_collecting),
            ft.ElevatedButton("停止采集", on_click=self.stop_collecting),
            self.stop_settings_button   # 新增按钮
        ], alignment=ft.MainAxisAlignment.CENTER)
        auto_med_controls = ft.Row([
            self.auto_med_switch,
            self.auto_med_dropdown
        ], alignment=ft.MainAxisAlignment.CENTER, spacing=20)
        self.page.add(
            ft.Column([
                config_card,
                stats_card,
                control_buttons,
                auto_med_controls,  # 新增自动服药设置控件
                log_title,
                self.log_box
            ], spacing=20)
        )

    # 修改 open_config_editor，从弹窗改为新页面
    def open_config_editor(self, e):
        # 修改返回回调，调用 refresh_config()
        def back(e):
            self.page.views.pop()
            self.refresh_config()  # 刷新主页面的配置显示
            self.page.update()
        config_editor = ConfigEditor(back)
        config_view = ft.View(
            route="/config",
            controls=[
                ft.AppBar(title=ft.Text("修改配置")),
                config_editor.build(),
                ft.Row(
                    controls=[
                        ft.ElevatedButton("返回", on_click=back),
                        ft.ElevatedButton("修改配置", on_click=config_editor.save_config)
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                )
            ]
        )
        self.page.views.append(config_view)
        self.page.go("/config")

    def open_stop_settings_editor(self, e):
        def back(e):
            self.page.views.pop()
            self.page.update()
        stop_editor = StopSettingsEditor(back)
        stop_view = ft.View(
            route="/stop_settings",
            controls=[
                ft.AppBar(title=ft.Text("定时停止设置")),
                stop_editor.build(),
                ft.Row(
                    controls=[
                        ft.ElevatedButton("返回", on_click=back),
                        ft.ElevatedButton("保存设置", on_click=stop_editor.save_stop_settings)
                    ],
                    alignment=ft.MainAxisAlignment.CENTER
                )
            ]
        )
        self.page.views.append(stop_view)
        self.page.go("/stop_settings")
        
    def update_stats(self):
        while self.running:
            cnt, goods1, goods2, last_time = get_collect_stats()
            self.collect_count = cnt
            self.goods1_count = goods1
            self.goods2_count = goods2
            self.last_collect_time = last_time  # 更新上次采集时间
            
            # 读取定时停止设置
            config_stop = configparser.ConfigParser()
            config_stop.read("config.ini", encoding="utf-8")
            stop_after_minutes = int(config_stop["StopSettings"].get("stop_after_minutes", "0"))
            goods1_threshold = int(config_stop["StopSettings"].get("goods1_threshold", "0"))
            goods2_threshold = int(config_stop["StopSettings"].get("goods2_threshold", "0"))
            
            if self.start_time:
                elapsed = datetime.now() - self.start_time
                minutes = elapsed.seconds // 60
                seconds = elapsed.seconds % 60
                time_str = f"采集已进行: {minutes}分{seconds}秒"
                if stop_after_minutes > 0 and elapsed.total_seconds() >= stop_after_minutes * 60:
                    sc_send("采集提醒", "达到设定时长，自动停止采集")
                    self.stop_collecting(None)
                    time_str += "（已定时停止）"
                if goods1_threshold > 0 and self.goods1_count >= goods1_threshold:
                    sc_send("采集提醒", f"达到设定采集{GOODS_NAME_1}掉落物数量，自动停止采集")
                    self.stop_collecting(None)
                    time_str += f"（{GOODS_NAME_1}已采集满数量）"
                elif goods2_threshold > 0 and self.goods2_count >= goods2_threshold:
                    sc_send("采集提醒", f"达到设定采集{GOODS_NAME_2}掉落物数量，自动停止采集")
                    self.stop_collecting(None)
                    time_str += f"（{GOODS_NAME_2}已采集满数量）"
            else:
                time_str = "尚未开始采集"
            
            if self.last_collect_time:
                elapsed = datetime.now() - datetime.fromtimestamp(self.last_collect_time)
                minutes = elapsed.seconds // 60
                seconds = elapsed.seconds % 60
                time_str = f"距离上次采集: {minutes}分{seconds}秒前"
                # 新增：如果距离上次采集超过10分钟且未发送提醒，则调用sc_send推送通知
                if elapsed.total_seconds() > 600 and not self.alert_sent:
                    sc_send("采集提醒", "距离上次采集超过10分钟，请检查采集状态")
                    self.alert_sent = True
                elif elapsed.total_seconds() <= 600:
                    self.alert_sent = False
            else:
                time_str = "尚未开始采集"
            
            # 更新统计显示
            self.stats_display.controls = [
                ft.Text(f"总采集次数: {self.collect_count}"),
                ft.Text(f"{GOODS_NAME_1} 采集次数: {self.goods1_count}"),
                ft.Text(f"{GOODS_NAME_2} 采集次数: {self.goods2_count}"),
                ft.Text(time_str)
            ]
            self.page.update()
            time.sleep(1)

    def start_collecting(self, e):
        import globals  # 延迟导入全局变量模块
        if not self.running:
            # 重置采集计数，避免下次启动采集使用上次数据
            global cnt, goods1, goods2, last_collect_time
            cnt = 0
            goods1 = 0
            goods2 = 0
            last_collect_time = None
            self.collect_count = 0
            self.goods1_count = 0
            self.goods2_count = 0
            self.start_time = datetime.now()  # 记录采集开始时间
            globals.collector_running = True  # 重置采集控制变量
            self.running = True
            self.collector_thread = threading.Thread(target=self.update_stats, daemon=True)
            self.collector_thread.start()
            threading.Thread(target=self.start_collector, daemon=True).start()

    def stop_collecting(self, e):
        from main import stop_collector  # 延迟导入
        if self.running:
            self.running = False
            stop_collector()  # 停止主模块采集循环
            # 如果停止采集，则关闭自动服药功能
            self.auto_med_switch.value = False
            if self.collector_thread:
                self.collector_thread.join()

    def start_collector(self):
        # 启动采集主程序
        start_collector(debug=False)

    def update_logs(self):
        while True:
            try:
                msg = self.log_queue.get(timeout=1)
                self.log_box.value += msg + "\n"
                self.page.update()
            except queue.Empty:
                pass

    def toggle_auto_med(self, e):
        if self.auto_med_switch.value:  # 开启自动服药
            self.log_box.value += "启动自动服药功能\n"
            self.page.update()
            # 启动新的线程进行定时服药
            if self.auto_med_thread is None or not self.auto_med_thread.is_alive():
                self.auto_med_thread = threading.Thread(target=self.auto_med_task, daemon=True)
                self.auto_med_thread.start()
        else:
            self.log_box.value += "关闭自动服药功能\n"
            self.page.update()

    def auto_med_task(self):
        # 等待自动采集启动且至少采集一次
        while (not self.running or self.collect_count < 1) and self.auto_med_switch.value:
            time.sleep(1)
        # 当采集开始且至少采集一次后，每10分钟执行自动服药，期间检测开关状态
        while self.auto_med_switch.value and self.running:
            self.log_box.value += "自动服药任务执行中...\n"
            self.page.update()
            auto_med_start(med=self.auto_med_dropdown.value)
            # 每10分钟一次
            for _ in range(600):
                if not (self.auto_med_switch.value and self.running):
                    break
                time.sleep(1)

def main(page: ft.Page):
    CollectorGUI(page)

if __name__ == "__main__":
   
    if not pyuac.isUserAdmin():
        pyuac.runAsAdmin()
    else:
        ft.app(target=main, view=ft.AppView.FLET_APP)
    """
    ft.app(target=main, view=ft.AppView.FLET_APP)"
     """



