from PySide6.QtWidgets import (QStackedWidget, QPushButton, QVBoxLayout, QWidget, 
                              QHBoxLayout, QLabel, QSizePolicy, QScrollArea)
from PySide6.QtCore import Qt, QObject, Signal, QEasingCurve, QPropertyAnimation, QParallelAnimationGroup, QTimer
from PySide6.QtGui import QFont

from core.font.font_manager import FontManager
from client.ui.components.scrollStyle import ScrollStyle
from client.ui.client_interface.history_window import HistoryWindow
from client.I18N.i18n import i18n

class CategoryButton(QPushButton):
    def __init__(self, text, parent=None, icon_code=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedHeight(44)  # 增加高度使其更易点击
        self.icon_code = icon_code
        self.text_content = text
        
        # 使用布局来放置图标和文本
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 0, 15, 0)
        self.layout.setSpacing(12)  # 增加间距使布局更舒适
        
        # 创建图标标签
        if icon_code:
            self.font_manager = FontManager()
            self.icon_label = QLabel()
            
            # 使用font_manager应用图标字体并设置图标
            self.font_manager.apply_icon_font(self.icon_label, icon_code, size=18)
            
            self.layout.addWidget(self.icon_label)
        
        # 创建文本标签 - 确保只添加一个文本标签
        self.text_label = QLabel(text)
        self.layout.addWidget(self.text_label)
        self.layout.addStretch()
        
        # 设置基本样式
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 15px;
                padding: 5px 0px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
            QPushButton:checked {
                background-color: rgba(179, 157, 219, 0.2);
                border: none;
            }
        """)
        
        # 单独设置标签样式
        self.updateStyle(self.isChecked())
    
    def setChecked(self, checked):
        super().setChecked(checked)
        self.updateStyle(checked)
    
    def updateStyle(self, checked):
        if checked:
            if hasattr(self, 'icon_label') and self.icon_label:
                self.icon_label.setStyleSheet("color: #B39DDB; background-color: transparent; font-size: 14px;")
                # 确保图标在选中状态下仍然可见
                self.icon_label.show()
            self.text_label.setStyleSheet("color: #B39DDB; background-color: transparent; font-weight: bold; font-size: 14px;")
            # 选中时使用一致的内边距
            self.layout.setContentsMargins(15, 0, 15, 0)
        else:
            if hasattr(self, 'icon_label') and self.icon_label:
                self.icon_label.setStyleSheet("color: #9E9E9E; background-color: transparent; font-size: 14px;")
                # 确保图标在非选中状态下仍然可见
                self.icon_label.show()
            self.text_label.setStyleSheet("color: #9E9E9E; background-color: transparent; font-size: 14px;")
            # 未选中时保持相同间距
            self.layout.setContentsMargins(15, 0, 15, 0)

class PageAnimationManager(QObject):
    def __init__(self):
        super().__init__()
        self.animations = []
        self.is_animating = False
        self.animation_duration = 250  # 减少默认动画时间，使切换更快
    
    def create_page_switch_animation(self, current_page, next_page, direction="left", duration=None):
        if duration is None:
            duration = self.animation_duration
            
        # 如果已经在动画中，打断当前动画
        if self.is_animating:
            self.stop_animations()
            
        # 标记动画状态
        self.is_animating = True
        
        # 获取页面宽度，用于计算偏移量
        width = current_page.width()
        
        # 设置起始位置 - 预先放置好页面
        if direction == "left":
            # 当前页面向左移动，下一页面从右侧进入
            next_page.setGeometry(width, 0, width, current_page.height())
        else:
            # 当前页面向右移动，下一页面从左侧进入
            next_page.setGeometry(-width, 0, width, current_page.height())
        
        # 创建并配置动画组
        animation_group = QParallelAnimationGroup()
        
        # 当前页面的动画
        current_anim = QPropertyAnimation(current_page, b"geometry")
        current_anim.setDuration(duration)
        current_anim.setStartValue(current_page.geometry())
        
        # 设置结束值
        if direction == "left":
            end_current_rect = current_page.geometry().adjusted(-width, 0, -width, 0)
        else:
            end_current_rect = current_page.geometry().adjusted(width, 0, width, 0)
            
        current_anim.setEndValue(end_current_rect)
        current_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # 下一页面的动画
        next_anim = QPropertyAnimation(next_page, b"geometry")
        next_anim.setDuration(duration)
        next_anim.setStartValue(next_page.geometry())
        next_anim.setEndValue(current_page.geometry())  # 直接使用当前页面的几何信息作为目标
        next_anim.setEasingCurve(QEasingCurve.OutCubic)
        
        # 添加动画到组
        animation_group.addAnimation(current_anim)
        animation_group.addAnimation(next_anim)
        
        # 确保下一页面在动画期间可见
        next_page.show()
        next_page.raise_()  # 确保新页面在上层
        
        # 记录动画组
        self.animations.append(animation_group)
        
        # 连接动画完成信号
        animation_group.finished.connect(lambda: self.on_animation_finished(current_page, next_page))
        
        # 启动动画
        animation_group.start()
        
        return animation_group
    
    def on_animation_finished(self, current_page, next_page):
        # 清理可能已完成的动画
        self.animations = [anim for anim in self.animations if anim.state() == QPropertyAnimation.Running]
        
        # 隐藏当前页面
        current_page.hide()
        
        # 重置当前页面和下一页面的几何布局
        parent = next_page.parent()
        if parent and isinstance(parent, QStackedWidget):
            # 确保下一页面在堆叠窗口中正确显示
            parent.setCurrentWidget(next_page)
            
            # 恢复几何布局，以便下次动画正常
            rect = parent.rect()
            next_page.setGeometry(rect)
            current_page.setGeometry(rect)
        
        # 重置动画状态标记
        self.is_animating = False
    
    def stop_animations(self):
        # 复制列表，避免迭代时修改
        animations_copy = list(self.animations)
        for anim in animations_copy:
            if hasattr(anim, 'stop'):
                anim.stop()
        
        # 清空列表
        self.animations.clear()
        self.is_animating = False

class PagesManager(QObject):
        
    # 定义信号
    page_changed = Signal(str)  # 页面变更信号
    
    def __init__(self, sidebar_widget, content_area, main_window=None):
        super().__init__()
        
        # 存储传入的部件
        self.sidebar_widget = sidebar_widget
        self.content_area = content_area
        self.main_window = main_window  # 存储主窗口引用，用于访问资源和配置
        
        # 初始化字体管理器
        self.font_manager = FontManager()
        
        # 创建堆叠窗口用于切换不同页面
        self.stacked_widget = QStackedWidget()
        # 设置堆叠窗口属性，确保显示正确
        self.stacked_widget.setContentsMargins(0, 0, 0, 0)
        self.stacked_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.stacked_widget.setObjectName("mainStackedWidget")
        
        # 初始化页面管理
        self.pages = {}  # 存储页面实例
        self.buttons = {}  # 存储按钮实例
        self.current_page = None  # 当前页面
        self._pending_switch = None  # 待处理的页面切换
        
        # 创建动画管理器
        self.animation_manager = PageAnimationManager()
        
        # 设置堆叠窗口布局
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.stacked_widget)
        
        # 添加定时器用于检查页面状态同步
        self.sync_timer = QTimer(self)
        self.sync_timer.setInterval(500)  # 每500毫秒检查一次
        self.sync_timer.timeout.connect(self.check_page_button_sync)
        self.sync_timer.start()
        
        # 连接语言变更信号
        i18n.language_changed.connect(self.update_all_button_texts)
    
    def check_page_button_sync(self):
        """检查当前页面与按钮选择状态是否同步"""
        if not self.animation_manager.is_animating and self.current_page:
            # 确保当前页面是可见的
            current_widget = self.pages.get(self.current_page)
            if current_widget and not current_widget.isVisible():
                # 强制同步状态
                self.stacked_widget.setCurrentWidget(current_widget)
                current_widget.show()
                
                # 同步按钮状态
                for btn_id, btn in self.buttons.items():
                    btn.setChecked(btn_id == self.current_page)
    
    def update_all_button_texts(self):
        # 更新所有按钮文本为当前语言
        for page_id, button in self.buttons.items():
            # 查找文本标签并直接设置国际化文本
            if hasattr(button, 'text_label') and button.text_label:
                # 设置国际化文本
                if page_id == "home":
                    button.text_label.setText(i18n.get_text("home"))
                elif page_id == "downloads":
                    button.text_label.setText(i18n.get_text("downloads"))
                elif page_id == "history":
                    button.text_label.setText(i18n.get_text("history"))
                elif page_id == "settings":
                    button.text_label.setText(i18n.get_text("settings"))
                elif page_id == "about":
                    button.text_label.setText(i18n.get_text("about"))
                elif page_id == "update":
                    button.text_label.setText(i18n.get_text("update"))
                elif page_id == "extension":
                    button.text_label.setText(i18n.get_text("browser_extension"))
    
    def register_common_pages(self):
        """注册常用页面"""
        # 清空旧有页面和按钮
        if hasattr(self, 'pages'):
            old_pages = list(self.pages.keys())
            for page_id in old_pages:
                self.remove_page(page_id)
        
        # 创建各个页面
        try:
            # 在函数内部导入HomeWindow，避免循环导入
            from client.ui.client_interface.home_window import HomeWindow
            home_page = HomeWindow()
        except Exception as e:
            print(f"创建首页失败: {e}")
            home_page = self.create_generic_page()
            home_page.content_widget.layout().addWidget(QLabel(i18n.get_text("home_load_failed")))
        
        download_page = self.create_download_page()
        history_page = self.create_history_page()  # 使用内部方法创建历史页面
        settings_page = self.main_window.settings_page if hasattr(self.main_window, 'settings_page') else None
        about_page = self.main_window.about_page if hasattr(self.main_window, 'about_page') else None
        update_page = None
        
        # 连接首页的导航信号
        if hasattr(home_page, 'navigate_to'):
            home_page.navigate_to.connect(self.switch_page)
        
        # 获取侧边栏布局
        sidebar_layout = self.sidebar_widget.layout()
        
        # 清除侧边栏布局中的所有按钮，确保按照正确顺序添加
        if sidebar_layout:
            for i in reversed(range(sidebar_layout.count())):
                item = sidebar_layout.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), CategoryButton):
                    widget = item.widget()
                    sidebar_layout.removeWidget(widget)
                    widget.setParent(None)
                    widget.deleteLater()
        
        # 添加中间弹性空间
        if sidebar_layout:
            # 确保只有一个弹性空间
            has_stretch = False
            for i in range(sidebar_layout.count()):
                if sidebar_layout.itemAt(i) and sidebar_layout.itemAt(i).spacerItem():
                    has_stretch = True
                    break
            
            # 如果没有添加过弹性空间，添加一个
            if not has_stretch:
                sidebar_layout.addStretch()
        
        # 直接按照固定顺序添加各个页面
        # 1. 首页
        if home_page:
            self.add_page("home", home_page, "ic_fluent_home_24_regular", i18n.get_text("home"), "top", 0)
        
        # 2. 下载页面
        if download_page:
            self.add_page("downloads", download_page, "ic_fluent_arrow_download_24_regular", i18n.get_text("downloads"), "top", 1)
        
        # 3. 历史页面
        if history_page:
            self.add_page("history", history_page, "ic_fluent_history_24_regular", i18n.get_text("history"), "top", 2)
        
        # 4. 设置页面
        if settings_page:
            self.add_page("settings", settings_page, "ic_fluent_settings_24_regular", i18n.get_text("settings"), "bottom", 1)
        
        # 5. 关于页面
        if about_page:
            self.add_page("about", about_page, "ic_fluent_info_24_regular", i18n.get_text("about"), "bottom", 0)
        
        # 6. 更新页面
        if update_page:
            self.add_page("update", update_page, "ic_fluent_arrow_sync_24_regular", i18n.get_text("update"), "bottom", 2)
        
        # 默认显示首页
        self.switch_page("home")
        
        return {
            "home": home_page,
            "downloads": download_page,
            "history": history_page,
            "settings": settings_page,
            "about": about_page,
            "update": update_page
        }
    
    def create_generic_page(self):
        """创建通用页面"""
        generic_page = QWidget()
        
        # 创建滚动区域
        generic_scroll = QScrollArea()
        generic_scroll.setWidgetResizable(True)
        generic_scroll.setFrameShape(QScrollArea.NoFrame)
        generic_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        generic_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(generic_scroll, "dark")
        
        # 创建内容容器
        generic_content = QWidget()
        generic_layout = QVBoxLayout(generic_content)
        generic_layout.setContentsMargins(15, 15, 15, 15)
        
        generic_label = QLabel(i18n.get_text("page_not_implemented"))
        generic_label.setAlignment(Qt.AlignCenter)
        generic_layout.addWidget(generic_label)
        
        # 设置滚动区域的内容
        generic_scroll.setWidget(generic_content)
        
        # 将滚动区域添加到页面
        generic_page_layout = QVBoxLayout(generic_page)
        generic_page_layout.setContentsMargins(0, 0, 0, 0)
        generic_page_layout.addWidget(generic_scroll)
        
        # 存储容器引用，方便主窗口使用
        generic_page.content_widget = generic_content
        generic_page.content_layout = generic_layout
        
        return generic_page
    
    def create_history_page(self):
        """创建历史页面"""
        try:
            # 使用HistoryWindow类创建历史页面
            history_page = HistoryWindow()
            return history_page
        except Exception as e:
            # 如果创建失败，创建一个通用页面
            print(f"创建历史页面失败: {e}")
            generic_page = self.create_generic_page()
            generic_page.content_widget.layout().addWidget(QLabel(i18n.get_text("history_load_failed")))
            return generic_page
        
    def create_finished_page(self):
        """创建已完成页面（保留此方法以兼容现有代码）"""
        # 调用历史页面以保持一致性
        return self.create_history_page()
    
    def create_page(self, page_id, page_name):
        """创建页面"""
        page_widget = QWidget()
        
        # 创建滚动区域
        page_scroll = QScrollArea()
        page_scroll.setWidgetResizable(True)
        page_scroll.setFrameShape(QScrollArea.NoFrame)
        page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(page_scroll, "dark")
        
        # 创建内容容器
        page_content = QWidget()
        page_layout = QVBoxLayout(page_content)
        page_layout.setContentsMargins(15, 15, 15, 15)
        page_layout.setSpacing(20)
        
        # 设置滚动区域的内容
        page_scroll.setWidget(page_content)
        
        # 将滚动区域添加到页面
        page_layout = QVBoxLayout(page_widget)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(page_scroll)
        
        # 存储容器引用，方便主窗口使用
        page_widget.content_widget = page_content
        page_widget.content_layout = page_layout
        
        return page_widget
    
    def switch_page(self, page_id):
        """切换到指定页面"""
        if page_id not in self.pages:
            print(f"{i18n.get_text('error')}: {i18n.get_text('page_not_exists', page_id)}")
            return
            
        if page_id == self.current_page:
            # 已经在当前页面
            if page_id in self.buttons:
                self.buttons[page_id].setChecked(True)
            return
        
        # 动画状态处理 - 当有新的切换请求时打断当前动画
        if self.animation_manager.is_animating:
            # 强制停止当前所有动画
            self.animation_manager.stop_animations()
            # 重置动画状态
            self.animation_manager.is_animating = False
            
            # 如果当前有页面正在切换，需要完成最后的整理
            if hasattr(self, '_pending_switch') and self._pending_switch:
                old_id, _ = self._pending_switch
                if old_id in self.pages:
                    self.pages[old_id].hide()
        
        # 更新按钮状态
        for btn_id, btn in self.buttons.items():
            btn.setChecked(btn_id == page_id)
        
        # 获取页面实例
        next_page = self.pages[page_id]
        
        # 记录待处理的切换，用于动画打断时恢复
        self._pending_switch = (self.current_page, page_id)
        
        # 先隐藏所有页面，避免多个页面同时可见
        for p_id, page in self.pages.items():
            if p_id != page_id and p_id != self.current_page:
                page.hide()
        
        if self.current_page:
            current_page = self.pages[self.current_page]
            
            # 在开始任何动画前确保页面可见并准备就绪
            current_page.show()
            current_page.raise_()
            
            # 确保设置页面位置正确
            if "settings" in [page_id, self.current_page]:
                # 设置页面有特殊处理，确保父级宽高正确
                parent = self.stacked_widget
                if parent:
                    rect = parent.rect()
                    if page_id == "settings":
                        next_page.setFixedSize(rect.width(), rect.height())
                    if self.current_page == "settings":
                        current_page.setFixedSize(rect.width(), rect.height())
            
            # 获取页面索引以确定动画方向
            try:
                current_index = list(self.pages.keys()).index(self.current_page)
                next_index = list(self.pages.keys()).index(page_id)
                direction = "left" if current_index < next_index else "right"
            except ValueError:
                # 索引错误时默认从右侧切入
                direction = "left"
            
            # 创建页面切换动画
            animation = self.animation_manager.create_page_switch_animation(
                current_page=current_page,
                next_page=next_page,
                direction=direction
            )
            
            # 如果动画创建失败，确保页面立即切换
            if not animation:
                self.stacked_widget.setCurrentWidget(next_page)
                current_page.hide()
                next_page.show()
        else:
            # 第一次切换，直接显示
            self.stacked_widget.setCurrentWidget(next_page)
            next_page.show()
        
        # 更新当前页面
        self.current_page = page_id
        
        # 发送页面变更信号
        self.page_changed.emit(page_id)
    
    def get_current_page(self):
        """获取当前页面ID"""
        return self.current_page
    
    def get_page(self, page_id):
        """获取指定ID的页面实例"""
        return self.pages.get(page_id)
    
    def get_button(self, page_id):
        """获取指定ID的按钮实例"""
        return self.buttons.get(page_id)
    
    def remove_page(self, page_id):
        """移除页面"""
        if page_id not in self.pages:
            return
        
        page = self.pages[page_id]
        self.stacked_widget.removeWidget(page)
        del self.pages[page_id]
        
        # 如果有对应的按钮，也移除
        if page_id in self.buttons:
            button = self.buttons[page_id]
            sidebar_layout = self.sidebar_widget.layout()
            if sidebar_layout:
                for i in range(sidebar_layout.count()):
                    item = sidebar_layout.itemAt(i)
                    if item and item.widget() == button:
                        sidebar_layout.removeItem(item)
                        button.deleteLater()
                        break
            del self.buttons[page_id]
        
        # 如果移除的是当前页面，切换到第一个可用页面
        if page_id == self.current_page:
            if self.pages:
                self.switch_page(next(iter(self.pages.keys())))
            else:
                self.current_page = None 
    
    def create_download_page(self):
        """创建下载页面"""
        download_page = QWidget()
        
        # 创建滚动区域
        download_scroll = QScrollArea()
        download_scroll.setWidgetResizable(True)
        download_scroll.setFrameShape(QScrollArea.NoFrame)
        download_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        download_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        ScrollStyle.apply_to_widget(download_scroll, "dark")
        
        # 创建内容容器
        download_content = QWidget()
        download_page_layout = QVBoxLayout(download_content)
        download_page_layout.setContentsMargins(15, 15, 15, 15)
        download_page_layout.setSpacing(20)
        
        # 设置滚动区域的内容
        download_scroll.setWidget(download_content)
        
        # 将滚动区域添加到下载页面
        download_layout = QVBoxLayout(download_page)
        download_layout.setContentsMargins(0, 0, 0, 0)
        download_layout.addWidget(download_scroll)
        
        # 存储容器引用，方便主窗口使用
        download_page.content_widget = download_content
        download_page.content_layout = download_page_layout
        
        return download_page
    
    def add_page(self, page_id, page_widget, icon_code, text, position="top", order=0):
        """添加页面到管理器
        
        参数:
            page_id: 页面ID
            page_widget: 页面部件
            icon_code: 图标代码
            text: 按钮文本
            position: 按钮位置，可以是"top"或"bottom"
            order: 按钮顺序，数字越小越靠前
        """
        self.pages[page_id] = page_widget
        
        # 创建侧边栏按钮
        button = CategoryButton(
            parent=self.sidebar_widget,
            text=text,
            icon_code=icon_code
        )
        button.clicked.connect(lambda checked=False, pid=page_id: self.switch_page(pid))
        self.buttons[page_id] = button
        
        # 获取侧边栏布局并添加按钮
        sidebar_layout = self.sidebar_widget.layout()
        if sidebar_layout:
            if position == "top":
                # 获取品牌容器的位置
                brand_index = -1
                for i in range(sidebar_layout.count()):
                    item = sidebar_layout.itemAt(i)
                    if item and item.widget() and item.widget().objectName() == "brand_container":
                        brand_index = i
                        break
                    
                # 根据顺序直接插入到指定位置，确保位置安全
                insert_pos = brand_index + 1 + order
                total_items = sidebar_layout.count()
                
                # 确保插入位置不超出布局范围
                if insert_pos < total_items:
                    try:
                        sidebar_layout.insertWidget(insert_pos, button)
                    except Exception as e:
                        import logging
                        logging.error(f"{i18n.get_text('button_insert_failed')}: {e}, {i18n.get_text('position')}: {insert_pos}, {i18n.get_text('max_index')}: {total_items-1}")
                        # 出错时使用安全的方式添加
                        sidebar_layout.addWidget(button)
                else:
                    # 如果位置超出范围，直接添加到末尾
                    sidebar_layout.addWidget(button)
                
            elif position == "bottom":
                # 添加到底部区域，在弹性空间之后
                stretch_index = -1
                
                # 查找最后一个拉伸项的位置
                for i in range(sidebar_layout.count()):
                    item = sidebar_layout.itemAt(i)
                    if item and item.spacerItem():
                        stretch_index = i
                
                total_items = sidebar_layout.count()
                
                if stretch_index >= 0:
                    # 在拉伸项之后插入，确保位置安全
                    insert_pos = min(stretch_index + 1 + order, total_items)
                    try:
                        sidebar_layout.insertWidget(insert_pos, button)
                    except Exception as e:
                        import logging
                        logging.error(f"{i18n.get_text('bottom_button_insert_failed')}: {e}, {i18n.get_text('position')}: {insert_pos}, {i18n.get_text('max_index')}: {total_items-1}")
                        # 出错时直接添加到末尾
                        sidebar_layout.addWidget(button)
                else:
                    # 如果没有找到拉伸项，添加到布局末尾
                    sidebar_layout.addWidget(button)
        
        # 将页面添加到堆叠窗口
        self.stacked_widget.addWidget(page_widget) 