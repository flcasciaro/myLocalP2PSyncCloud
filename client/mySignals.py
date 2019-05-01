"""Custom signals of myLocalP2PSyncCLoud"""

"""@author: Francesco Lorenzo Casciaro - Politecnico di Torino - UPC"""


from PyQt5.QtCore import QObject, pyqtSignal

class mySig(QObject):

    refresh = pyqtSignal(str)

    def __init__(self):
        QObject.__init__(self)

    def refreshEmit(self, message):
        self.refresh.emit(message)

