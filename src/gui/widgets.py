"""
M.B.S Studio - Custom Widgets
==============================

Reusable custom Qt widgets for the M.B.S Studio application.

Widgets:
    - SmoothScrollArea: Enhanced scroll area with smooth scrolling
    - ChatBubbleDelegate: Custom delegate for chat bubble rendering

Author: M.B.S Studio
Version: 1.0.0
"""

from __future__ import annotations

from typing import Callable, Dict, Optional

from PyQt6.QtCore import QEvent, QRect, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QTextDocument,
    QTextOption,
    QWheelEvent,
)
from PyQt6.QtWidgets import (
    QFrame,
    QScrollArea,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QWidget,
)


def _text_is_rtl(text: str) -> bool:
    """
    Detect if text contains Hebrew characters (RTL).
    
    Args:
        text: Text string to analyze
        
    Returns:
        True if text contains Hebrew characters, False otherwise
    """
    return any("\u0590" <= char <= "\u05FF" for char in (text or ""))


class SmoothScrollArea(QScrollArea):
    """
    Enhanced scroll area with normalized wheel/trackpad scrolling.
    
    Provides consistent smooth scrolling behavior across different
    input devices and platforms. Automatically propagates scroll
    events to nested widgets.
    
    Args:
        scroll_multiplier: Multiplier for scroll speed (default: 0.5)
    
    Example:
        >>> scroll_area = SmoothScrollArea(scroll_multiplier=0.5)
        >>> scroll_area.setWidget(content_widget)
    """

    def __init__(
        self,
        *args,
        scroll_multiplier: float = 0.5,
        **kwargs,
    ) -> None:
        """
        Initialize the smooth scroll area.
        
        Args:
            scroll_multiplier: Speed multiplier for scroll events
            *args: Additional positional arguments for QScrollArea
            **kwargs: Additional keyword arguments for QScrollArea
        """
        super().__init__(*args, **kwargs)
        self._scroll_multiplier = scroll_multiplier
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def setWidget(self, widget: QWidget) -> None:
        """
        Set the scrollable widget and register scroll targets.
        
        Args:
            widget: Widget to display in the scroll area
        """
        super().setWidget(widget)
        self._register_scroll_targets(widget)

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Handle wheel events with smooth scrolling.
        
        Normalizes scroll delta from different input devices
        and applies the scroll multiplier for consistent behavior.
        
        Args:
            event: Wheel event to process
        """
        delta = self._extract_delta(event)
        if delta:
            step = int(delta * self._scroll_multiplier)
            if step == 0:
                step = 1 if delta > 0 else -1
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() - step)
            event.accept()
        else:
            super().wheelEvent(event)

    def eventFilter(self, obj, event) -> bool:
        """
        Filter events from child widgets to handle scrolling.
        
        Intercepts wheel events from nested widgets and redirects
        them to the scroll area for consistent behavior.
        
        Args:
            obj: Object that generated the event
            event: Event to filter
            
        Returns:
            True if event was handled, False otherwise
        """
        if event.type() == QEvent.Type.Wheel:
            # Check if we actually have a scroll delta to handle
            if self._extract_delta(event):
                self.wheelEvent(event)
                return True
        return super().eventFilter(obj, event)

    def _register_scroll_targets(self, widget: QWidget) -> None:
        """
        Install event filter on widget and all children.
        
        Args:
            widget: Parent widget to register
        """
        widget.installEventFilter(self)
        for child in widget.findChildren(QWidget):
            child.installEventFilter(self)

    def _extract_delta(self, event: QWheelEvent) -> float:
        """
        Extract normalized scroll delta from wheel event.
        
        Handles both pixel-based (trackpad) and angle-based (mouse wheel)
        scroll events.
        
        Args:
            event: Wheel event to extract delta from
            
        Returns:
            Normalized scroll delta value
        """
        pixel = event.pixelDelta()
        if pixel.y():
            return pixel.y()
        angle = event.angleDelta()
        if angle.y():
            return angle.y() / 8  # Convert to degrees
        return 0.0


class ChatBubbleDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering chat messages as bubbles.
    
    Renders chat items with proper text wrapping, RTL support,
    and distinct styling for user vs assistant messages.
    
    Args:
        parent: Parent widget (optional)
        config_provider: Callable returning theme configuration dict
    
    Example:
        >>> delegate = ChatBubbleDelegate(
        ...     parent=list_widget,
        ...     config_provider=lambda: {"user_bubble": "#1d4ed8", ...}
        ... )
        >>> list_widget.setItemDelegate(delegate)
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        config_provider: Optional[Callable[[], Dict[str, object]]] = None,
    ) -> None:
        """
        Initialize the chat bubble delegate.
        
        Args:
            parent: Parent widget for the delegate
            config_provider: Function returning theme configuration
        """
        super().__init__(parent)
        self._doc = QTextDocument()
        self._doc.setDocumentMargin(0)
        self._config_provider = config_provider
        self._custom_font: Optional[QFont] = None

    def setFont(self, font: QFont) -> None:
        """Set the font for chat bubbles."""
        self._custom_font = font

    def _get_font(self, option: QStyleOptionViewItem) -> QFont:
        """Get the font to use, preferring custom font if set."""
        if self._custom_font:
            return self._custom_font
        return option.font

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index,
    ) -> None:
        """
        Paint a chat bubble for the given item.
        
        Renders the message text inside a rounded rectangle with
        appropriate colors based on message alignment (user vs assistant).
        
        Args:
            painter: QPainter to use for drawing
            option: Style options for the item
            index: Model index of the item to paint
        """
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not text:
            super().paint(painter, option, index)
            return

        available_width = option.rect.width()
        if available_width <= 0 and option.widget:
            available_width = option.widget.width()
        available_width = max(220, available_width - 40)
        
        self._doc.setDefaultFont(self._get_font(option))
        self._doc.setDefaultTextOption(QTextOption(Qt.AlignmentFlag.AlignLeft))
        self._doc.setTextWidth(available_width)
        self._doc.setPlainText(text)
        doc_size = self._doc.size().toSize()
        bubble_width = min(doc_size.width() + 28, option.rect.width() - 16)
        bubble_height = doc_size.height() + 24

        bubble_rect = QRect(
            option.rect.left() + 8,
            option.rect.top() + 4,
            bubble_width,
            bubble_height,
        )
        alignment = index.data(Qt.ItemDataRole.TextAlignmentRole) or Qt.AlignmentFlag.AlignLeft
        config = self._config_provider() if self._config_provider else {}
        
        if alignment & Qt.AlignmentFlag.AlignRight:
            bubble_rect.moveRight(option.rect.right() - 8)
            # User messages: teal/cyan color
            bg_color = QColor(config.get("user_bubble", "#0f766e"))
            text_color = QColor(config.get("user_text", "#f8fafc"))
        else:
            # AI (M.B.S) messages: purple/violet color
            bg_color = QColor(config.get("assistant_bubble", "#4c1d95"))
            text_color = QColor(config.get("assistant_text", "#e2e8f0"))

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(bubble_rect, 12, 12)
        painter.setPen(text_color)

        text_rect = bubble_rect.adjusted(12, 8, -12, -8)
        painter.translate(text_rect.topLeft())
        self._doc.drawContents(
            painter,
            QRectF(0, 0, text_rect.width(), text_rect.height()),
        )
        painter.restore()

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index,
    ) -> QSize:
        """
        Calculate the size hint for a chat bubble item.
        
        Determines the required height based on text content
        and available width for proper layout.
        
        Args:
            option: Style options for the item
            index: Model index of the item
            
        Returns:
            QSize with calculated dimensions
        """
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if not text:
            return super().sizeHint(option, index)
        
        width = option.rect.width()
        if width <= 0 and option.widget:
            width = option.widget.width()
        width = max(220, width - 40)
        
        self._doc.setDefaultFont(self._get_font(option))
        self._doc.setTextWidth(width)
        self._doc.setPlainText(text)
        doc_size = self._doc.size().toSize()
        height = doc_size.height() + 28
        parent_width = option.rect.width() or (
            option.widget.width() if option.widget else width + 40
        )
        return QSize(parent_width, height)

