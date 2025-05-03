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

class UpdatePage(QWidget):
    updateFound = Signal(str, str)  # 版本号, 更新内容
    updateError = Signal(str)       # 错误信息
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.font_manager = FontManager()
        
        # 软件当前版本
        self.current_version = "1.0.2"
        
        # 检查更新API地址
        self.api_url = "https://zzbuaoye.dpdns.org"
        
        # 缓存文件路径
        self.cache_dir = os.path.join(os.path.expanduser("~"), ".hanabi_dm")
        self.cache_file = os.path.join(self.cache_dir, "update_cache.json")
        
        # 确保缓存目录存在
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        
        # 加载缓存的版本信息
        self.cached_data = self.load_cache()
        self.has_newer_version = False
        
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
        
        # 如果启用了自动检查更新，程序启动后自动检查
        if self.config_manager.get_auto_check_update():
            # 如果上次检查距今已超过24小时，则重新检查
            if self.should_check_again():
                QTimer.singleShot(3000, self.check_update)
            else:
                # 否则直接使用缓存数据
                self.update_ui_from_cache()
    
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
    
    def check_update(self):
        self.check_button.setEnabled(False)
        self.status_label.setText("正在检查更新...")
        self.status_label.setStyleSheet("color: #B39DDB; font-size: 13px; background-color: transparent;")
        
        # 记录检查时间
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_check_label.setText(f"上次检查：{now}")
        
        # 模拟网络请求检查更新
        # 实际项目中应使用QNetworkAccessManager或requests在线程中进行
        try:
            response = requests.get(f"{self.api_url}/HanabiDM/version.json", timeout=10)
            if response.status_code == 200:
                data = response.json()
                latest = data.get("latest", {})
                
                if not latest:
                    self.status_label.setText("检查更新失败: 无效的版本信息")
                    self.status_label.setStyleSheet("color: #F44336; font-size: 13px; background-color: transparent;")
                    return
                
                # 保存缓存和检查时间
                data["last_check_time"] = now
                data["last_check_timestamp"] = time.time()
                self.cached_data = data
                self.save_cache(data)
                
                # 检查是否有新版本
                if self.compare_versions(latest["version"], self.current_version) > 0:
                    # 有更新版本
                    self.has_newer_version = True
                    self.status_label.setText(f"发现新版本: {latest['version']}")
                    self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px; background-color: transparent;")
                    
                    # 更新更新日志
                    self.update_release_notes(latest, True)
                    
                    # 发出更新信号
                    self.updateFound.emit(latest["version"], json.dumps(latest))
                else:
                    # 已经是最新版本
                    self.has_newer_version = False
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
        
        except Exception as e:
            # 检查更新失败
            self.status_label.setText(f"检查更新失败: {str(e)}")
            self.status_label.setStyleSheet("color: #F44336; font-size: 13px; background-color: transparent;")
            self.updateError.emit(str(e))
        
        finally:
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
                download_btn.clicked.connect(lambda: self.download_update(url))
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
    
    def download_update(self, url):
        # 实际项目中应下载安装包或启动更新程序
        self.status_label.setText(f"开始下载更新: {url}")
        # 在实际项目中，你可能会使用内置下载引擎来下载更新
    
    def toggle_auto_check(self, checked):
        self.config_manager.set_auto_check_update(checked)
    
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
        