from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QSpacerItem, QSizePolicy, QScrollArea, QFrame, QMessageBox)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint, QThread
from PySide6.QtGui import QFont, QColor
from core.font.font_manager import FontManager
from client.ui.components.customMessagebox import CustomMessageBox
from client.version.version_manager import VersionManager
import requests
import json
import os
import time
from datetime import datetime
import logging
import urllib.request
import urllib3
import random
# 导入版本信息获取工具
from client.ui.client_interface.settings.utils.net_update_get import get_version_info

class UpdateCheckerThread(QThread):
    """更新检查线程，避免UI阻塞"""
    updateDataReady = Signal(dict, str)  # 数据, 检查时间
    updateError = Signal(str)            # 错误信息
    
    def __init__(self, update_page, check_time, silent=False):
        super().__init__()
        self.update_page = update_page
        self.check_time = check_time
        self.silent = silent
        
    def run(self):
        """线程主函数：获取更新信息"""
        try:
            # 构建请求头
            headers = None
            if hasattr(self.update_page, 'get_user_agent'):
                user_agent = self.update_page.get_user_agent()
                if user_agent:
                    headers = {"User-Agent": user_agent}
            
            # 使用net_update_get获取版本信息，传递代理设置和请求头
            data = get_version_info(
                proxy_settings=self.update_page.proxy_settings if self.update_page.use_proxy else None,
                headers=headers
            )
            
            # 检查数据是否有效
            if data:
                # 标记为主源
                self.update_page.current_update_source = "primary"
                logging.info("通过net_update_get获取版本信息成功")
                
                # 保存工作的源信息
                data["working_source"] = "primary"
                data["working_endpoint"] = self.update_page.primary_endpoint
                
                # 发送信号
                self.updateDataReady.emit(data, self.check_time)
                return
            else:
                # 获取失败，尝试备用方案
                logging.warning("主更新源通过net_update_get获取失败，尝试备用方案")
                self.try_backup_sources()
        except Exception as e:
            logging.error(f"通过net_update_get获取版本信息出错: {e}")
            import traceback
            logging.error(traceback.format_exc())
            self.try_backup_sources()
    
    def try_backup_sources(self):
        """尝试使用备用方法获取更新信息"""
        # 尝试从备用源获取更新
        logging.info("尝试使用备用源获取更新信息")
        
        try:
            # 构建请求头
            headers = None
            if hasattr(self.update_page, 'get_user_agent'):
                user_agent = self.update_page.get_user_agent()
                if user_agent:
                    headers = {"User-Agent": user_agent}
            
            # 调用net_update_get.py中的get_version_info，指定备用URL
            # 通过第二个参数传递备用URL
            data = get_version_info(
                proxy_settings=self.update_page.proxy_settings if self.update_page.use_proxy else None,
                headers=headers,
                alt_url="https://zzbuaoye.dpdns.org/HanabiDM/version.json"  # 指定备用URL
            )
            
            # 检查数据是否有效
            if data:
                # 标记为次源
                self.update_page.current_update_source = "secondary"
                logging.info("备用更新源连接成功")
                
                # 保存工作的源信息
                data["working_source"] = "secondary"
                data["working_endpoint"] = "/HanabiDM/version.json"
                
                # 添加警告标记
                if not data.get("warning_shown", False):
                    data["warning_shown"] = True
                    data["source_warning"] = "备用更新源数据可能不是最新的"
                
                # 发送信号
                self.updateDataReady.emit(data, self.check_time)
                return
        except Exception as e:
            logging.error(f"备用更新源请求出错: {e}")
            import traceback
            logging.error(traceback.format_exc())
        
        # 所有更新源连接均失败
        logging.warning("所有更新源连接均失败")
        if self.update_page.cached_data and self.update_page.cached_data.get("latest"):
            logging.info("但有缓存的更新数据可用")
            # 发送空数据信号，让主线程处理缓存数据
            self.updateDataReady.emit({}, self.check_time)
        else:
            # 没有缓存数据可用
            self.updateError.emit("所有更新源连接失败，且无缓存数据可用")

