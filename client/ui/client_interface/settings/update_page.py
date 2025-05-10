from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QSpacerItem, QSizePolicy, QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor
from core.font.font_manager import FontManager
from client.ui.components.customMessagebox import CustomMessageBox
import requests
import json
import os
import time
from datetime import datetime
from PySide6.QtWidgets import QMessageBox
import logging
import urllib.request
import urllib3

class UpdatePage(QWidget):
    updateFound = Signal(str, str)  # 版本号, 更新内容
    updateError = Signal(str)       # 错误信息
    addDownloadTask = Signal(str, str, int)  # 下载URL, 文件名, 文件大小
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        
        # 软件当前版本
        self.current_version = "1.0.4"
        
        # 更新源配置
        self.primary_api_url = "https://apiv2.xiaoy.asia"  # 主更新源URL
        # 次更新源 - 已知目前可能有连接问题
        self.secondary_api_url = "https://zzbuaoye.dpdns.org"  
        
        # 更新源端点
        self.primary_endpoint = "/custody-project/hdm/api/version.php"  # 新的API地址
        self.secondary_endpoint = "/HanabiDM/version.json"
        
        # 主更新源尝试次数和连接参数
        self.primary_max_retries = 3  # 主更新源重试次数更多
        self.primary_retry_delay = 1  # 秒
        
        # 次更新源尝试次数和连接参数
        self.secondary_max_retries = 2
        self.secondary_retry_delay = 1  # 秒
        
        # 代理设置
        self.use_proxy = self.config_manager.get_use_proxy() if hasattr(self.config_manager, 'get_use_proxy') else False
        self.proxy_settings = self.get_proxy_settings()
        
        # 缓存文件路径
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".hanabi_dm")
        self.cache_file = os.path.join(self.cache_dir, "update_cache.json")
        
        # 确保缓存目录存在
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # 加载缓存的版本信息
        self.cached_data = self.load_cache()
        self.has_newer_version = False
        self.current_update_source = None  # 记录当前使用的更新源
        
        # 创建主滚动区域，使整个页面可滚动
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #252526;
                width: 12px;
                margin: 0px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # 创建内容容器
        self.content_widget = QWidget()
        
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.scroll_area)
        
        # 初始化UI
        self.setup_ui()
        
        # 设置滚动区域的内容
        self.scroll_area.setWidget(self.content_widget)
        
        # 加载上次检查时间
        self.load_last_check_time()
        
        # 总是先从缓存加载数据显示
        self.update_ui_from_cache()
        
        # 如果启用了自动检查更新且符合条件，在后台自动检查
        if self.config_manager.get_auto_check_update() and self.should_check_again():
            # 延迟3秒后自动检查更新
            QTimer.singleShot(3000, lambda: self.check_update(silent=True))
    
    def should_check_again(self):
        last_check = self.cached_data.get("last_check_timestamp", 0)
        # 24小时 = 86400秒
        return time.time() - last_check > 86400
    
    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def save_cache(self, data):
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {str(e)}")
    
    def load_last_check_time(self):
        last_check = self.cached_data.get("last_check_time", "从未检查")
        self.last_check_label.setText(f"上次检查：{last_check}")
    
    def update_ui_from_cache(self):
        if not self.cached_data:
            return
            
        # 更新最后检查时间
        self.load_last_check_time()
        
        # 获取版本信息
        latest = self.cached_data.get("latest", {})
        if not latest:
            return
            
        # 检查是否有新版本
        if self.compare_versions(latest.get("version", "0.0.0"), self.current_version) > 0:
            # 有更新版本
            self.has_newer_version = True
            self.status_label.setText(f"发现新版本: {latest['version']}")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px; background-color: transparent;")
            
            # 更新更新日志
            self.update_release_notes(latest, True)
        else:
            # 已经是最新版本
            self.has_newer_version = False
            self.status_label.setText("您当前使用的已经是最新版本")
            self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px; background-color: transparent;")
            
            # 显示当前版本的更新日志
            current_version_info = None
            
            # 如果当前版本是最新版本
            if latest.get("version") == self.current_version:
                current_version_info = latest
            # 否则从历史记录中查找
            elif "history" in self.cached_data and self.current_version in self.cached_data["history"]:
                current_version_info = self.cached_data["history"][self.current_version]
            
            if current_version_info:
                self.update_release_notes(current_version_info, False)
    
    def setup_ui(self):
        # 内容布局
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        # 版本信息卡片
        version_card = self.create_card()
        version_layout = QVBoxLayout(version_card)
        version_layout.setContentsMargins(20, 20, 20, 20)
        version_layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        
        # 添加图标
        icon_label = QLabel()
        self.font_manager.apply_icon_font(icon_label, 24)
        icon_label.setText(self.font_manager.get_icon_text("ic_fluent_arrow_sync_circle_24_regular"))
        icon_label.setStyleSheet("""
            QLabel {
                color: #B39DDB;
                background-color: transparent;
            }
        """)
        title_layout.addWidget(icon_label)
        
        # 标题文本
        title_label = QLabel("软件更新")
        title_label.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(title_label)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        version_layout.addLayout(title_layout)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #333333;")
        separator.setFixedHeight(1)
        version_layout.addWidget(separator)
        
        # 当前版本信息
        version_info_layout = QHBoxLayout()
        version_info_layout.setSpacing(10)
        
        current_version_label = QLabel("当前版本：")
        current_version_label.setStyleSheet("color: #9E9E9E; font-size: 14px; background-color: transparent;")
        self.font_manager.apply_font(current_version_label)
        version_info_layout.addWidget(current_version_label)
        
        self.version_value_label = QLabel(self.current_version)
        self.version_value_label.setStyleSheet("color: #FFFFFF; font-size: 14px; background-color: transparent;")
        self.font_manager.apply_font(self.version_value_label)
        version_info_layout.addWidget(self.version_value_label)
        
        version_info_layout.addStretch()
        
        # 最后检查时间
        self.last_check_label = QLabel("上次检查：从未检查")
        self.last_check_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
        self.font_manager.apply_font(self.last_check_label)
        version_info_layout.addWidget(self.last_check_label)
        
        version_layout.addLayout(version_info_layout)
        
        # 添加代理设置提示（如果启用）
        if self.use_proxy and self.proxy_settings:
            proxy_label = QLabel(f"已启用代理服务器进行更新")
            proxy_label.setStyleSheet("color: #64B5F6; font-size: 12px; background-color: transparent;")
            self.font_manager.apply_font(proxy_label)
            version_layout.addWidget(proxy_label)
        
        # 检查更新按钮
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        button_style = """
            QPushButton {
                background-color: #7E57C2;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 120px;
                max-width: 160px;
            }
            QPushButton:hover {
                background-color: #9575CD;
            }
            QPushButton:pressed {
                background-color: #673AB7;
            }
            QPushButton:disabled {
                background-color: #424242;
                color: #757575;
            }
        """
        
        self.check_button = QPushButton()
        self.check_button.setStyleSheet(button_style)
        self.check_button.setFixedHeight(36)
        
        # 使用布局方式添加图标
        button_inner_layout = QHBoxLayout(self.check_button)
        button_inner_layout.setContentsMargins(10, 0, 10, 0)
        button_inner_layout.setSpacing(8)
        
        # 图标
        check_icon = QLabel()
        self.font_manager.apply_icon_font(check_icon, 16)
        check_icon.setText(self.font_manager.get_icon_text("ic_fluent_arrow_counterclockwise_24_regular"))
        check_icon.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: transparent;
            }
        """)
        button_inner_layout.addWidget(check_icon)
        
        # 文本
        check_text = QLabel("检查更新")
        check_text.setStyleSheet("color: #FFFFFF; background-color: transparent; font-weight: bold;")
        self.font_manager.apply_font(check_text)
        button_inner_layout.addWidget(check_text)
        
        self.check_button.clicked.connect(self.check_update)
        button_layout.addWidget(self.check_button)
        
        # 清除缓存按钮
        self.clear_cache_button = QPushButton()
        self.clear_cache_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 8px 16px;
                min-width: 120px;
                max-width: 160px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
        """)
        self.clear_cache_button.setFixedHeight(36)
        
        # 使用布局方式添加图标
        clear_button_layout = QHBoxLayout(self.clear_cache_button)
        clear_button_layout.setContentsMargins(10, 0, 10, 0)
        clear_button_layout.setSpacing(8)
        
        # 图标
        clear_icon = QLabel()
        self.font_manager.apply_icon_font(clear_icon, 16)
        clear_icon.setText(self.font_manager.get_icon_text("delete"))
        clear_icon.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: transparent;
            }
        """)
        clear_button_layout.addWidget(clear_icon)
        
        # 文本
        clear_text = QLabel("清除缓存")
        clear_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        self.font_manager.apply_font(clear_text)
        clear_button_layout.addWidget(clear_text)
        
        self.clear_cache_button.clicked.connect(self.clear_update_cache)
        button_layout.addWidget(self.clear_cache_button)
        
        # 自动检查更新选项
        self.auto_check_button = QPushButton()
        self.auto_check_button.setStyleSheet("""
            QPushButton {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 8px 16px;
                min-width: 140px;
                max-width: 180px;
            }
            QPushButton:hover {
                background-color: #3E3E42;
                border: 1px solid #B39DDB;
            }
            QPushButton:pressed {
                background-color: #252526;
            }
            QPushButton:checked {
                background-color: rgba(179, 157, 219, 0.2);
                border: 1px solid #B39DDB;
            }
        """)
        self.auto_check_button.setFixedHeight(36)
        self.auto_check_button.setCheckable(True)
        self.auto_check_button.setChecked(self.config_manager.get_auto_check_update())
        
        # 使用布局方式添加图标
        auto_button_layout = QHBoxLayout(self.auto_check_button)
        auto_button_layout.setContentsMargins(10, 0, 10, 0)
        auto_button_layout.setSpacing(8)
        
        # 图标
        auto_icon = QLabel()
        self.font_manager.apply_icon_font(auto_icon, 16)
        auto_icon.setText(self.font_manager.get_icon_text("schedule"))
        auto_icon.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                background-color: transparent;
            }
        """)
        auto_button_layout.addWidget(auto_icon)
        
        # 文本
        auto_text = QLabel("自动检查更新")
        auto_text.setStyleSheet("color: #FFFFFF; background-color: transparent;")
        self.font_manager.apply_font(auto_text)
        auto_button_layout.addWidget(auto_text)
        
        self.auto_check_button.toggled.connect(self.toggle_auto_check)
        button_layout.addWidget(self.auto_check_button)
        
        button_layout.addStretch()
        version_layout.addLayout(button_layout)
        
        # 状态文本
        self.status_label = QLabel("点击检查按钮以检查更新")
        self.status_label.setStyleSheet("color: #9E9E9E; font-size: 13px; background-color: transparent;")
        self.font_manager.apply_font(self.status_label)
        version_layout.addWidget(self.status_label)
        
        content_layout.addWidget(version_card)
        
        # 更新日志卡片
        update_log_card = self.create_card()
        update_log_layout = QVBoxLayout(update_log_card)
        update_log_layout.setContentsMargins(20, 20, 20, 20)
        update_log_layout.setSpacing(15)
        
        # 日志标题
        log_title_layout = QHBoxLayout()
        
        log_icon = QLabel()
        self.font_manager.apply_icon_font(log_icon, 24)
        log_icon.setText(self.font_manager.get_icon_text("ic_fluent_bookmark_16_regular"))
        log_icon.setStyleSheet("""
            QLabel {
                color: #B39DDB;
                background-color: transparent;
            }
        """)
        log_title_layout.addWidget(log_icon)
        
        log_title = QLabel("更新日志")
        log_title.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(log_title)
        log_title_layout.addWidget(log_title)
        log_title_layout.addStretch()
        
        update_log_layout.addLayout(log_title_layout)
        
        # 分隔线
        log_separator = QFrame()
        log_separator.setFrameShape(QFrame.HLine)
        log_separator.setFrameShadow(QFrame.Sunken)
        log_separator.setStyleSheet("background-color: #333333;")
        log_separator.setFixedHeight(1)
        update_log_layout.addWidget(log_separator)
        
        # 创建日志内容区域（不使用滚动区域）
        self.log_content = QWidget()
        self.log_content.setStyleSheet("background-color: transparent;")
        self.log_layout = QVBoxLayout(self.log_content)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        self.log_layout.setSpacing(15)
        
        # 默认内容
        default_log = QLabel("""
        <html>
        <body style="color: #9E9E9E;">
        <p>暂无更新日志信息，请检查更新</p>
        <p>检查更新后将在此处显示最新版本信息</p>
        </body>
        </html>
        """)
        default_log.setTextFormat(Qt.RichText)
        default_log.setWordWrap(True)
        default_log.setStyleSheet("background-color: transparent;")
        self.font_manager.apply_font(default_log)
        self.log_layout.addWidget(default_log)
        self.log_layout.addStretch()
        
        # 直接添加日志内容到布局中（不使用滚动区域）
        update_log_layout.addWidget(self.log_content)
        
        # 添加日志卡片到内容布局
        content_layout.addWidget(update_log_card)
        
        # 添加底部间距
        bottom_spacer = QWidget()
        bottom_spacer.setFixedHeight(20)
        bottom_spacer.setStyleSheet("background-color: transparent;")
        content_layout.addWidget(bottom_spacer)
    
    def create_card(self):
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background-color: #2C2C2C;
                border-radius: 15px;
            }
        """)
        return card
    
    def check_update(self, silent=False):
        """检查更新
        
        Args:
            silent (bool, optional): 是否为静默检查（自动后台检查），静默检查不更新UI状态. Defaults to False.
        """
        if not silent:
            self.check_button.setEnabled(False)
            self.status_label.setText("正在检查更新...")
            self.status_label.setStyleSheet("color: #B39DDB; font-size: 13px; background-color: transparent;")
        
        # 记录检查时间
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not silent:
            self.last_check_label.setText(f"上次检查：{now}")
        
        # 优先使用缓存的更新源
        if self.cached_data and self.cached_data.get("working_source"):
            source = self.cached_data.get("working_source")
            endpoint = self.cached_data.get("working_endpoint", "")
            
            if source == "primary":
                logging.info("使用缓存中记录的主更新源")
                self.primary_endpoint = endpoint
                self.try_primary_source(now, silent)
            else:
                logging.info("使用缓存中记录的次更新源")
                self.secondary_endpoint = endpoint
                self.try_secondary_source(now, silent)
        else:
            # 没有缓存的可用源，按正常顺序尝试
            self.try_primary_source(now, silent)
    
    def try_primary_source(self, now, silent=False):
        """尝试从主更新源获取更新信息"""
        retry_count = 0
        
        # 禁止不安全连接警告 - 仅在此函数中禁用
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        while retry_count <= self.primary_max_retries:
            try:
                primary_url = f"{self.primary_api_url}{self.primary_endpoint}"
                logging.info(f"正在从主更新源获取更新信息 [尝试 {retry_count+1}/{self.primary_max_retries+1}]: {primary_url}")
                
                # 准备代理设置
                proxy_info = ""
                if self.use_proxy and self.proxy_settings:
                    proxy_info = f"（使用代理）"
                    logging.info(f"使用代理访问主更新源")
                else:
                    logging.info(f"直接连接主更新源（不使用代理）")
                
                logging.info(f"主更新源请求开始 {proxy_info}")
                
                # 创建新的会话对象
                session = requests.Session()
                
                # 设置代理（如果启用）
                if self.use_proxy and self.proxy_settings:
                    session.proxies.update(self.proxy_settings)
                
                # 模拟浏览器头部
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", 
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "close",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                    "DNT": "1"
                }
                
                # 使用requests
                response = session.get(
                    primary_url,
                    headers=headers,
                    timeout=10,
                    verify=False,  # 禁用SSL验证
                    allow_redirects=True,
                    proxies=self.proxy_settings if self.use_proxy else None
                )
                
                # 检查响应
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # 标记为主源
                        self.current_update_source = "primary"
                        logging.info("主更新源连接成功")
                        
                        # 保存工作的源信息
                        data["working_source"] = "primary"
                        data["working_endpoint"] = self.primary_endpoint
                        
                        # 处理数据
                        self.process_update_data(data, now, silent)
                        return  # 成功后返回
                    except json.JSONDecodeError as json_err:
                        logging.error(f"响应不是有效的JSON: {json_err}")
                        # 这里尝试打印响应内容以便调试
                        logging.debug(f"响应内容: {response.text[:200]}...")
                        
                        # 尝试检查并手动解析响应内容
                        if response.content and len(response.content) > 0:
                            # 检查是否有BOM标记或其他编码问题
                            try:
                                text = response.content.decode('utf-8-sig')
                                logging.info("尝试使用utf-8-sig解码响应内容")
                                data = json.loads(text)
                                logging.info("成功使用utf-8-sig解析JSON")
                                
                                # 保存和处理数据
                                self.current_update_source = "primary"
                                data["working_source"] = "primary"
                                data["working_endpoint"] = self.primary_endpoint
                                self.process_update_data(data, now, silent)
                                return
                            except Exception as decode_err:
                                logging.error(f"尝试替代解码方法失败: {decode_err}")
                        raise
                else:
                    logging.warning(f"主更新源返回状态码: {response.status_code}")
                    
                    # 尝试备用路径
                    alternate_url = f"{self.primary_api_url}/version.json"
                    logging.info(f"尝试备用主源路径: {alternate_url}")
                    
                    alt_response = session.get(
                        alternate_url,
                        headers=headers,
                        timeout=10,
                        verify=False,
                        allow_redirects=True,
                        proxies=self.proxy_settings if self.use_proxy else None
                    )
                    
                    if alt_response.status_code == 200:
                        try:
                            data = alt_response.json()
                            
                            # 更新端点
                            self.primary_endpoint = "/version.json"
                            
                            # 标记为主源
                            self.current_update_source = "primary"
                            logging.info("主更新源备用路径连接成功")
                            
                            # 保存工作的源信息
                            data["working_source"] = "primary"
                            data["working_endpoint"] = self.primary_endpoint
                            
                            # 处理数据
                            self.process_update_data(data, now, silent)
                            return  # 成功后返回
                        except json.JSONDecodeError:
                            logging.error(f"备用路径响应不是有效的JSON")
                            # 尝试手动解码
                            try:
                                text = alt_response.content.decode('utf-8-sig')
                                data = json.loads(text)
                                logging.info("备用路径使用utf-8-sig解析成功")
                                
                                # 处理数据
                                self.primary_endpoint = "/version.json"
                                self.current_update_source = "primary"
                                data["working_source"] = "primary"
                                data["working_endpoint"] = self.primary_endpoint
                                self.process_update_data(data, now, silent)
                                return
                            except Exception as alt_decode_err:
                                logging.error(f"备用路径解码失败: {alt_decode_err}")
                            raise
                    else:
                        logging.warning(f"备用主源路径返回状态码: {alt_response.status_code}")
                
            except requests.exceptions.ConnectionError as conn_err:
                logging.error(f"主更新源连接错误 [尝试 {retry_count+1}]: {conn_err}")
            except requests.exceptions.Timeout as timeout_err:
                logging.error(f"主更新源连接超时 [尝试 {retry_count+1}]: {timeout_err}")
            except ValueError as json_err:
                logging.error(f"主更新源JSON解析错误: {json_err}")
                # JSON解析错误不重试，直接尝试次源
                break
            except Exception as e:
                logging.error(f"主更新源连接尝试过程中出现未预期错误: {e}")
            finally:
                # 确保关闭session
                if 'session' in locals():
                    session.close()
            
            # 增加重试计数
            retry_count += 1
            
            # 如果还有重试机会，等待一段时间再重试
            if retry_count <= self.primary_max_retries:
                retry_delay = self.primary_retry_delay * retry_count  # 逐次增加等待时间
                logging.info(f"等待 {retry_delay} 秒后重试主更新源连接...")
                time.sleep(retry_delay)
        
        # 所有主源重试都失败了，尝试次源
        logging.warning("主更新源所有尝试均失败，切换到次更新源")
        self.try_secondary_source(now, silent)
    
    def try_secondary_source(self, now, silent=False):
        """从次更新源获取更新信息，支持多次重试，模拟浏览器行为，支持代理"""
        retry_count = 0
        
        # 禁止不安全连接警告 - 仅在此函数中禁用
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        while retry_count <= self.secondary_max_retries:
            try:
                secondary_url = f"{self.secondary_api_url}{self.secondary_endpoint}"
                logging.info(f"正在从次更新源获取更新信息 [尝试 {retry_count+1}/{self.secondary_max_retries+1}]: {secondary_url}")
                
                # 准备代理设置
                proxy_info = ""
                if self.use_proxy and self.proxy_settings:
                    proxy_info = f"（使用代理）"
                    logging.info(f"使用代理访问次更新源")
                else:
                    logging.info(f"直接连接次更新源（不使用代理）")
                
                logging.info(f"次更新源请求开始 {proxy_info}")
                
                # 使用模拟浏览器行为的方式
                try:
                    # 创建新的会话对象
                    session = requests.Session()
                    
                    # 设置代理（如果启用）
                    if self.use_proxy and self.proxy_settings:
                        session.proxies.update(self.proxy_settings)
                    
                    # 模拟浏览器头部
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                        "Accept": "application/json, text/plain, */*",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8", 
                        "Accept-Encoding": "gzip, deflate, br",
                        "Connection": "close",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                        "DNT": "1"
                    }
                    
                    # 优先使用requests，不再尝试urllib
                    logging.info(f"使用requests请求更新信息")
                    
                    # 直接使用requests
                    response = session.get(
                        secondary_url,
                        headers=headers,
                        timeout=30,
                        verify=False,  # 禁用SSL验证
                        allow_redirects=True,
                        proxies=self.proxy_settings if self.use_proxy else None
                    )
                    
                    # 检查响应
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            
                            # 标记为次源
                            self.current_update_source = "secondary"
                            logging.info("次更新源连接成功 (通过requests)")
                            
                            # 保存工作的源信息
                            data["working_source"] = "secondary"
                            data["working_endpoint"] = self.secondary_endpoint
                            
                            # 添加警告标记
                            if not data.get("warning_shown", False):
                                data["warning_shown"] = True
                                data["source_warning"] = "次更新源数据可能不是最新的"
                            
                            # 处理数据
                            self.process_update_data(data, now, silent)
                            return  # 成功后返回
                        except json.JSONDecodeError as json_err:
                            logging.error(f"响应不是有效的JSON: {json_err}")
                            # 这里尝试打印响应内容以便调试
                            logging.debug(f"响应内容: {response.text[:200]}...")
                            
                            # 尝试检查并手动解析响应内容
                            if response.content and len(response.content) > 0:
                                # 检查是否有BOM标记或其他编码问题
                                try:
                                    text = response.content.decode('utf-8-sig')
                                    logging.info("尝试使用utf-8-sig解码响应内容")
                                    data = json.loads(text)
                                    logging.info("成功使用utf-8-sig解析JSON")
                                    
                                    # 保存和处理数据
                                    self.current_update_source = "secondary"
                                    data["working_source"] = "secondary"
                                    data["working_endpoint"] = self.secondary_endpoint
                                    if not data.get("warning_shown", False):
                                        data["warning_shown"] = True
                                        data["source_warning"] = "次更新源数据可能不是最新的"
                                    self.process_update_data(data, now, silent)
                                    return
                                except Exception as decode_err:
                                    logging.error(f"尝试替代解码方法失败: {decode_err}")
                            raise
                    else:
                        logging.warning(f"次更新源返回状态码: {response.status_code}")
                        
                        # 尝试备用路径
                        alternate_url = f"{self.secondary_api_url}/version.json"
                        logging.info(f"尝试备用次源路径: {alternate_url}")
                        
                        alt_response = session.get(
                            alternate_url,
                            headers=headers,
                            timeout=30,
                            verify=False,
                            allow_redirects=True,
                            proxies=self.proxy_settings if self.use_proxy else None
                        )
                        
                        if alt_response.status_code == 200:
                            try:
                                data = alt_response.json()
                                
                                # 更新端点
                                self.secondary_endpoint = "/version.json"
                                
                                # 标记为次源
                                self.current_update_source = "secondary"
                                logging.info("次更新源备用路径连接成功")
                                
                                # 保存工作的源信息
                                data["working_source"] = "secondary"
                                data["working_endpoint"] = self.secondary_endpoint
                                
                                # 添加警告标记
                                if not data.get("warning_shown", False):
                                    data["warning_shown"] = True
                                    data["source_warning"] = "次更新源数据可能不是最新的"
                                
                                # 处理数据
                                self.process_update_data(data, now, silent)
                                return  # 成功后返回
                            except json.JSONDecodeError:
                                logging.error(f"备用路径响应不是有效的JSON")
                                # 尝试手动解码
                                try:
                                    text = alt_response.content.decode('utf-8-sig')
                                    data = json.loads(text)
                                    logging.info("备用路径使用utf-8-sig解析成功")
                                    
                                    # 处理数据
                                    self.secondary_endpoint = "/version.json"
                                    self.current_update_source = "secondary"
                                    data["working_source"] = "secondary"
                                    data["working_endpoint"] = self.secondary_endpoint
                                    if not data.get("warning_shown", False):
                                        data["warning_shown"] = True
                                        data["source_warning"] = "次更新源数据可能不是最新的"
                                    self.process_update_data(data, now, silent)
                                    return
                                except Exception as alt_decode_err:
                                    logging.error(f"备用路径解码失败: {alt_decode_err}")
                                raise
                        else:
                            logging.warning(f"备用次源路径返回状态码: {alt_response.status_code}")
                            raise requests.exceptions.HTTPError(f"HTTP {alt_response.status_code}")
                    
                except (requests.exceptions.ConnectionError, urllib.error.URLError) as conn_err:
                    logging.error(f"次更新源请求错误 [尝试 {retry_count+1}]: {conn_err}")
                    # 继续尝试重试
                    
                except requests.exceptions.Timeout as timeout_err:
                    logging.error(f"次更新源连接超时 [尝试 {retry_count+1}]: {timeout_err}")
                    # 继续尝试重试
                    
                except json.JSONDecodeError as json_err:
                    logging.error(f"次更新源JSON解析错误: {json_err}")
                    # JSON解析错误不重试，直接尝试缓存
                    break
                    
                except Exception as req_err:
                    logging.error(f"次更新源请求过程中出现其他错误 [尝试 {retry_count+1}]: {req_err}")
                    # 继续尝试重试
                
                finally:
                    # 确保关闭session
                    if 'session' in locals():
                        session.close()
                
            except Exception as e:
                # 捕获所有异常，确保重试循环不会中断
                logging.error(f"次更新源连接尝试过程中出现未预期错误: {str(e)}")
            
            # 增加重试计数
            retry_count += 1
            
            # 如果还有重试机会，等待一段时间再重试
            if retry_count <= self.secondary_max_retries:
                retry_delay = self.secondary_retry_delay * retry_count  # 逐次增加等待时间
                logging.info(f"等待 {retry_delay} 秒后重试次更新源连接...")
                time.sleep(retry_delay)
        
        # 所有重试都失败了，尝试使用缓存数据
        logging.warning("所有更新源连接均失败，尝试使用缓存数据")
        if self.cached_data and self.cached_data.get("latest"):
            logging.info("使用缓存的更新数据")
            # 设置缓存数据来源提示
            if not silent:
                self.status_label.setText("无法连接到更新服务器，使用缓存数据")
                self.status_label.setStyleSheet("color: #FFC107; font-size: 13px; background-color: transparent;")
                # 更新UI使用缓存数据
                self.update_ui_from_cache()
            self.check_button.setEnabled(True)
        else:
            # 没有缓存数据可用
            self.handle_update_failure("所有更新源连接失败，且无缓存数据可用", silent)
    
    def handle_update_failure(self, error_msg, silent=False):
        """处理更新失败"""
        if not silent:
            self.status_label.setText(f"检查更新失败: {error_msg}")
            self.status_label.setStyleSheet("color: #F44336; font-size: 13px; background-color: transparent;")
        self.updateError.emit(error_msg)
        self.check_button.setEnabled(True)
    
    def process_update_data(self, data, now, silent=False):
        """处理获取到的更新数据"""
        latest = data.get("latest", {})
        
        if not latest:
            self.handle_update_failure("无效的版本信息", silent)
            return
        
        # 保存缓存和检查时间
        data["last_check_time"] = now
        data["last_check_timestamp"] = time.time()
        data["source"] = self.current_update_source
        self.cached_data = data
        self.save_cache(data)
        
        # 检查是否有新版本
        if self.compare_versions(latest["version"], self.current_version) > 0:
            # 有更新版本
            self.has_newer_version = True
            if not silent:
                self.status_label.setText(f"发现新版本: {latest['version']}")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px; background-color: transparent;")
                
                # 更新更新日志
                self.update_release_notes(latest, True)
            
            # 发出更新信号
            self.updateFound.emit(latest["version"], json.dumps(latest))
        else:
            # 已经是最新版本
            self.has_newer_version = False
            if not silent:
                self.status_label.setText("您当前使用的已经是最新版本")
                self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px; background-color: transparent;")
                
                # 显示当前版本的更新日志
                current_version_info = None
                
                # 如果当前版本是最新版本
                if latest["version"] == self.current_version:
                    current_version_info = latest
                # 否则从历史记录中查找
                elif "history" in data and self.current_version in data["history"]:
                    current_version_info = data["history"][self.current_version]
                
                if current_version_info:
                    self.update_release_notes(current_version_info, False)
                else:
                    # 清除原有内容
                    for i in reversed(range(self.log_layout.count())):
                        item = self.log_layout.itemAt(i)
                        if item.widget():
                            item.widget().deleteLater()
                    
                    # 显示提示信息
                    no_log_label = QLabel("暂无当前版本的更新日志信息")
                    no_log_label.setStyleSheet("color: #9E9E9E; font-size: 14px; background-color: transparent;")
                    self.font_manager.apply_font(no_log_label)
                    self.log_layout.addWidget(no_log_label)
                    self.log_layout.addStretch()
        
        # 如果是次更新源，显示警告
        if not silent and self.current_update_source == "secondary" and data.get("source_warning"):
            self.status_label.setText(f"{self.status_label.text()} (使用次更新源)")
            
            # 添加次更新源警告提示
            source_warning_label = QLabel(data["source_warning"])
            source_warning_label.setStyleSheet("color: #FFC107; font-size: 12px; background-color: transparent;")
            self.font_manager.apply_font(source_warning_label)
            
            # 在日志上方添加警告
            if hasattr(self, 'log_layout') and self.log_layout.count() > 0:
                # 找到合适的位置插入警告
                first_item = self.log_layout.itemAt(0)
                if first_item and first_item.widget():
                    warning_container = QWidget()
                    warning_layout = QHBoxLayout(warning_container)
                    warning_layout.setContentsMargins(0, 5, 0, 5)
                    warning_icon = QLabel()
                    self.font_manager.apply_icon_font(warning_icon, 14)
                    warning_icon.setText(self.font_manager.get_icon_text("warning"))
                    warning_icon.setStyleSheet("color: #FFC107; background-color: transparent;")
                    warning_layout.addWidget(warning_icon)
                    warning_layout.addWidget(source_warning_label)
                    warning_layout.addStretch()
                    
                    # 在布局的开头插入
                    self.log_layout.insertWidget(0, warning_container)
        
        if not silent:
            self.check_button.setEnabled(True)
    
    def update_release_notes(self, latest, show_download=True):
        # 清除原有内容
        for i in reversed(range(self.log_layout.count())):
            item = self.log_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新版本信息
        version_label = QLabel(f"<b>版本 {latest['version']}</b> ({latest.get('date', '')})")
        version_label.setStyleSheet("color: #B39DDB; font-size: 16px; background-color: transparent;")
        self.font_manager.apply_font(version_label)
        self.log_layout.addWidget(version_label)
        
        # 添加更新说明标题
        notes = latest.get("notes", {})
        title_label = QLabel(notes.get("title", ""))
        title_label.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold; background-color: transparent;")
        self.font_manager.apply_font(title_label)
        self.log_layout.addWidget(title_label)
        
        # 添加更新内容
        changes_html = "<ul style='margin-left: 20px; color: #CCCCCC;'>"
        for change in notes.get("content", []):
            changes_html += f"<li>{change}</li>"
        changes_html += "</ul>"
        
        changes_label = QLabel(changes_html)
        changes_label.setTextFormat(Qt.RichText)
        changes_label.setWordWrap(True)
        changes_label.setStyleSheet("background-color: transparent;")
        self.font_manager.apply_font(changes_label)
        self.log_layout.addWidget(changes_label)
        
        # 如果需要强制更新
        if latest.get("force_update", False) and show_download:
            required_label = QLabel("此版本为必须更新版本，请尽快更新")
            required_label.setStyleSheet("color: #FF9800; font-size: 14px; font-weight: bold; background-color: transparent;")
            self.font_manager.apply_font(required_label)
            self.log_layout.addWidget(required_label)
            
            # 如果是强制更新，可能需要立即下载
            if latest.get("force_update_action") == "immediate":
                # 获取下载信息
                self.download_update_immediately(latest)
        
        # 添加文件大小信息
        platform = "win"  # 这里可以根据实际系统判断
        download_info = latest.get("download", {}).get(platform, {})
        if download_info.get("size"):
            size_label = QLabel(f"文件大小：{download_info['size']}")
            size_label.setStyleSheet("color: #9E9E9E; font-size: 12px; background-color: transparent;")
            self.font_manager.apply_font(size_label)
            self.log_layout.addWidget(size_label)
        
        # 仅当有新版本时才显示下载按钮
        if download_info.get("url") and show_download and self.has_newer_version:
            download_btn = QPushButton()
            download_btn.setStyleSheet("""
                QPushButton {
                    background-color: #7E57C2;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-weight: bold;
                    min-width: 120px;
                    max-width: 160px;
                }
                QPushButton:hover {
                    background-color: #9575CD;
                }
                QPushButton:pressed {
                    background-color: #673AB7;
                }
            """)
            
            # 使用布局方式添加图标
            download_layout = QHBoxLayout(download_btn)
            download_layout.setContentsMargins(10, 0, 10, 0)
            download_layout.setSpacing(8)
            
            # 图标
            download_icon = QLabel()
            self.font_manager.apply_icon_font(download_icon, 16)
            download_icon.setText(self.font_manager.get_icon_text("download"))
            download_icon.setStyleSheet("""
                QLabel {
                    color: #FFFFFF;
                    background-color: transparent;
                }
            """)
            download_layout.addWidget(download_icon)
            
            # 文本
            download_text = QLabel("下载更新")
            download_text.setStyleSheet("color: #FFFFFF; background-color: transparent; font-weight: bold;")
            self.font_manager.apply_font(download_text)
            download_layout.addWidget(download_text)
            
            # 检查下载链接有效性
            url = download_info["url"]
            if url and url not in ["Not Support", "NS", "N", ""]:
                # 保存下载相关信息供按钮使用
                download_btn.setProperty("url", url)
                download_btn.setProperty("filename", f"HanabiDM_{latest['version']}_update.exe")
                download_btn.setProperty("filesize", download_info.get("size_bytes", 0))
                download_btn.clicked.connect(self.on_download_button_clicked)
            else:
                download_btn.clicked.connect(lambda: CustomMessageBox.warning(
                    self,
                    "下载提示",
                    "未提供下载链接，请前往GitHub获取最新版本。"
                ))
            
            button_container = QWidget()
            button_container.setStyleSheet("background-color: transparent;")
            button_container_layout = QHBoxLayout(button_container)
            button_container_layout.setContentsMargins(0, 10, 0, 10)
            button_container_layout.addWidget(download_btn)
            button_container_layout.addStretch()
            
            self.log_layout.addWidget(button_container)
        
        self.log_layout.addStretch()
    
    def on_download_button_clicked(self):
        """下载按钮点击处理函数"""
        button = self.sender()
        if not button:
            return
            
        url = button.property("url")
        filename = button.property("filename")
        filesize = button.property("filesize")
        
        if not url or not filename:
            return
        
        # 直接获取主窗口实例并调用下载方法
        try:
            # 通过父级组件查找主窗口
            main_window = None
            parent = self.parent()
            
            # 向上查找主窗口
            while parent:
                if parent.__class__.__name__ == "DownloadManagerWindow":
                    main_window = parent
                    break
                parent = parent.parent()
            
            # 如果找不到，尝试通过QApplication获取
            if not main_window:
                from PySide6.QtWidgets import QApplication
                for widget in QApplication.topLevelWidgets():
                    if widget.__class__.__name__ == "DownloadManagerWindow":
                        main_window = widget
                        break
            
            if main_window:
                # 构建下载任务数据
                task_data = {
                    "url": url,
                    "file_name": filename,
                    "total_size": filesize,
                    "progress": 0,
                    "status": "初始化中",
                    "speed": "0 B/s",
                    "save_path": main_window.save_path,
                    "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "update",
                    "request_id": f"update_{int(time.time() * 1000)}"
                }
                
                # 请求格式，适配download方法的需求
                download_data = {
                    "url": url,
                    "filename": filename,
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                    },
                    "requestId": task_data["request_id"],
                    "type": "update"
                }
                
                # 直接调用添加下载任务的方法
                success = main_window.start_download_with_data(task_data, download_data)
                
                if success:
                    # 切换到下载页面
                    main_window.switch_page(0)
                    logging.info(f"已直接添加更新下载任务: {filename}")
                    
                    # 更新按钮状态 - 修复文字重叠问题
                    button.setEnabled(False)
                    
                    # 查找按钮布局中的文本标签并更新内容
                    button_layout = button.layout()
                    if button_layout:
                        for i in range(button_layout.count()):
                            item = button_layout.itemAt(i)
                            if item and item.widget():
                                widget = item.widget()
                                if isinstance(widget, QLabel) and widget != button_layout.itemAt(0).widget():  # 跳过图标标签
                                    widget.setText("已添加到下载列表")
                                    break
                    
                    # 提示用户
                    self.status_label.setText(f"更新包已添加到下载列表")
                else:
                    # 添加失败
                    self.status_label.setText(f"添加下载任务失败")
                    logging.error(f"直接添加更新下载任务失败")
            else:
                # 找不到主窗口，使用原来的信号方式
                self.addDownloadTask.emit(url, filename, filesize)
                
                # 更新按钮状态 - 修复文字重叠问题
                button.setEnabled(False)
                
                # 查找按钮布局中的文本标签并更新内容
                button_layout = button.layout()
                if button_layout:
                    for i in range(button_layout.count()):
                        item = button_layout.itemAt(i)
                        if item and item.widget():
                            widget = item.widget()
                            if isinstance(widget, QLabel) and widget != button_layout.itemAt(0).widget():  # 跳过图标标签
                                widget.setText("已添加到下载列表")
                                break
                
                # 提示用户
                self.status_label.setText(f"更新包已添加到下载列表")
        except Exception as e:
            logging.error(f"直接添加下载任务失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            
            # 出错时使用原来的信号方式
            self.addDownloadTask.emit(url, filename, filesize)
            
            # 更新按钮状态 - 修复文字重叠问题
            button.setEnabled(False)
            
            # 查找按钮布局中的文本标签并更新内容
            button_layout = button.layout()
            if button_layout:
                for i in range(button_layout.count()):
                    item = button_layout.itemAt(i)
                    if item and item.widget():
                        widget = item.widget()
                        if isinstance(widget, QLabel) and widget != button_layout.itemAt(0).widget():  # 跳过图标标签
                            widget.setText("已添加到下载列表")
                            break
            
            # 提示用户
            self.status_label.setText(f"更新包已添加到下载列表")
    
    def download_update_immediately(self, latest_info):
        """立即下载更新（用于强制更新）"""
        platform = "win"  # 这里可以根据实际系统判断
        download_info = latest_info.get("download", {}).get(platform, {})
        
        if not download_info or not download_info.get("url"):
            return
            
        url = download_info["url"]
        filename = f"HanabiDM_{latest_info['version']}_update.exe"
        filesize = download_info.get("size_bytes", 0)
        
        # 发送信号添加下载任务
        self.addDownloadTask.emit(url, filename, filesize)
        
        # 显示强制更新提示
        CustomMessageBox.warning(
            self,
            "强制更新通知",
            f"当前版本需要强制更新到 {latest_info['version']}，更新包已添加到下载列表。"
        )
    
    def toggle_auto_check(self, checked):
        self.config_manager.set_auto_check_update(checked)
    
    def clear_update_cache(self):
        """清除更新缓存并强制从主源获取数据"""
        try:
            # 删除缓存文件
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
                self.cached_data = {}
                self.current_update_source = None
                
                # 更新UI
                self.status_label.setText("已清除更新缓存，将从主源获取数据")
                self.status_label.setStyleSheet("color: #64B5F6; font-size: 13px; background-color: transparent;")
                
                # 更新最后检查时间显示
                self.last_check_label.setText("上次检查：从未检查")
                
                # 清空日志显示
                for i in reversed(range(self.log_layout.count())):
                    item = self.log_layout.itemAt(i)
                    if item.widget():
                        item.widget().deleteLater()
                
                # 显示默认内容
                default_log = QLabel("""
                <html>
                <body style="color: #9E9E9E;">
                <p>已清除更新日志信息</p>
                <p>请点击检查更新按钮从主更新源获取最新信息</p>
                </body>
                </html>
                """)
                default_log.setTextFormat(Qt.RichText)
                default_log.setWordWrap(True)
                default_log.setStyleSheet("background-color: transparent;")
                self.font_manager.apply_font(default_log)
                self.log_layout.addWidget(default_log)
                self.log_layout.addStretch()
                
                # 弹出提示
                CustomMessageBox.information(
                    self,
                    "操作成功",
                    "已成功清除更新缓存，请点击检查更新按钮从主更新源获取最新数据。"
                )
            else:
                self.status_label.setText("无需清除，更新缓存不存在")
                CustomMessageBox.information(
                    self,
                    "提示",
                    "无需清除，更新缓存不存在。"
                )
                
        except Exception as e:
            self.status_label.setText(f"清除缓存失败: {str(e)}")
            self.status_label.setStyleSheet("color: #F44336; font-size: 13px; background-color: transparent;")
            CustomMessageBox.warning(
                self,
                "操作失败",
                f"清除更新缓存失败: {str(e)}"
            )
    
    def compare_versions(self, version1, version2):
        """
        比较两个版本号的大小
        支持以下格式:
        - 标准版本号 (1.0.0)
        - 带hotfix/remake后缀 (1.0.0-1 hotfix, 1.0.0 remake)
        - 四段式版本号 (1.0.0.1000)
        - 混合模式 (1.1.1.9033 hotfix)
        
        返回值:
        - 1: version1 更新
        - 0: 版本相同
        - -1: version2 更新
        """
        # 定义优先级字典，值越大优先级越高
        suffix_priority = {
            "": 0,
            "hotfix": 1,  # hotfix优先级低于普通版本
            "remake": 2   # remake优先级高于普通版本
        }
        
        # 解析版本1
        v1_main, v1_build, v1_suffix, v1_suffix_num = self._parse_version(version1)
        
        # 解析版本2
        v2_main, v2_build, v2_suffix, v2_suffix_num = self._parse_version(version2)
        
        # 首先比较主版本号
        for i in range(max(len(v1_main), len(v2_main))):
            v1_comp = v1_main[i] if i < len(v1_main) else 0
            v2_comp = v2_main[i] if i < len(v2_main) else 0
            
            if v1_comp > v2_comp:
                return 1  # version1 更新
            elif v1_comp < v2_comp:
                return -1  # version2 更新
        
        # 如果主版本号相同，比较构建版本号
        if v1_build > v2_build:
            return 1
        elif v1_build < v2_build:
            return -1
            
        # 如果主版本号和构建版本号都相同，比较后缀优先级
        if suffix_priority.get(v1_suffix, 0) > suffix_priority.get(v2_suffix, 0):
            return 1
        elif suffix_priority.get(v1_suffix, 0) < suffix_priority.get(v2_suffix, 0):
            return -1
            
        # 如果后缀类型相同，比较后缀数字（仅hotfix有）
        if v1_suffix == v2_suffix == "hotfix":
            if v1_suffix_num > v2_suffix_num:
                return 1
            elif v1_suffix_num < v2_suffix_num:
                return -1
        
        # 完全相同
        return 0
        
    def _parse_version(self, version_str):
        """解析版本号字符串
        
        返回:
            tuple: (主版本号列表, 构建版本号, 后缀类型, 后缀编号)
        """
        # 默认值
        main_version = []
        build_number = 0
        suffix_type = ""
        suffix_number = 0
        
        # 处理特殊情况：空字符串或None
        if not version_str:
            return ([0, 0, 0], 0, "", 0)
            
        # 处理后缀
        version_parts = version_str.lower().split()
        version_base = version_parts[0]  # 基本版本部分
        
        # 检查是否有后缀类型
        if len(version_parts) > 1:
            if "hotfix" in version_parts:
                suffix_type = "hotfix"
            elif "remake" in version_parts:
                suffix_type = "remake"
        
        # 处理带有-的hotfix格式（例如1.0.0-1）
        if "-" in version_base and suffix_type == "hotfix":
            version_base, suffix_num_str = version_base.split("-", 1)
            try:
                suffix_number = int(suffix_num_str)
            except ValueError:
                suffix_number = 0
        
        # 分割版本号
        version_segments = version_base.split(".")
        
        # 解析主版本号（前三段）
        main_segments = min(3, len(version_segments))
        for i in range(main_segments):
            try:
                main_version.append(int(version_segments[i]))
            except ValueError:
                main_version.append(0)
        
        # 补齐主版本号到3段
        while len(main_version) < 3:
            main_version.append(0)
        
        # 如果有第四段，作为构建版本号，支持超大数字
        if len(version_segments) > 3:
            try:
                build_number = int(version_segments[3])
                # 确保构建号能处理大数值
                print(f"解析构建号: {version_segments[3]} -> {build_number}")
            except ValueError:
                build_number = 0
                print(f"无效的构建号格式: {version_segments[3]}")
        
        result = (main_version, build_number, suffix_type, suffix_number)
        print(f"版本解析结果: {version_str} -> {result}")
        return result
        
    def get_proxy_settings(self):
        """获取代理设置"""
        if not hasattr(self.config_manager, 'get_proxy_settings'):
            return None
        
        proxy_settings = self.config_manager.get_proxy_settings()
        if not proxy_settings:
            return None
            
        # 格式化代理URL
        proxy_type = proxy_settings.get('type', 'http')
        proxy_host = proxy_settings.get('host', '')
        proxy_port = proxy_settings.get('port', '')
        proxy_user = proxy_settings.get('username', '')
        proxy_pass = proxy_settings.get('password', '')
        
        if not proxy_host or not proxy_port:
            return None
            
        # 如果有用户名密码，添加认证信息
        auth = f"{proxy_user}:{proxy_pass}@" if proxy_user and proxy_pass else ""
        proxy_url = f"{proxy_type}://{auth}{proxy_host}:{proxy_port}"
        
        proxies = {
            "http": proxy_url,
            "https": proxy_url,
        }
        
        logging.info(f"使用代理设置: {proxy_type}://{proxy_host}:{proxy_port}")
        return proxies
        