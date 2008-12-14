
''' Pluggable sidebar widget that shows the structure of the source 
file currently being edited '''

import functools
import random
import time
import threading
import sys

import kate
from kate import Kate # Kate library API

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyKDE4.kdeui import KIcon
from PyKDE4.ktexteditor import KTextEditor # KTE namespace

# time between updates in milliseconds
updateInterval = 5000




mimeTypeToAnalyser = {}
def register(*mimeTypes):
    ''' Register a source analyser for a the given
    mimetype(s). Periodically the function will be called in a
    separate thread and fed a string containing the contents of a file
    of registered mime. The function must return a list of 
    StructureItem subclasses as appropriate to describe the file's
    structure. See source_python.py for an example.
    
    Behaviour is undefined if more than one plugin registers
    for the same mimetype '''
    def inner(func):
        for mimeType in mimeTypes:
            mimeTypeToAnalyser[mimeType] = func
        return func
    return inner


@kate._attribute(cache={})
def gradientImageWithLine(fromColor, toColor, penColor=210):
    if (fromColor, toColor, penColor) not in gradientImageWithLine.cache:
        brush = verticalGradient(fromColor, toColor)
        # and draw a thin line
        i = QImage(1, SourceList.ItemHeight, QImage.Format_RGB32)
        p = QPainter(i)
        p.fillRect(i.rect(), brush)
        p.setPen(QPen(QColor(penColor, penColor, penColor)))
        p.drawLine(0, SourceList.ItemHeight - 1, 1, SourceList.ItemHeight - 1)
        p.end()
        gradientImageWithLine.cache[fromColor, toColor, penColor] = i
    return gradientImageWithLine.cache[fromColor, toColor, penColor]


class StructureItem(QListWidgetItem):
    ''' Represents something in a source document -- a global variable,
    a function, etc. Each of these has a line (on which their definition
    begins), a name, and a brush to fill the background with, but may
    have more information such as parameters. '''
    def __init__(self, line, name, backgroundImage):
        QListWidgetItem.__init__(self)
        self.line = line
        self.setText(name)
        self.backgroundImage = backgroundImage
        # brush.
        self.name = name.strip()
        self.setSizeHint(QSize(1000, SourceList.ItemHeight))
    
    def beforeAddedToListWidget(self):
        # called before this is put on a listwidget
        if not hasattr(self.__class__, 'BackgroundBrush'):
            self.__class__.BackgroundBrush = QBrush(self.backgroundImage)
        self.setBackground(self.__class__.BackgroundBrush)


class GlobalVariable(StructureItem):
    def __init__(self, line, name):
        gradientBrush = verticalGradient('#ede0b2', '#f3eacd')
        StructureItem.__init__(self, line, name, self._bg(gradientBrush))

class Function(StructureItem):
    ''' A function or procedure. It is up to you what you give as the
    name (i.e. you may choose to include parameters or return types
    in it depending on your language) '''
    brush = None
    def __init__(self, line, name):
        StructureItem.__init__(self, line, name, gradientImageWithLine('#dbedaa', '#e7f3c7'))

class Class(StructureItem):
    def __init__(self, line, name):
        StructureItem.__init__(self, line, name, gradientImageWithLine('#c4dbf1', '#c8dff6', 190))

class Method(StructureItem):
    ''' A method is a function member of a class. '''
    def __init__(self, line, name):
        ''' Pass the usual line and name as well as a reference
        to the class that it is a method of '''
        StructureItem.__init__(self, line, '    %s' % name, gradientImageWithLine('#d3ebf9', '#e3f0f7'))

class Property(StructureItem):
    ''' Properties are things on a class that always have a method
    for getting a value, most of the time a method for setting this
    value, and sometimes a method for deleting or clearing the value.
    They are used as syntactic sugar in some programming languages or
    as additional meta information. '''
    def __init__(self, line, name, getter=None, setter=None, deleter=None):
        # we override the widget for this list item
        # because we need ultimo power in our custom display,
        # so do nothing but store data now.
        StructureItem.__init__(self, line, '    %s' % name, gradientImageWithLine('#d3ebf9', '#e3f0f7'))
        self.getter = getter
        self.setter = setter
        self.deleter = deleter


