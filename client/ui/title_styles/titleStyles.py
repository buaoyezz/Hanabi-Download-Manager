from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy, QSystemTrayIcon, QMenu
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QIcon, QPixmap, QAction
from core.font.font_manager import FontManager
import os
import sys

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
        self.font_manager = FontManager()
        
        # 初始化系统托盘
        self.setup_system_tray()
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 0)  # 增加上边距，确保按钮不会太靠近窗口边缘
        self.layout.setSpacing(8)
        
        # 左侧Logo
        self.logo_label = QLabel()
        self.logo_label.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        try:
            # 获取与托盘图标相同的图标路径
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
                pixmap = QPixmap(icon_path)
                scaled_pixmap = pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_label.setPixmap(scaled_pixmap)
            else:
                raise FileNotFoundError(f"Logo文件不存在: {icon_path}")
        except:
            # 如果logo加载失败，使用文本替代
            self.logo_label = QLabel("H")
            self.logo_label.setStyleSheet("""
                background-color: #B39DDB;
                color: #121212;
                font-size: 18px;
                font-weight: bold;
                border-radius: 15px;
                min-width: 30px;
                min-height: 30px;
                max-width: 30px;
                max-height: 30px;
                padding: 0px;
                text-align: center;
                font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei";
            """)
            self.font_manager.apply_font(self.logo_label)
        
        # 左侧部分
        left_part = QWidget()
        left_part.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        left_layout = QHBoxLayout(left_part)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        left_layout.addWidget(self.logo_label)
        # 设置左侧部分宽度固定，与右侧按钮组保持一致
        left_part.setFixedWidth(130)  # 调整为与右侧宽度一致，保持对称
        
        # 中间标题
        self.title_label = QLabel("Hanabi Download Manager")
        self.title_label.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            color: #FFFFFF;
            font-size: 16px;
            font-weight: bold;
            background-color: transparent;
            font-family: "HarmonyOS Sans SC", "Source Han Sans CN", "Microsoft YaHei";
        """)
        self.font_manager.apply_font(self.title_label)
        
        # 右侧控制按钮
        right_part = QWidget()
        right_part.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        right_layout = QHBoxLayout(right_part)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
        # 添加托盘最小化按钮
        self.tray_btn = QPushButton()
        self.tray_btn.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        self.tray_btn.setFixedSize(30, 30)
        self.tray_btn.setObjectName("trayBtn")
        self.tray_btn.setStyleSheet("""
            #trayBtn {
                background-color: transparent;
                color: #9E9E9E;
                border: none;
                border-radius: 15px;
                font-family: 'Material Icons';
                font-size: 16px;
                padding: 0px;
            }
            #trayBtn:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
            #trayBtn:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        self.tray_btn.setText(self.font_manager.get_icon_text("minimize"))
        self.font_manager.apply_icon_font(self.tray_btn, 16)
        self.tray_btn.setToolTip("最小化到托盘")
        self.tray_btn.clicked.connect(self.minimize_to_tray)
        right_layout.addWidget(self.tray_btn)
        
        # 最小化按钮
        self.minimize_btn = QPushButton()
        self.minimize_btn.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        self.minimize_btn.setFixedSize(30, 30)
        self.minimize_btn.setObjectName("minimizeBtn")
        self.minimize_btn.setStyleSheet("""
            #minimizeBtn {
                background-color: transparent;
                color: #9E9E9E;
                border: none;
                border-radius: 15px;
                font-family: 'Material Icons';
                font-size: 16px;
                padding: 0px;
            }
            #minimizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
            #minimizeBtn:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        self.minimize_btn.setText(self.font_manager.get_icon_text("horizontal_rule"))
        self.font_manager.apply_icon_font(self.minimize_btn, 16)
        self.minimize_btn.setToolTip("最小化")
        self.minimize_btn.clicked.connect(self.parent.showMinimized)
        right_layout.addWidget(self.minimize_btn)
        
        # 最大化按钮
        self.maximize_btn = QPushButton()
        self.maximize_btn.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        self.maximize_btn.setFixedSize(30, 30)
        self.maximize_btn.setObjectName("maximizeBtn")
        self.maximize_btn.setStyleSheet("""
            #maximizeBtn {
                background-color: transparent;
                color: #9E9E9E;
                border: none;
                border-radius: 15px;
                font-family: 'Material Icons';
                font-size: 16px;
                padding: 0px;
            }
            #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.1);
                color: #FFFFFF;
            }
            #maximizeBtn:pressed {
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        self.maximize_btn.setText(self.font_manager.get_icon_text("check_box_outline_blank"))
        self.font_manager.apply_icon_font(self.maximize_btn, 16)
        self.maximize_btn.setToolTip("最大化")
        self.maximize_btn.clicked.connect(self.toggle_maximize)
        right_layout.addWidget(self.maximize_btn)
        
        # 关闭按钮
        self.close_btn = QPushButton()
        self.close_btn.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setStyleSheet("""
            #closeBtn {
                background-color: transparent;
                color: #9E9E9E;
                border: none;
                border-radius: 15px;
                font-family: 'Material Icons';
                font-size: 16px;
                padding: 0px;
            }
            #closeBtn:hover {
                background-color: #E53935;
                color: #FFFFFF;
            }
            #closeBtn:pressed {
                background-color: #C62828;
            }
        """)
        self.close_btn.setText(self.font_manager.get_icon_text("close"))
        self.font_manager.apply_icon_font(self.close_btn, 16)
        self.close_btn.setToolTip("关闭")
        self.close_btn.clicked.connect(self.parent.close)
        right_layout.addWidget(self.close_btn)
        
        # 设置右侧部分宽度固定
        right_part.setFixedWidth(130)  # 增加宽度以适应新增的托盘按钮
        
        # 将三个部分添加到主布局中，确保标题居中
        self.layout.addWidget(left_part)
        self.layout.addWidget(self.title_label, 1)  # 1表示拉伸系数，确保中间标题可以拉伸
        self.layout.addWidget(right_part)
        
        # 拖动相关变量
        self.pressing = False
        self.start_point = QPoint(0, 0)
    
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
        tray_menu = QMenu()
        
        # 添加菜单项
        show_action = QAction("显示窗口", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        
        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.parent.close)
        tray_menu.addAction(exit_action)
        
        # 设置托盘菜单
        self.tray_icon.setContextMenu(tray_menu)
        
        # 双击托盘图标显示窗口
        self.tray_icon.activated.connect(self.tray_activated)
    
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
        # 显示系统托盘图标
        if not self.tray_icon.isVisible():
            self.tray_icon.show()
        
        # 隐藏主窗口
        self.parent.hide()
        
        # 发送信号
        self.minimizeToTray.emit()
    
    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.maximize_btn.setText(self.font_manager.get_icon_text("check_box_outline_blank"))
        else:
            self.parent.showMaximized()
            self.maximize_btn.setText(self.font_manager.get_icon_text("crop_free"))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pressing = True
            self.start_point = event.position().toPoint()
    
    def mouseMoveEvent(self, event):
        if self.pressing and not self.parent.isMaximized():
            self.parent.move(self.parent.pos() + event.position().toPoint() - self.start_point)
    
    def mouseReleaseEvent(self, event):
        self.pressing = False


