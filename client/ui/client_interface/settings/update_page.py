from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLabel, QSpacerItem, QSizePolicy, QScrollArea, QFrame)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QColor
from core.font.font_manager import FontManager
from client.ui.components.customMessagebox import CustomMessageBox
import requests
import json
import os
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
        self.current_version = "1.0.0"
        
        # 检查更新API地址
        self.api_url = "https://zzbuaoye.dpdns.org"
        
        # 初始化UI
        self.setup_ui()
        
        # 如果启用了自动检查更新，程序启动后自动检查
        if self.config_manager.get_auto_check_update():
            QTimer.singleShot(3000, self.check_update)
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 版本信息卡片
        version_card = self.create_card()
        version_layout = QVBoxLayout(version_card)
        version_layout.setContentsMargins(20, 20, 20, 20)
        version_layout.setSpacing(15)
        
        # 标题
        title_layout = QHBoxLayout()
        
        # 添加图标
        icon_label = QLabel()
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(24)
        icon_label.setFont(icon_font)
        icon_label.setText(self.font_manager.get_icon_text("browser_updated"))
        icon_label.setStyleSheet("color: #B39DDB; background-color: transparent;")
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
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(16)
        check_icon.setFont(icon_font)
        check_icon.setText(self.font_manager.get_icon_text("refresh"))
        check_icon.setStyleSheet("color: #FFFFFF; background-color: transparent;")
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
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(16)
        auto_icon.setFont(icon_font)
        auto_icon.setText(self.font_manager.get_icon_text("schedule"))
        auto_icon.setStyleSheet("color: #FFFFFF; background-color: transparent;")
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
        
        main_layout.addWidget(version_card)
        
        # 更新日志卡片
        update_log_card = self.create_card()
        update_log_layout = QVBoxLayout(update_log_card)
        update_log_layout.setContentsMargins(20, 20, 20, 20)
        update_log_layout.setSpacing(15)
        
        # 日志标题
        log_title_layout = QHBoxLayout()
        
        log_icon = QLabel()
        icon_font = QFont("Material Icons")
        icon_font.setPixelSize(24)
        log_icon.setFont(icon_font)
        log_icon.setText(self.font_manager.get_icon_text("history"))
        log_icon.setStyleSheet("color: #B39DDB; background-color: transparent;")
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
        
        # 创建滚动区域用于显示更新日志
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setStyleSheet("""
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
        
        # 创建内容部件
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
        
        scroll_area.setWidget(self.log_content)
        update_log_layout.addWidget(scroll_area)
        
        main_layout.addWidget(update_log_card, 1)  # 1表示拉伸系数，使更新日志卡片可拉伸
        
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
                
                # 检查是否有新版本
                if self.compare_versions(latest["version"], self.current_version) > 0:
                    # 有更新版本
                    self.status_label.setText(f"发现新版本: {latest['version']}")
                    self.status_label.setStyleSheet("color: #4CAF50; font-size: 13px; background-color: transparent;")
                    
                    # 更新更新日志
                    self.update_release_notes(latest)
                    
                    # 发出更新信号
                    self.updateFound.emit(latest["version"], json.dumps(latest))
                else:
                    # 已经是最新版本
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
                        self.update_release_notes(current_version_info)
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
    
    def update_release_notes(self, latest):
        # 清除原有内容
        for i in reversed(range(self.log_layout.count())):
            item = self.log_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加新版本信息
        version_label = QLabel(f"<b>版本 {latest['version']}</b> ({latest['date']})")
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
        if latest.get("force_update", False):
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
        
        # 添加下载按钮
        if download_info.get("url"):
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
            icon_font = QFont("Material Icons")
            icon_font.setPixelSize(16)
            download_icon.setFont(icon_font)
            download_icon.setText(self.font_manager.get_icon_text("download"))
            download_icon.setStyleSheet("color: #FFFFFF; background-color: transparent;")
            download_layout.addWidget(download_icon)
            
            # 文本
            download_text = QLabel("下载更新")
            download_text.setStyleSheet("color: #FFFFFF; background-color: transparent; font-weight: bold;")
            self.font_manager.apply_font(download_text)
            download_layout.addWidget(download_text)
            
            # 检查我又没有放下载链接
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
        # 简单版本比较：将版本号分解为组件，然后比较各个组件
        v1_components = list(map(int, version1.split('.')))
        v2_components = list(map(int, version2.split('.')))
        
        # 确保两个版本号具有相同数量的组件
        while len(v1_components) < len(v2_components):
            v1_components.append(0)
        while len(v2_components) < len(v1_components):
            v2_components.append(0)
        
        # 比较各个组件
        for i in range(len(v1_components)):
            if v1_components[i] > v2_components[i]:
                return 1  # version1 更新
            elif v1_components[i] < v2_components[i]:
                return -1  # version2 更新
        
        return 0  # 版本相同