# class FadeWidget(QWidget):
    # def __init__(self, endColor, parent=None):
        # QWidget.__init__(self, parent)
        # self.endColor = endColor
        # self.gradient = None
        
    # def resizeEvent(self, e):
        # self.gradient = QLinearGradient(QPointF(0, 0), QPointF(self.width(), 0))
        # self.gradient.setColorAt(0, QColor(Qt.transparent))
        # self.gradient.setColorAt(1, QColor(self.endColor))
    
    # def paintEvent(self, e):
        # if self.gradient is not None:
            # QPainter(self).fillRect(self.rect(), QBrush(self.gradient))


class SourceList(QListWidget):
    ItemHeight = 0
    def __init__(self, parent):
        QListWidget.__init__(self, parent)
        self._structure = []
        # disable eliding of the items so that we can add our fade
        self.setTextElideMode(Qt.ElideNone)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # stupid hack for a PyQt4 bug:
        # QGradiant doesn't seem to have setCoordinateMode member.
        self.addItem('Blah')
        SourceList.ItemHeight = self.sizeHintForRow(0) + 2
        self.clear()
        #
        # self.fade = FadeWidget(Qt.white, self)
        # self.fade.resize(20, 100)
        #
        self.setStyleSheet('QListView { show-decoration-selected: 1; } QListView::item:selected { color: white; background: #999 }')
        self.connect(self, SIGNAL('activated(const QModelIndex &)'), self.itemActivated)
    
    # def resizeEvent(self, e):
        # # move the fading-out bit to the right
        # viewport = self.viewport()
        # w = viewport.width()
        # h = viewport.height()
        # fadeWidth = 20
        # self.fade.setFixedSize(QSize(fadeWidth, h))
        # self.fade.move(w - fadeWidth + self.frameWidth(), self.frameWidth())
    
    def itemActivated(self, index):
        line = self.item(index.row()).line
        self.clearSelection()
        self.emit(SIGNAL('itemOnLineSelected(int)'), line)
    
    def setStructure(self, structure):
        ''' Set the source list structure. You do not need to call this or touch
        this class at all if you're merely writing a plugin for a language.
        The format of "structure" is a list of StructureItem subclasses '''
        self.clear()
        self._structure = structure[:]
        for i, item in enumerate(structure):
            item.beforeAddedToListWidget()
            self.addItem(item)


class AnalyseEvent(QEvent):
    Type = QEvent.User + 111
    def __init__(self, mimeType, source):
        QEvent.__init__(self, QEvent.Type(self.Type))
        self.mimeType = mimeType
        self.source = source


class AnalyserThread(QThread):
    ''' Asynchronously analyses a bit of source code and produce
    a structure from it. To start analysing a bit of source,
    pass its mime type and the code to the 'analyse' function.
    When it has finished analysing, the thread will emit an
    'analysed' signal, passing the structure (as a list of 
    StructureItem subclasses).
    To see whether source analysis is underway, check the value
    of the analysing attribute '''
    def __init__(self):
        QThread.__init__(self)
        self.analysing = False
    
    def analyse(self, mimeType, source):
        ''' Start analysing the source to produce the structure.
        When it has been parsed, an 'analysed' signal is emitted.
        The thread must have started running before this function is
        called.
        n.b. this function is fully thread-safe '''
        self.analysing = True
        event = AnalyseEvent(mimeType, source)
        QCoreApplication.postEvent(self.o, event)
    
    def run(self):
        self.o = QObject()
        self.o.customEvent = self.customEventInThread
        self.exec_()
        # self.structure = mimeTypeToAnalyser[self.mimeType](self.source)
        # self.finished = True
    
    def customEventInThread(self, e):
        print QThread.currentThreadId()
        if e.type() != AnalyseEvent.Type:
            return
        structure = mimeTypeToAnalyser[e.mimeType](e.source)
        self.analysing = False
        self.emit(SIGNAL('analysed'), structure)


class SourceStructureWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.sourceList = SourceList(self)
        self.connect(self.sourceList, SIGNAL('itemOnLineSelected(int)'), self.goToLine)
        layout = QVBoxLayout(self)
        layout.setMargin(0)
        layout.addWidget(self.sourceList)
        self.analyser = AnalyserThread()
        self.connect(self.analyser, SIGNAL('started()'), self.startAnalysing, Qt.QueuedConnection)
        self.connect(self.analyser, SIGNAL('analysed'), self.setStructure, Qt.QueuedConnection)
        self.analyser.start()
    
    def startAnalysing(self):
        while not hasattr(self.analyser, 'o'):
            time.sleep(0.1)
        self.analyseTimer = self.startTimer(updateInterval)
        self.timerEvent()
    
    def timerEvent(self, e=None):
        # print 'timer'
        if e is not None and e.timerId() != self.analyseTimer:
            return
        if self.analyser.analysing:
            return
        document = kate.activeDocument()
        mimeType = str(document.mimeType())
        source = unicode(document.text())
        self.analyser.analyse(mimeType, source)
        
        # # if there are any running threads, forget it
        # if self.analysisThread is not None:
            # if self.analysisThread.finished:
                # print 'set structure'
                # self.setStructure(self.analysisThread.structure)
            # else:
                # print 'not finished'
                # return
        # document = kate.activeDocument()
        # mimeType = str(document.mimeType())
        # source = unicode(document.text())
        # if mimeType in mimeTypeToAnalyser:
            # self.analysisThread = AnalyserThread(mimeType, source)
            # print 'started analyser'
            # self.analysisThread.start()
        # else:
            # print 'set structure empty'
            # self.setStructure([])
    
    def setStructure(self, structure):
        if structure is None:
            pass
        else:
            self.sourceList.setStructure(structure)
    
    def goToLine(self, line):
        view = kate.activeView()
        cursor = view.cursorPosition()
        lineLength = len(unicode(view.document().line(line)))
        view.setCursorPosition(KTextEditor.Cursor(line, lineLength))
        kate.centralWidget().setFocus(Qt.OtherFocusReason)
        # self.sourceList.clearSelection()
        # self.sourceList.clearFocus()


# the singleton instance of the structure widget that's used. This is
# added to the Kate sidebar on init.
sidebar = SourceStructureWidget()

@kate.init
def attachSourceSidebar():
    ''' Create the side bar (or "tool view" in Kate-speak) and attach it
    to the Kate window '''
    w = kate.mainInterfaceWindow()
    # createToolView parameters:
    # * an arbitrary ID
    # * initial position on the window
    # * icon
    # * label
    icon = KIcon('applications-development').pixmap(16)
    tool = w.createToolView('source_view', Kate.MainWindow.Left, icon, '  Source  ')
    sidebar.setParent(tool)
    # show it too. It sucks that the tool view loads a little after the application,
    # so that your preference on its visibility isn't remembered. Disable the plugin
    # if you don't like it :(
    w.showToolView(tool)
    
    # Human = Class(30, 'Human')
    # sidebar.setStructure([
        # GlobalVariable(3, '__name__'),
        # GlobalVariable(4, '__author__'),
        # Function(6, 'print(string, end=\'\\n\')'),
        # Function(10, 'exit()'),
        # Human,
        # Method(31, '__init__(self)'),
        # Method(35, '__del__(self)'),
        # Method(38, 'setName(self, name)'),
        # Method(45, 'sayMyName(self)'),
    # ])


@kate.viewChanged
def viewChanged():
    print 'view changed'


def verticalGradient(top, bottom):
    g = QLinearGradient(0, 0, 0, SourceList.ItemHeight)
    # g.setCoordinateMode(QGradient.StretchToDeviceMode)
    g.setColorAt(0, QColor(top))
    g.setColorAt(1, QColor(bottom))
    return QBrush(g)

