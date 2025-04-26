from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtGui import QIcon, QPixmap
from core.font.font_manager import FontManager

class TitleBar(QWidget):
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(50)
        self.setStyleSheet("""
            background-color: transparent;
        """)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 0)  # 增加上边距，确保按钮不会太靠近窗口边缘
        self.layout.setSpacing(8)
        
        # 左侧Logo
        self.logo_label = QLabel()
        self.logo_label.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        try:
            pixmap = QPixmap("resources/logo.png")
            scaled_pixmap = pixmap.scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
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
        left_part.setFixedWidth(105)  # 增加左侧宽度从90到105，使标题整体向右偏移
        
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
            padding-right: 15px;  /* 添加右边距，进一步微调向右对齐 */
        """)
        self.font_manager.apply_font(self.title_label)
        
        # 右侧控制按钮
        right_part = QWidget()
        right_part.setAttribute(Qt.WA_TranslucentBackground)  # 确保透明
        right_layout = QHBoxLayout(right_part)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        
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
        self.close_btn.clicked.connect(self.parent.close)
        right_layout.addWidget(self.close_btn)
        
        # 设置右侧部分宽度固定
        right_part.setFixedWidth(90)
        
        # 将三个部分添加到主布局中，确保标题居中
        self.layout.addWidget(left_part)
        self.layout.addWidget(self.title_label, 1)  # 1表示拉伸系数，确保中间标题可以拉伸
        self.layout.addWidget(right_part)
        
        # 拖动相关变量
        self.pressing = False
        self.start_point = QPoint(0, 0)
    
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