class UpdatePage(QWidget):
    updateFound = Signal(str, str)  # 版本号, 更新内容
    updateError = Signal(str)       # 错误信息
    addDownloadTask = Signal(str, str, int)  # 下载URL, 文件名, 文件大小
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        
        # 初始化版本管理器
        self.version_manager = VersionManager.get_instance()
        
        # 软件当前版本
        self.current_version = self.version_manager.get_client_version()
        
        # 更新源配置 - 用于显示和标记，实际获取已移至net_update_get.py
        self.primary_api_url = "https://apiv2.xiaoy.asia"  # 主更新源URL
        self.primary_endpoint = "/custody-project/hdm/api/version.php"  # 主API路径
        
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
        
        # 更新检查线程
        self.update_thread = None
    
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
        
        # 创建并启动更新检查线程
        if self.update_thread is not None and self.update_thread.isRunning():
            # 如果线程已在运行，不要创建新线程
            logging.info("更新检查线程已在运行中")
            return
            
        # 创建新线程
        self.update_thread = UpdateCheckerThread(self, now, silent)
        
        # 连接信号
        self.update_thread.updateDataReady.connect(self.on_update_data_ready)
        self.update_thread.updateError.connect(self.on_update_error)
        self.update_thread.finished.connect(self.on_update_thread_finished)
        
        # 启动线程
        self.update_thread.start()
        
        logging.info("更新检查线程已启动")
    
    def on_update_data_ready(self, data, check_time):
        """处理线程返回的更新数据"""
        if data:  # 有数据
            self.process_update_data(data, check_time, getattr(self.update_thread, 'silent', False))
        elif self.cached_data and self.cached_data.get("latest"):  # 无数据但有缓存
            logging.info("使用缓存的更新数据")
            # 设置缓存数据来源提示
            silent = getattr(self.update_thread, 'silent', False)
            if not silent:
                self.status_label.setText("无法连接到更新服务器，使用缓存数据")
                self.status_label.setStyleSheet("color: #FFC107; font-size: 13px; background-color: transparent;")
                # 更新UI使用缓存数据
                self.update_ui_from_cache()
            self.check_button.setEnabled(True)
        else:
            # 没有缓存数据可用
            self.handle_update_failure("所有更新源连接失败，且无缓存数据可用", getattr(self.update_thread, 'silent', False))
    
    def on_update_error(self, error_msg):
        """处理线程返回的错误信息"""
        self.handle_update_failure(error_msg, getattr(self.update_thread, 'silent', False))
    
    def on_update_thread_finished(self):
        """处理线程完成事件"""
        logging.info("更新检查线程已完成")
        
        # 如果按钮还未启用，确保启用
        if not self.check_button.isEnabled():
            self.check_button.setEnabled(True)
    
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
                # 使用下载信息中的真实文件名，如果没有则使用默认名称
                real_filename = download_info.get("filename", f"HanabiDownloadManager_{latest['version']}_UpgradePackages")
                download_btn.setProperty("filename", real_filename)
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
        
        # 获取最新版本信息中的发布时间和发布者
        release_time = ""
        release_author = ""
        
        # 从缓存数据中获取最新版本的详细信息
        if self.cached_data and self.cached_data.get("latest"):
            latest_info = self.cached_data.get("latest", {})
            release_time = latest_info.get("date", "未知")
            release_author = latest_info.get("author", "ZZBuAoYe")
        
        # 格式化文件大小显示
        size_display = "未知"
        if isinstance(filesize, (int, float)) and filesize > 0:
            # 如果是数字且大于0，格式化显示
            if filesize < 1024 * 1024:  # 小于1MB
                size_display = f"{filesize / 1024:.2f} KB"
            else:  # 大于等于1MB
                size_display = f"{filesize / (1024 * 1024):.2f} MB"
        else:
            # 尝试从缓存中获取文本形式的大小
            if self.cached_data and self.cached_data.get("latest"):
                platform = "win"  # 这里可以根据实际系统判断
                download_info = self.cached_data.get("latest", {}).get("download", {}).get(platform, {})
                if download_info.get("size"):
                    size_display = download_info.get("size")
        
        # 弹出确认对话框询问用户 - 使用正确的按钮格式
        confirm = CustomMessageBox.question(
            self,
            "✦更新包信息确认",
            f"✿安装包信息:\n▌文件名称：{filename}\n▌发布时间：{release_time}\n▌发布作者：{release_author}\n▌版本代号：{latest_info['version']}\n▌整包大小：{size_display}",
            [("确定", True), ("取消", False)]  # 使用正确的按钮格式
        )
        
        # 如果用户取消，则直接返回
        if not confirm:
            return
        
        try:
            # 导入弹窗类
            from client.ui.extension_interface.pop_dialog import DownloadPopDialog
            from PySide6.QtWidgets import QApplication
            
            # 获取用户设置的UA
            user_agent = self.get_user_agent()
            
            # 构建下载任务数据
            download_data = {
                "url": url,
                "filename": filename,
                "filesize": filesize,
                "headers": {
                    "User-Agent": user_agent
                },
                "requestId": f"update_{int(time.time() * 1000)}",
                "type": "update",
                "download_source": "update_page"
            }
            
            # 获取主窗口作为父窗口
            main_window = None
            parent = self.parent()
            
            # 向上查找主窗口
            while parent:
                if parent.__class__.__name__ == "DownloadManagerWindow":
                    main_window = parent
                    break
                parent = parent.parent()
            
            # 创建下载弹窗并自动开始下载
            dialog = DownloadPopDialog.create_and_show(
                download_data=download_data,
                parent=main_window,
                auto_start=True  # 设置为自动开始下载
            )
            
            # 手动调整弹窗位置到屏幕中央
            def center_dialog():
                screen = QApplication.primaryScreen().availableGeometry()
                dialog_size = dialog.size()
                x = (screen.width() - dialog_size.width()) // 2
                y = (screen.height() - dialog_size.height()) // 2
                dialog.move(QPoint(x, y))
                dialog.raise_()
                dialog.activateWindow()
            
            # 在UI更新循环后执行位置调整
            QTimer.singleShot(50, center_dialog)
            QTimer.singleShot(300, center_dialog)  # 再延迟一点再次调整，确保窗口尺寸计算完成
            
            # 更新按钮状态
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
            self.status_label.setText(f"更新包正在下载中...")
            
        except Exception as e:
            logging.error(f"创建下载弹窗失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            
            # 出错时使用原来的信号方式
            self.addDownloadTask.emit(url, filename, filesize)
    
    def get_user_agent(self):
        """获取用户设置的User-Agent，查找上层窗口的配置管理器
        
        返回:
            str: 用户设置的User-Agent，如未设置则返回默认值
        """
        try:
            # 向上查找主窗口
            parent = self.parent()
            while parent:
                # 查找主窗口的get_user_agent方法
                if hasattr(parent, 'get_user_agent'):
                    return parent.get_user_agent()
                # 查找主窗口的配置管理器
                elif hasattr(parent, 'config_manager') and parent.config_manager:
                    # 尝试获取UA
                    if hasattr(parent.config_manager, 'get_user_agent'):
                        return parent.config_manager.get_user_agent()
                    else:
                        network_config = parent.config_manager.get("network", {})
                        user_agent = network_config.get("user_agent")
                        if user_agent:
                            return user_agent
                parent = parent.parent()
        except Exception as e:
            logging.warning(f"获取User-Agent失败: {e}")
        
        # 返回默认值
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    
    def download_update_immediately(self, latest_info):
        """立即下载更新（用于强制更新）"""
        platform = "win"  # 这里可以根据实际系统判断
        download_info = latest_info.get("download", {}).get(platform, {})
        
        if not download_info or not download_info.get("url"):
            return
            
        url = download_info["url"]
        # 使用下载信息中的真实文件名，如果没有则使用默认名称
        filename = download_info.get("filename", f"HDM_{latest_info['version']}_UpgradePackages")
        filesize = download_info.get("size_bytes", 0)
        
        # 获取发布时间和发布者
        release_time = latest_info.get("date", "未知")
        release_author = latest_info.get("author", "ZZBuAoYe")
        
        # 格式化文件大小显示
        size_display = "未知"
        if isinstance(filesize, (int, float)) and filesize > 0:
            if filesize < 1024 * 1024:  # 小于1MB
                size_display = f"{filesize / 1024:.2f} KB"
            else:  # 大于等于1MB
                size_display = f"{filesize / (1024 * 1024):.2f} MB"
        elif download_info.get("size"):
            size_display = download_info.get("size")
        
        try:
            # 导入弹窗类
            from client.ui.extension_interface.pop_dialog import DownloadPopDialog
            from PySide6.QtWidgets import QApplication
            
            # 获取用户设置的UA
            user_agent = self.get_user_agent()
            
            # 构建下载任务数据
            download_data = {
                "url": url,
                "filename": filename,
                "filesize": filesize,
                "headers": {
                    "User-Agent": user_agent
                },
                "requestId": f"update_force_{int(time.time() * 1000)}",
                "type": "update",
                "download_source": "force_update"
            }
            
            # 获取主窗口作为父窗口
            main_window = None
            parent = self.parent()
            
            # 向上查找主窗口
            while parent:
                if parent.__class__.__name__ == "DownloadManagerWindow":
                    main_window = parent
                    break
                parent = parent.parent()
            
            # 创建下载弹窗并自动开始下载
            dialog = DownloadPopDialog.create_and_show(
                download_data=download_data,
                parent=main_window,
                auto_start=True  # 设置为自动开始下载
            )
            
            # 手动调整弹窗位置到屏幕中央
            def center_dialog():
                screen = QApplication.primaryScreen().availableGeometry()
                dialog_size = dialog.size()
                x = (screen.width() - dialog_size.width()) // 2
                y = (screen.height() - dialog_size.height()) // 2
                dialog.move(QPoint(x, y))
                dialog.raise_()
                dialog.activateWindow()
            
            # 在UI更新循环后执行位置调整
            QTimer.singleShot(50, center_dialog)
            QTimer.singleShot(300, center_dialog)  # 再延迟一点再次调整，确保窗口尺寸计算完成
            
            # 显示强制更新提示
            CustomMessageBox.warning(
                self,
                "强制更新通知",
                f"当前版本需要强制更新到 {latest_info['version']}，更新已开始下载。",
                [("确定", True)]  # 使用正确的按钮格式
            )
            
        except Exception as e:
            logging.error(f"创建强制更新下载弹窗失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            
            # 出错时使用原来的信号方式
            self.addDownloadTask.emit(url, filename, filesize)
            
            # 显示强制更新提示
            CustomMessageBox.warning(
                self,
                "强制更新通知",
                f"当前版本需要强制更新到 {latest_info['version']}，更新包已添加到下载列表。",
                [("确定", True)]  # 使用正确的按钮格式
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
        