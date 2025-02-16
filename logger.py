import logging
import os

# 日志目录（如果不存在则创建）
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 配置日志格式
log_format = "%(asctime)s %(levelname)s - %(message)s"
log_file = os.path.join(log_dir, "game.log")

# 配置日志（只精确到秒）
logging.basicConfig(
    level=logging.INFO,  # 默认记录 INFO 及以上级别日志
    format=log_format,
    datefmt="%Y-%m-%d %H:%M:%S",  # 指定只显示到秒
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler()
    ],
    force=True
)

# 获取全局 logger
logger = logging.getLogger(__name__)
