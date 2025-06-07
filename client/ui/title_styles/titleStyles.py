from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy, QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt, QPoint, Signal, QTimer
from PySide6.QtGui import QIcon, QPixmap, QAction, QFont
from core.font.font_manager import FontManager
from client.I18N.i18n import i18n
import os
import sys
import logging

class TitleBar(QWidget):
    # 添加信号用于托盘操作
    minimizeToTray = Signal()
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(50)
        self.setStyleSheet("""
            background-color: transparent;
        """)
        
        # 初始化字体管理器
        self.font_manager = parent.font_manager if hasattr(parent, 'font_manager') else FontManager()
        
        # 初始化系统托盘
        self.setup_system_tray()
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 0)  # 增加上边距，确保按钮不会太靠近窗口边缘
        self.layout.setSpacing(8)
        
        # 构建UI
        self.build_ui()
        
        # 拖动相关变量
        self.pressing = False
        self.start_point = QPoint(0, 0)
        
        # 连接语言变更信号
        i18n.language_changed.connect(self.update_tray_menu_texts)
    
    def setup_system_tray(self):
        """初始化系统托盘"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # 获取应用图标（使用主窗口的图标）
        if hasattr(self.parent, 'app_icon') and self.parent.app_icon:
            self.tray_icon.setIcon(self.parent.app_icon)
        else:
            # 尝试设置托盘图标
            try:
                # 使用与主窗口相同的方法获取图标路径
                if getattr(sys, 'frozen', False):
                    # 如果是打包环境
                    application_path = os.path.dirname(sys.executable)
                else:
                    # 如果是开发环境
                    application_path = os.path.dirname(os.path.abspath(__file__))
                    # 转到项目根目录
                    application_path = os.path.dirname(os.path.dirname(os.path.dirname(application_path)))
                    
                icon_path = os.path.join(application_path, "resources", "logo.png")
                
                if os.path.exists(icon_path):
                    icon = QIcon(icon_path)
                    self.tray_icon.setIcon(icon)
                else:
                    # 如果图标加载失败，使用默认图标
                    self.tray_icon.setIcon(QIcon.fromTheme("application-x-executable"))
            except:
                # 如果图标加载失败，使用默认图标
                self.tray_icon.setIcon(QIcon.fromTheme("application-x-executable"))
        
        # 创建托盘菜单
        self.tray_menu = QMenu()
        # 设置菜单样式，与应用主题一致
        self.tray_menu.setStyleSheet("""
            QMenu {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 4px;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px 5px 10px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #3F3F46;
                color: #B39DDB;
            }
            QMenu::separator {
                height: 1px;
                background-color: #3C3C3C;
                margin: 5px 2px;
            }
        """)
        
        # 添加菜单项 - 使用字体图标
        self.show_action = QAction(i18n.get_text("show_main_window"), self)
        # 设置图标如果有字体管理器
        if hasattr(self, 'font_manager') and self.font_manager:
            show_icon = self.font_manager.get_qicon("ic_fluent_window_24_regular")
            if show_icon:
                self.show_action.setIcon(show_icon)
        self.show_action.triggered.connect(self.show_window)
        self.tray_menu.addAction(self.show_action)
        
        # 添加分隔线
        self.tray_menu.addSeparator()
        
        # 添加下载管理项
        self.download_action = QAction(i18n.get_text("downloads"), self)
        if hasattr(self, 'font_manager') and self.font_manager:
            download_icon = self.font_manager.get_qicon("ic_fluent_arrow_download_24_regular")
            if download_icon:
                self.download_action.setIcon(download_icon)
        self.download_action.triggered.connect(lambda: self.switch_to_page("downloads"))
        self.tray_menu.addAction(self.download_action)
        
        # 添加历史记录项
        self.history_action = QAction(i18n.get_text("history"), self)
        if hasattr(self, 'font_manager') and self.font_manager:
            history_icon = self.font_manager.get_qicon("ic_fluent_history_24_regular")
            if history_icon:
                self.history_action.setIcon(history_icon)
        self.history_action.triggered.connect(lambda: self.switch_to_page("history"))
        self.tray_menu.addAction(self.history_action)
        
        # 添加设置项
        self.settings_action = QAction(i18n.get_text("settings"), self)
        if hasattr(self, 'font_manager') and self.font_manager:
            settings_icon = self.font_manager.get_qicon("ic_fluent_settings_24_regular")
            if settings_icon:
                self.settings_action.setIcon(settings_icon)
        self.settings_action.triggered.connect(lambda: self.switch_to_page("settings"))
        self.tray_menu.addAction(self.settings_action)
        
        # 添加分隔线
        self.tray_menu.addSeparator()
        
        # 退出项
        self.exit_action = QAction(i18n.get_text("exit_app"), self)
        if hasattr(self, 'font_manager') and self.font_manager:
            exit_icon = self.font_manager.get_qicon("ic_fluent_power_24_regular")
            if exit_icon:
                self.exit_action.setIcon(exit_icon)
        # 修改退出动作，确保应用正确退出
        self.exit_action.triggered.connect(self.exit_application)
        self.tray_menu.addAction(self.exit_action)
        
        # 设置托盘菜单
        self.tray_icon.setContextMenu(self.tray_menu)
        
        # 双击托盘图标显示窗口
        self.tray_icon.activated.connect(self.tray_activated)
    
    def update_tray_menu_texts(self):
        # 更新托盘菜单文本
        self.show_action.setText(i18n.get_text("show_main_window"))
        self.download_action.setText(i18n.get_text("downloads"))
        self.history_action.setText(i18n.get_text("history"))
        self.settings_action.setText(i18n.get_text("settings"))
        self.exit_action.setText(i18n.get_text("exit_app"))
        
        # 更新按钮提示
        if hasattr(self, 'minimize_btn'):
            self.minimize_btn.setToolTip(i18n.get_text("minimize"))
        if hasattr(self, 'maximize_btn'):
            if self.parent.isMaximized():
                self.maximize_btn.setToolTip(i18n.get_text("restore"))
            else:
                self.maximize_btn.setToolTip(i18n.get_text("maximize"))
        if hasattr(self, 'close_btn'):
            self.close_btn.setToolTip(i18n.get_text("close"))
    
    def tray_activated(self, reason):
        """托盘图标被激活时的处理函数"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window()
    
    def show_window(self):
        """显示主窗口"""
        self.parent.showNormal()
        self.parent.activateWindow()
    
    def minimize_to_tray(self):
        """最小化到系统托盘"""
        logging.info("执行 TitleBar.minimize_to_tray()")
        
        # 显示系统托盘图标
        if not self.tray_icon.isVisible():
            logging.info("托盘图标未显示，正在显示...")
            self.tray_icon.show()
            
            # 确保托盘图标显示
            QTimer.singleShot(100, self._ensure_tray_visible)
        
        # 隐藏主窗口
        self.parent.hide()
        logging.info("已隐藏主窗口")
        
        # 发送信号
        self.minimizeToTray.emit()
        logging.info("发送了 minimizeToTray 信号")
    
    def _ensure_tray_visible(self):
        """确保托盘图标可见的辅助方法"""
        if not self.tray_icon.isVisible():
            logging.info("托盘图标仍未显示，第二次尝试显示")
            self.tray_icon.show()
        else:
            logging.info("托盘图标已显示成功")
    
    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            # 恢复时显示最大化图标
            self.set_button_icon(self.maximize_btn, "maximize", i18n.get_text("maximize"))
        else:
            self.parent.showMaximized()
            # 最大化时显示还原图标
            self.set_button_icon(self.maximize_btn, "arrow_maximize", i18n.get_text("restore"))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressing = True
            self.start_point = event.position().toPoint()
    
    def mouseMoveEvent(self, event):
        if self.pressing and not self.parent.isMaximized():
            self.parent.move(self.parent.pos() + event.position().toPoint() - self.start_point)
    
    def mouseReleaseEvent(self, event):
        self.pressing = False

    def set_button_icon(self, button, icon_name, tooltip=""):
        """设置按钮图标并应用样式
        
        Args:
            button: QPushButton对象
            icon_name: Fluent图标名称
            tooltip: 按钮提示文本
        """
        import logging
        logging.debug(f"设置按钮图标: {icon_name}")
        
        try:
            # 获取图标Unicode并设置
            icon_text = self.font_manager.get_icon_text(icon_name)
            if not icon_text:
                # 如果没有找到图标，尝试添加前缀再查找
                if not icon_name.startswith("ic_fluent_"):
                    icon_name = f"ic_fluent_{icon_name}_24_regular"
                    icon_text = self.font_manager.get_icon_text(icon_name)
                
                # 如果仍然找不到图标，使用默认的"⚠"字符
                if not icon_text:
                    icon_text = "⚠"
                    logging.warning(f"未找到图标: {icon_name}，使用默认警告符号")
            
            button.setText(icon_text)
            
            # 设置图标字体
            button.setFont(QFont(self.font_manager.fluent_icons_font, 14))
            
            # 不要通过拼接方式添加样式表，这可能导致语法错误
            # 使用单独的属性设置颜色
            button.setProperty("iconColor", "#FFFFFF")
            
            # 如果提供了提示文本，设置提示
            if tooltip:
                button.setToolTip(tooltip)
                
        except Exception as e:
            logging.error(f"设置按钮图标失败: {e}")
            # 使用默认的"⚠"字符作为回退图标
            button.setText("⚠")
            if tooltip:
                button.setToolTip(tooltip)

    def build_ui(self):
        """构建标题栏UI"""
        # 标题区域布局
        left_layout = QHBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)
        
        # 使用QSpacerItem使标题区域和右侧控制按钮分隔
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        # 右侧区域布局
        right_layout = QHBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)  # 控制按钮之间的间距
        
        # 添加自定义区域到布局
        self.layout.addLayout(left_layout)
        self.layout.addItem(spacer)
        self.layout.addLayout(right_layout)
        
        # ==== 标题部分 ====
        # 添加应用标题
        title_label = QLabel("Hanabi Download Manager")
        title_font = self.font_manager.create_optimized_font(is_bold=False, size=11)
        title_label.setFont(title_font)
        title_label.setStyleSheet("""
            color: #FFFFFF;
            background-color: transparent;
            font-weight: bold;
            margin-left: 5px;
        """)
        left_layout.addWidget(title_label)
        
        # ==== 右侧控制按钮 ====
        # 先添加版本标签
        version_label = QLabel(f"v{i18n.client_version}")
        version_label.setStyleSheet("""
            color: #9E9E9E;
            background-color: transparent;
            font-size: 10px;
            margin-right: 8px;
        """)
        right_layout.addWidget(version_label)
        
        # 最小化到托盘按钮
        self.min_to_tray_btn = QPushButton()
        self.min_to_tray_btn.setAttribute(Qt.WA_TranslucentBackground)
        self.min_to_tray_btn.setFixedSize(30, 30)
        self.min_to_tray_btn.setObjectName("minToTrayBtn")
        self.min_to_tray_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 15px;
                background-color: transparent;
                margin: 0;
                padding: 0;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        # 设置托盘图标
        self.set_button_icon(self.min_to_tray_btn, "ic_fluent_minimize_24_regular", "最小化到托盘")
        self.min_to_tray_btn.clicked.connect(self.minimize_to_tray)
        right_layout.addWidget(self.min_to_tray_btn)
        
        # 最小化按钮
        self.minimize_btn = QPushButton()
        self.minimize_btn.setAttribute(Qt.WA_TranslucentBackground)
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.setObjectName("minimizeBtn")
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 15px;
                background-color: transparent;
                margin: 0;
                padding: 0;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        # 设置最小化图标
        self.set_button_icon(self.minimize_btn, "ic_fluent_subtract_24_regular", "最小化")
        self.minimize_btn.clicked.connect(self.parent.showMinimized)
        right_layout.addWidget(self.minimize_btn)
        
        # 最大化按钮
        self.maximize_btn = QPushButton()
        self.maximize_btn.setAttribute(Qt.WA_TranslucentBackground)
        self.maximize_btn.setFixedSize(30, 30)
        self.maximize_btn.setObjectName("maximizeBtn")
        self.maximize_btn.setStyleSheet("""
            #maximizeBtn {
                background-color: transparent;
                color: #FFFFFF;
                border: none;
                border-radius: 15px;
                font-size: 16px;
                padding: 0;
            }
            #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
            #maximizeBtn:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        self.set_button_icon(self.maximize_btn, "maximize", i18n.get_text("maximize"))
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        right_layout.addWidget(self.maximize_btn)
        
        # 关闭按钮
        self.close_btn = QPushButton()
        self.close_btn.setAttribute(Qt.WA_TranslucentBackground)
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setStyleSheet("""
            #closeBtn {
                background-color: transparent;
                color: #FFFFFF;
                border: none;
                border-radius: 15px;
                font-size: 16px;
                padding: 0;
            }
            #closeBtn:hover {
                background-color: #E53935;
                color: #FFFFFF;
            }
            #closeBtn:pressed {
                background-color: #C62828;
            }
        """)
        self.set_button_icon(self.close_btn, "dismiss", "关闭")
        self.close_btn.clicked.connect(self.handle_close_button)
        right_layout.addWidget(self.close_btn)

    def switch_to_page(self, page_id):
        """切换到指定页面"""
        # 先显示窗口
        self.show_window()
        
        # 然后切换页面 - 如果父窗口有pages_manager
        if hasattr(self.parent, 'pages_manager'):
            QTimer.singleShot(100, lambda: self.parent.pages_manager.switch_page(page_id))
    
    def exit_application(self):
        """确保应用程序完全退出"""
        # 停止所有可能的后台任务
        if hasattr(self.parent, 'download_tasks'):
            for task in self.parent.download_tasks:
                if task.get('status') == '下载中' and task.get('manager'):
                    task['manager'].stop()
        
        # 确保托盘图标被隐藏
        if self.tray_icon.isVisible():
            self.tray_icon.hide()
        
        # 退出应用程序
        import sys
        sys.exit(0)

    def handle_close_button(self):
        """处理关闭按钮点击事件"""
        import logging
        logging.info("关闭按钮被点击")
        
        # 检查配置，看是否需要最小化到托盘
        # 如果父窗口有配置管理器，查询最小化到托盘设置
        close_to_tray = True  # 默认最小化到托盘
        
        if hasattr(self.parent, 'config_manager'):
            try:
                close_to_tray = self.parent.config_manager.get_setting("window", "close_to_tray", True)
                logging.info(f"从配置中读取 close_to_tray: {close_to_tray}")
            except Exception as e:
                logging.error(f"读取 close_to_tray 设置失败: {e}")
        
        # 根据配置决定行为
        if close_to_tray:
            logging.info("根据配置，最小化到托盘而非关闭")
            self.minimize_to_tray()
        else:
            logging.info("根据配置，直接关闭应用")
            self.parent.close()


