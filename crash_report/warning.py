#!/usr/bin/env python
"""
警告图标绘制模块

动态生成警告图标，避免依赖外部资源文件。
"""

def create_warning_icon(size=48):
    """动态创建警告图标
    
    Args:
        size: 图标尺寸
        
    Returns:
        QPixmap: 图标对象，失败返回None
    """
    try:
        from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath, QPoint
        from PySide6.QtCore import Qt
        
        # 创建透明背景的图片
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        
        # 创建画笔
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置三角形的大小，略小于图标尺寸
        triangle_size = int(size * 0.8)
        # 计算左上角坐标，使三角形居中
        x_offset = (size - triangle_size) // 2
        y_offset = x_offset
        
        # 绘制黄色三角形
        path = QPainterPath()
        path.moveTo(x_offset + triangle_size // 2, y_offset)
        path.lineTo(x_offset, y_offset + triangle_size)
        path.lineTo(x_offset + triangle_size, y_offset + triangle_size)
        path.lineTo(x_offset + triangle_size // 2, y_offset)
        
        # 填充黄色
        painter.setBrush(QBrush(QColor(255, 200, 0)))
        # 设置黑色边框
        painter.setPen(QPen(Qt.black, 2))
        painter.drawPath(path)
        
        # 绘制感叹号
        painter.setPen(QPen(Qt.black, 3))
        # 感叹号竖线
        exclamation_height = int(triangle_size * 0.4)
        center_x = size // 2
        base_y = y_offset + int(triangle_size * 0.4)
        painter.drawLine(center_x, base_y, center_x, base_y + exclamation_height)
        
        # 感叹号点
        dot_y = base_y + exclamation_height + int(triangle_size * 0.1)
        painter.setBrush(QBrush(Qt.black))
        painter.drawEllipse(QPoint(center_x, dot_y), 2, 2)
        
        painter.end()
        return pixmap
    except Exception as e:
        import sys
        print(f"创建警告图标失败: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    """测试警告图标绘制"""
    import sys
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    
    window = QWidget()
    layout = QVBoxLayout(window)
    
    # 创建不同尺寸的图标
    for size in [24, 32, 48, 64, 96]:
        icon = create_warning_icon(size)
        if icon:
            label = QLabel(f"警告图标 {size}x{size}")
            icon_label = QLabel()
            icon_label.setPixmap(icon)
            layout.addWidget(label)
            layout.addWidget(icon_label)
    
    window.setWindowTitle("警告图标测试")
    window.show()
    
    sys.exit(app.exec()) 