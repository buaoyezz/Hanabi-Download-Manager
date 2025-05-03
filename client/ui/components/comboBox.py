from PySide6.QtWidgets import QComboBox, QStyledItemDelegate, QListView, QStyle
from PySide6.QtCore import Qt, QRect, QPoint, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QFontMetrics
from core.font.font_manager import FontManager

class CustomComboBox(QComboBox):
    """自定义下拉框组件，符合应用的深色主题设计"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        self.font_manager.apply_font(self)
        
        # 设置视图为自定义列表视图
        self.view = QListView()
        self.view.setObjectName("comboBoxListView")
        self.view.setTextElideMode(Qt.ElideRight)
        self.view.setAlternatingRowColors(False)
        self.view.setStyleSheet("""
            background-color: #252525;
            color: #FFFFFF;
            border: 1px solid #3C3C3C;
            border-radius: 6px;
            padding: 5px;
        """)
        self.setView(self.view)
        
        # 设置自定义项委托
        self.delegate = CustomItemDelegate(self)
        self.setItemDelegate(self.delegate)
        
        # 基本属性设置
        self.setMaxVisibleItems(8)  # 最多显示8个选项
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(36)  # 设置最小高度
        
        # 设置样式表
        self.setStyleSheet("""
            CustomComboBox {
                background-color: #2D2D30;
                color: #FFFFFF;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 3px 12px 3px 12px;
                min-width: 120px;
                font-size: 14px;
            }
            
            CustomComboBox:hover {
                border: 1px solid #7E57C2;
                background-color: #333337;
            }
            
            CustomComboBox:focus {
                border: 1px solid #B39DDB;
            }
            
            CustomComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 30px;
                border: none;
                background: transparent;
            }
            
            CustomComboBox::down-arrow {
                width: 0;
                height: 0;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #AAAAAA;
                margin-right: 10px;
            }
            
            CustomComboBox::down-arrow:hover {
                border-top: 5px solid #B39DDB;
            }
            
            CustomComboBox QAbstractItemView {
                background-color: #252525;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 5px;
                selection-background-color: #7E57C2;
                selection-color: #FFFFFF;
                outline: none;
                color: #FFFFFF;
            }
            
            #comboBoxListView {
                background-color: #252525;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 5px;
                outline: none;
                color: #FFFFFF;
            }
            
            #comboBoxListView::item {
                background-color: transparent;
                color: #FFFFFF;
                padding: 5px 10px;
                border-radius: 4px;
                min-height: 24px;
            }
            
            #comboBoxListView::item:selected {
                background-color: #7E57C2;
                color: #FFFFFF;
            }
            
            #comboBoxListView::item:hover:!selected {
                background-color: #333337;
                color: #FFFFFF;
            }
        """)
    
    def paintEvent(self, event):
        """自定义绘制下拉框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制背景
        rect = self.rect().adjusted(0, 0, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        
        # 设置背景色
        if self.hasFocus():
            background_color = QColor("#2D2D30")
        elif self.underMouse():
            background_color = QColor("#333337")
        else:
            background_color = QColor("#2D2D30")
        
        # 绘制背景
        painter.fillPath(path, background_color)
        
        # 绘制边框
        if self.hasFocus():
            border_color = QColor("#B39DDB")  # 紫色聚焦边框
        elif self.underMouse():
            border_color = QColor("#7E57C2")  # 较浅的紫色悬停边框
        else:
            border_color = QColor("#3C3C3C")  # 默认边框颜色
        
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawPath(path)
        
        # 绘制当前文本
        text_rect = rect.adjusted(12, 0, -30, 0)  # 左侧留出内边距，右侧留出下拉箭头的空间
        text = self.currentText()
        if not text:
            # 如果没有文本，绘制占位符
            painter.setPen(QColor("#777777"))
            painter.drawText(text_rect, Qt.AlignVCenter, self.placeholderText() or "")
        else:
            # 绘制当前文本
            painter.setPen(QColor("#FFFFFF"))
            # 如果文本太长，进行裁剪并添加省略号
            metrics = QFontMetrics(self.font())
            elided_text = metrics.elidedText(text, Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignVCenter, elided_text)
        
        # 绘制下拉箭头
        arrow_rect = QRect(rect.width() - 25, rect.height() // 2 - 3, 10, 6)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#AAAAAA") if not self.underMouse() else QColor("#B39DDB"))
        arrow_path = QPainterPath()
        arrow_path.moveTo(arrow_rect.left(), arrow_rect.top())
        arrow_path.lineTo(arrow_rect.left() + arrow_rect.width() // 2, arrow_rect.bottom())
        arrow_path.lineTo(arrow_rect.right(), arrow_rect.top())
        arrow_path.closeSubpath()
        painter.drawPath(arrow_path)
    
    def addIconItem(self, text, icon_name=None, data=None):
        """添加带图标的选项
        
        Args:
            text: 显示的文本
            icon_name: 图标名称（Fluent图标）
            data: 用户数据
        """
        if icon_name:
            # 使用FontManager获取图标代码
            icon_text = self.font_manager.get_icon_text(icon_name)
            item_text = f"{icon_text} {text}"
            
            # 添加项
            self.addItem(item_text)
            
            # 设置用户数据
            if data is not None:
                self.setItemData(self.count() - 1, data, Qt.UserRole)
                
            # 设置图标标志
            self.setItemData(self.count() - 1, True, Qt.UserRole + 1)
            # 存储图标名称
            self.setItemData(self.count() - 1, icon_name, Qt.UserRole + 2)
        else:
            # 添加普通项
            self.addItem(text)
            if data is not None:
                self.setItemData(self.count() - 1, data, Qt.UserRole)
    
    def setCurrentByUserData(self, user_data):
        """根据用户数据设置当前项"""
        for i in range(self.count()):
            if self.itemData(i, Qt.UserRole) == user_data:
                self.setCurrentIndex(i)
                return True
        return False
    
    def getCurrentUserData(self):
        """获取当前项的用户数据"""
        return self.currentData(Qt.UserRole)

class CustomItemDelegate(QStyledItemDelegate):
    """自定义项委托，用于绘制下拉列表中的选项"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.font_manager = FontManager()
    
    def paint(self, painter, option, index):
        """绘制下拉列表项"""
        # 设置渲染优化
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 计算绘制区域
        rect = option.rect
        
        # 绘制背景
        if option.state & QStyle.State_Selected:
            # 选中状态
            painter.fillRect(rect, QColor("#7E57C2"))
        elif option.state & QStyle.State_MouseOver:
            # 鼠标悬停状态
            painter.fillRect(rect, QColor("#333337"))
        else:
            # 普通状态
            painter.fillRect(rect, QColor("#252525"))
        
        # 获取文本
        text = index.data()
        
        # 检查是否有图标标志
        has_icon = index.data(Qt.UserRole + 1)
        
        if has_icon:
            # 如果有图标，从文本中分离出图标和文本
            # 假设格式为"图标代码 文本"
            parts = text.split(" ", 1)
            if len(parts) > 1:
                icon_text = parts[0]
                display_text = parts[1]
                
                # 绘制图标
                icon_rect = QRect(rect.left() + 5, rect.top(), rect.height(), rect.height())
                painter.save()
                # 设置图标颜色
                if option.state & QStyle.State_Selected:
                    painter.setPen(QColor("#FFFFFF"))
                else:
                    painter.setPen(QColor("#B39DDB"))  # 紫色图标
                
                # 获取图标字体
                icon_font = self.font_manager.create_icon_font(14)
                painter.setFont(icon_font)
                painter.drawText(icon_rect, Qt.AlignCenter, icon_text)
                painter.restore()
                
                # 绘制文本
                text_rect = rect.adjusted(icon_rect.width() + 10, 0, -5, 0)
                painter.save()
                if option.state & QStyle.State_Selected:
                    painter.setPen(QColor("#FFFFFF"))
                else:
                    painter.setPen(QColor("#FFFFFF"))  # 修改为白色更容易看见
                
                # 使用常规字体
                text_font = option.font
                painter.setFont(text_font)
                
                # 如果文本太长，进行裁剪并添加省略号
                metrics = QFontMetrics(text_font)
                elided_text = metrics.elidedText(display_text, Qt.ElideRight, text_rect.width())
                painter.drawText(text_rect, Qt.AlignVCenter, elided_text)
                painter.restore()
            else:
                # 如果分离失败，直接显示全部文本
                super().paint(painter, option, index)
        else:
            # 没有图标的普通文本
            text_rect = rect.adjusted(10, 0, -5, 0)
            painter.save()
            if option.state & QStyle.State_Selected:
                painter.setPen(QColor("#FFFFFF"))
            else:
                painter.setPen(QColor("#FFFFFF"))  # 修改为白色更容易看见
            
            # 使用常规字体
            text_font = option.font
            painter.setFont(text_font)
            
            # 如果文本太长，进行裁剪并添加省略号
            metrics = QFontMetrics(text_font)
            elided_text = metrics.elidedText(text, Qt.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignVCenter, elided_text)
            painter.restore()
    
    def sizeHint(self, option, index):
        """返回项的大小提示"""
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(36, size.height()))  # 确保最小高度为36px
