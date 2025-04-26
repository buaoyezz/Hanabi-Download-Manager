# coding: utf-8
from PySide6.QtCore import QObject, Signal


class SignalManager(QObject):
    addTaskSignal = Signal(str, str, str, dict, str, int, bool, str)
    allTaskFinished = Signal()
    appErrorSig = Signal(str)

SignalManager = SignalManager()
