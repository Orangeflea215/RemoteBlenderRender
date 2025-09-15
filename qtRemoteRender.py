#For dealing with local file paths
#from os.path import expanduser
import os, os.path

#for remote file operations
import paramiko
from paramiko.client import *
from paramiko.sftp_client import *

#for remote file information
import stat

#for running command line
import subprocess

#for UI
from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6 import QtWidgets
from PySide6.QtWidgets import QFrame
from PySide6 import QtGui

#for viewing images
from imageviewer import ImageViewer

#home_directory = expanduser('~')

def openFileBrowser(parent):
    fileDialog = QtWidgets.QFileDialog(parent)
    fileDialog.setWindowTitle("Choose Blend File")
    fileDialog.setFileMode(QtWidgets.QFileDialog.FileMode.ExistingFile)
    fileDialog.setViewMode(QtWidgets.QFileDialog.ViewMode.Detail)
    fileDialog.setNameFilter(("Blend files (*.blend *.blend1)"))
    
    if fileDialog.exec():
        selectedFile = fileDialog.selectedFiles()
        print("Selected File:", selectedFile[0])
        parent.blendFilePath = selectedFile[0]
        parent.fileNameLabel.setText(selectedFile[0])
        
def makeRefsLocal(remoteConnApp):
    filePath = remoteConnApp.blendFilePath
    print(filePath)
    currentDirectory = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(["blender", "-b", filePath, "--python", currentDirectory + "\\makeObjectsLocalAndPack.py"])
        
def remoteIPPrompt(parent):
    #present a modal with username and password options
    def cancelIPPrompt(promptDialog):
        promptDialog.reject()
    
    def confirmRemoteCredentials(promptDialog):
        promptDialog.done(QtWidgets.QDialog.DialogCode.Accepted)
        
        
    def attemptRemoteConnection(mainWindow, username, password):
        print("connecting...")
        print("Username: " + username)
        print("Password: " + password)
        print("Remote IP: " + mainWindow.remoteConnectionIP)
        client = SSHClient()
        mainWindow.ssh_client = client
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(hostname=mainWindow.remoteConnectionIP, username=username, password=password)
            mainWindow.sftp_client = client.open_sftp()
            mainWindow.sftp_client.chdir(mainWindow.sftp_remote_folder_path[0])
            mainWindow.treeViewWidget.setHeaderLabels(['Name'])
            #mainWindow.remoteDirectoryDisplay.setText("/".join(mainWindow.sftp_remote_folder_path))
            mainWindow.treeViewWidget.setHeaderLabels(["/".join(mainWindow.sftp_remote_folder_path)])
            mainWindow.remoteDirectoryDisplay.setEnabled(True)
            remoteList = mainWindow.sftp_client.listdir_attr()
            treeItems = []
            for fileAttr in remoteList:
                item = QtWidgets.QTreeWidgetItem([fileAttr.filename])
                treeItems.append(item)
                if(stat.S_ISDIR(fileAttr.st_mode)):
                    item.setIcon(0, QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.FolderOpen))
                else:
                    item.setIcon(0, QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentOpen))
                
            mainWindow.treeViewWidget.insertTopLevelItems(0, treeItems)
            mainWindow.treeViewWidget.itemClicked.connect(mainWindow.treeFolderClicked)
            mainWindow.treeViewWidget.itemDoubleClicked.connect(mainWindow.treeFolderDoubleClicked)
            mainWindow.remoteMachineConnected = True
            mainWindow.updateButtons()
        except Exception as e:
            print(f"Error during SFTP upload: {e}")
        
    promptDialog = QtWidgets.QDialog(parent)
    promptDialog.setWindowTitle("Enter Remote Credentials")
    
    promptLayout = QtWidgets.QVBoxLayout()
    
    remoteIPUsername = QtWidgets.QLineEdit()
    remoteIPUsername.setPlaceholderText("username")

    remoteIPUsernameLabel = QtWidgets.QLabel("Remote Username:")
    remoteIPUsernameLabel.setBuddy(remoteIPUsername)
    
    remoteIPPassword = QtWidgets.QLineEdit()
    remoteIPPassword.setPlaceholderText("Password")

    remoteIPPasswordLabel = QtWidgets.QLabel("Remote Password:")
    remoteIPPasswordLabel.setBuddy(remoteIPPassword)
    
    promptLayout.addWidget(remoteIPUsernameLabel)
    promptLayout.addWidget(remoteIPUsername)
    promptLayout.addWidget(remoteIPPasswordLabel)
    promptLayout.addWidget(remoteIPPassword)
    
    
    buttonLayout = QtWidgets.QHBoxLayout()
    
    cancelButton = QtWidgets.QPushButton('Cancel')
    cancelButton.clicked.connect(lambda: cancelIPPrompt(promptDialog))
    
    connectButton = QtWidgets.QPushButton('Connect')
    connectButton.clicked.connect(lambda: confirmRemoteCredentials(promptDialog))
    
    buttonLayout.addWidget(cancelButton)
    buttonLayout.addWidget(connectButton)
    
    promptLayout.addLayout(buttonLayout)
    
    promptDialog.setLayout(promptLayout)
    
    promptDialog.accepted.connect(lambda: attemptRemoteConnection(parent, remoteIPUsername.text(), remoteIPPassword.text()))
    
    promptDialog.open()
    
class fileUploader(QObject):
    finished = Signal()
    progress = Signal(int, int)

    def __init__(self, sftp_client, fileToTransfer, remoteFilePath, mainApp):
        super(fileUploader, self).__init__()
        self.sftp_client = sftp_client
        self.fileToTransfer = fileToTransfer
        self.remoteFilePath = remoteFilePath
        self.mainApp = mainApp
    
    def updateProgress(self, bytesTransferred, totalBytes):
        self.progress.emit(bytesTransferred, totalBytes)

    def run(self):
        """Long-running task."""
        try:
            self.sftp_client.put(self.fileToTransfer, self.remoteFilePath, self.updateProgress)
        except Exception as e:
            print(e)
        self.mainApp.fileTransferred = True
        self.mainApp.updateButtons()
        self.finished.emit()
        # for i in range(5):
            # sleep(1)
            # self.progress.emit(i + 1)
        # self.finished.emit()
    
class RemoteConnectionApplication(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(RemoteConnectionApplication, self).__init__(parent)
        
        #set Application Variables
        self.remoteConnectionIP = ""
        self.remoteConnectionUsername = ""
        self.remoteConnectionPassword = ""
        self.blendFilePath = ""
        
        self.ssh_client = None
        self.sftp_client = None
        self.sftp_remote_folder_path = ["/C:"]
        self.selected_remote_folder = ""
        self.fileTransferred = False
        self.remoteMachineConnected = False
        self.renderComplete = False
        
        self.fileTransferThread = None
        self.fileTransferrer = None
        self.fileTransferWorker = None
        self.progressDialog = None
        self.imageViewer = None
        
        self.frameToRender = 1
        self.outputFileName = "rendered_"
        self.cyclesDevice = "OPTIX"
        
        self.setWindowTitle("Remote Render")
        self.setFixedSize(640, 480)
        self.mainLayout = QtWidgets.QGridLayout()
        
        self.blendFilePreparer = QtWidgets.QHBoxLayout()
        
        self.blendFilePreparerButtonContainer = QtWidgets.QVBoxLayout()
       
        fileChooserButton = QtWidgets.QPushButton('Choose blend file')
        fileChooserButton.clicked.connect(lambda: openFileBrowser(self))
        self.blendFilePreparerButtonContainer.addWidget(fileChooserButton)
        
        fileLocalMakerButton = QtWidgets.QPushButton('Make all blend file references local and pack data')
        fileLocalMakerButton.clicked.connect(lambda: makeRefsLocal(self))
        self.blendFilePreparerButtonContainer.addWidget(fileLocalMakerButton)
        
        self.blendFilePreparer.addLayout(self.blendFilePreparerButtonContainer)
        
        self.fileNameLabel = QtWidgets.QLabel('No file chosen.')
        self.blendFilePreparer.addWidget(self.fileNameLabel)
        
        self.mainLayout.addLayout(self.blendFilePreparer, 0, 0)

        self.remoteIPLayout = QtWidgets.QHBoxLayout()

        self.remoteIPText = QtWidgets.QLineEdit()
        self.remoteIPText.setPlaceholderText("xxx.xxx.xxx.xxx")
        self.remoteIPText.setMaximumWidth = 100
        self.remoteIPText.textEdited.connect(lambda text: self.updateRemoteIP(text))

        remoteIPLabel = QtWidgets.QLabel("Rendering Machine IP Address:")
        remoteIPLabel.setBuddy(self.remoteIPText)

        remoteConnectButton = QtWidgets.QPushButton('Connect')
        remoteConnectButton.clicked.connect(lambda: remoteIPPrompt(self))

        self.remoteIPLayout.addWidget(remoteIPLabel)
        self.remoteIPLayout.addWidget(self.remoteIPText)
        self.remoteIPLayout.addWidget(remoteConnectButton)

        self.mainLayout.addLayout(self.remoteIPLayout, 1, 0)
        
        self.treeViewWidget = QtWidgets.QTreeWidget()
        self.treeViewWidget.setColumnCount(1)
        self.treeViewWidget.setHeaderLabels(['Not Connected.'])
        
        
        remoteDirectoryControls = QtWidgets.QHBoxLayout()
        
        remoteDirectoryLabel = QtWidgets.QLabel("Choose Remote Directory for copy:")
        remoteDirectoryLabel.setBuddy(self.treeViewWidget)
        
        self.remoteDirectoryRefresh = QtWidgets.QPushButton('Refresh Listing')
        self.remoteDirectoryRefresh.setDisabled(True)
        self.remoteDirectoryRefresh.clicked.connect(self.updateDirectoryListing)
        
        remoteDirectoryControls.addWidget(remoteDirectoryLabel)
        remoteDirectoryControls.addWidget(self.remoteDirectoryRefresh)
        
        #self.remoteDirectoryDisplay = QtWidgets.QLineEdit("".join(self.sftp_remote_folder_path))
        self.remoteDirectoryDisplay = QtWidgets.QLineEdit("Not connected.")
        self.remoteDirectoryDisplay.setReadOnly(True)
        self.remoteDirectoryDisplay.setEnabled(False)

        self.mainLayout.addLayout(remoteDirectoryControls, 2, 0)
        #self.mainLayout.addWidget(self.remoteDirectoryDisplay)
        self.mainLayout.addWidget(self.treeViewWidget)
        
        self.copyFileButton = QtWidgets.QPushButton('Copy to Remote Machine')
        self.copyFileButton.setDisabled(True)
        self.copyFileButton.clicked.connect(self.copySelectedFile)
        self.copyFileButton.setMaximumWidth(150)
        
        self.mainLayout.addWidget(self.copyFileButton, 4, 0, Qt.AlignmentFlag.AlignRight)

        renderOptionsHeader = QtWidgets.QLabel('Render Options:')
        self.mainLayout.addWidget(renderOptionsHeader)
        
        renderOptionsFrame = QFrame()
        renderOptionsFrame.setFrameShape(QFrame.Shape.Box)
        renderOptionsFrame.setLineWidth(1)
        
        renderOptions = QtWidgets.QHBoxLayout(renderOptionsFrame)
        
        frameSelectorLayout = QtWidgets.QVBoxLayout()
        frameSelectorLabel = QtWidgets.QLabel("Rendered Frame:")
        frameSelectorInput = QtWidgets.QLineEdit()
        frameSelectorInput.setMaximumWidth(100)
        frameSelectorInput.setPlaceholderText("1")
        frameSelectorInput.textEdited.connect(lambda text: self.updateFrameToRender(text))
        
        frameSelectorLayout.addWidget(frameSelectorLabel)
        frameSelectorLayout.addWidget(frameSelectorInput)
        
        outputFilenameLayout = QtWidgets.QVBoxLayout()
        outputFilenameLabel = QtWidgets.QLabel("Output Filename:")
        outputFilenameInput = QtWidgets.QLineEdit()
        outputFilenameInput.setPlaceholderText('rendered_')
        outputFilenameInput.textEdited.connect(lambda text: self.updateOutputFilname(text))
        
        outputFilenameLayout.addWidget(outputFilenameLabel)
        outputFilenameLayout.addWidget(outputFilenameInput)
        
        cyclesRenderDeviceLayout = QtWidgets.QVBoxLayout()
        cyclesRenderDeviceLabel = QtWidgets.QLabel("Cycles Render Device:")
        cyclesRenderDeviceInput = QtWidgets.QComboBox()
        cyclesRenderDeviceInput.addItems(["CPU", "CUDA", "OPTIX", "HIP", "ONEAPI", "METAL"])
        cyclesRenderDeviceInput.setPlaceholderText("CPU")
        cyclesRenderDeviceInput.currentTextChanged.connect(lambda text: self.updateCyclesDevice(text))
        
        cyclesRenderDeviceLayout.addWidget(cyclesRenderDeviceLabel)
        cyclesRenderDeviceLayout.addWidget(cyclesRenderDeviceInput)
        
        renderOptions.addLayout(frameSelectorLayout)
        renderOptions.addLayout(outputFilenameLayout)
        renderOptions.addLayout(cyclesRenderDeviceLayout)
        
        self.mainLayout.addWidget(renderOptionsFrame)
        
        self.renderButton = QtWidgets.QPushButton('Render Remotely')
        self.renderButton.setDisabled(True)
        self.renderButton.clicked.connect(self.renderRemotely)
        self.renderButton.setMaximumWidth(200)
        
        self.viewRenderButton = QtWidgets.QPushButton('View Render')
        self.viewRenderButton.setDisabled(True)
        self.viewRenderButton.clicked.connect(self.viewRemoteRender)
        self.viewRenderButton.setMaximumWidth(200)
        
        renderButtonContainer = QtWidgets.QHBoxLayout()
        renderButtonContainer.addWidget(self.renderButton)
        renderButtonContainer.addWidget(self.viewRenderButton)
        
        self.mainLayout.addLayout(renderButtonContainer, 7, 0, Qt.AlignmentFlag.AlignRight)

        self.setLayout(self.mainLayout)
        
    def updateRemoteIP(self, IPAddress):
        self.remoteConnectionIP = IPAddress
        #print(self.remoteConnectionIP)
        
    def updateFrameToRender(self, frameNumber):
        self.frameToRender = frameNumber
        
    def updateOutputFilname(self, outputFilename):
        self.outputFileName = outputFilename
        
    def updateCyclesDevice(self, newDevice):
        self.cyclesDevice = newDevice
        
    def treeFolderClicked(self, item, col):
        #print(item.text(col))
        self.selected_remote_folder = item.text(col)
        self.treeViewWidget.setHeaderLabels(["/".join(self.sftp_remote_folder_path) + "/" + self.selected_remote_folder])
        
    def updateDirectoryListing(self):
        remoteList = self.sftp_client.listdir_attr()
        
        self.treeViewWidget.clear()
        treeItems = []
        #print(self.sftp_client.getcwd())
        if(self.sftp_client.getcwd()[:-1] != self.sftp_remote_folder_path[0]):
            treeItems.append(QtWidgets.QTreeWidgetItem([".."]))
        for fileAttr in remoteList:
            item = QtWidgets.QTreeWidgetItem([fileAttr.filename])
            treeItems.append(item)
            if(stat.S_ISDIR(fileAttr.st_mode)):
                item.setIcon(0, QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.FolderOpen))
            else:
                item.setIcon(0, QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentOpen))
        self.treeViewWidget.insertTopLevelItems(0, treeItems)
    
    def treeFolderDoubleClicked(self, item, col):
        #print(item.text(col))
        self.sftp_client.chdir(item.text(col))
        
        if(item.text(col) != ".."):
            self.sftp_remote_folder_path.append(item.text(col))
        elif len(self.sftp_remote_folder_path) > 1:
            del self.sftp_remote_folder_path[-1]
        #self.remoteDirectoryDisplay.setText("/".join(self.sftp_remote_folder_path))
        self.treeViewWidget.setHeaderLabels(["/".join(self.sftp_remote_folder_path)])
        remoteList = self.sftp_client.listdir_attr()
        
        self.treeViewWidget.clear()
        self.selected_remote_folder = ""
        self.fileTransferred = False
        treeItems = []
        #print(self.sftp_client.getcwd())
        if(self.sftp_client.getcwd()[:-1] != self.sftp_remote_folder_path[0]):
            treeItems.append(QtWidgets.QTreeWidgetItem([".."]))
        for fileAttr in remoteList:
            item = QtWidgets.QTreeWidgetItem([fileAttr.filename])
            treeItems.append(item)
            if(stat.S_ISDIR(fileAttr.st_mode)):
                item.setIcon(0, QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.FolderOpen))
            else:
                item.setIcon(0, QtGui.QIcon.fromTheme(QtGui.QIcon.ThemeIcon.DocumentOpen))
                if(fileAttr.filename == os.path.basename(self.blendFilePath)):
                    
                    self.fileTransferred = True
        self.treeViewWidget.insertTopLevelItems(0, treeItems)
        
        if(self.fileTransferred):
            print("Found file")
        self.updateButtons()
        
    def copySelectedFile(self):
        #print("/".join(self.sftp_remote_folder_path) + "/" + self.selected_remote_folder)
        remotePath = "/".join(self.sftp_remote_folder_path)
        if(self.selected_remote_folder != ""):
            remotePath = remotePath + "/" + self.selected_remote_folder
        fileName = self.blendFilePath[self.blendFilePath.rfind("/")+1:]
        #print(remotePath + "/" + fileName)
        self.progressDialog = QtWidgets.QProgressDialog(self)
        self.progressDialog.setWindowTitle("Tranferring File")
        self.progressDialog.setMinimum(0)
        self.progressDialog.setMaximum(os.path.getsize(self.blendFilePath))
        self.progressDialog.canceled.connect(self.stopFileTransfer)
        self.progressDialog.show()
        
        #Create transfer object
        self.fileTransferThread = QThread()
        self.fileTransferrer = fileUploader(self.sftp_client, self.blendFilePath, remotePath + "/" + fileName, self)
        
        self.fileTransferrer.moveToThread(self.fileTransferThread)
        
        self.fileTransferThread.started.connect(self.fileTransferrer.run)
        self.fileTransferrer.progress.connect(self.updateCopyProgress)
        self.fileTransferrer.finished.connect(self.fileTransferThread.quit)
        
        self.fileTransferThread.start()
        #self.sftp_client.put(self.blendFilePath, remotePath + "/" + fileName, self.updateCopyProgress)
        
    def updateCopyProgress(self, bytesTransferred, filesize):
        print("transferred " + str(bytesTransferred) + " of " + str(filesize) + " total bytes")
        if(not self.progressDialog.wasCanceled()):
            self.progressDialog.setValue(bytesTransferred)

    def stopFileTransfer(self):
        self.sftp_client.close()
        self.fileTransferThread.quit()
        self.fileTransferThread.wait()
        self.sftp_client = None
        self.sftp_client = SFTPClient.from_transport(self.ssh_client.get_transport())
        self.sftp_client.chdir("/".join(self.sftp_remote_folder_path))

    def renderRemotely(self):
        print("rendering...")
        remotePath = "/".join(self.sftp_remote_folder_path)
        
        remotePath = remotePath[1:]
        fileName = self.blendFilePath[self.blendFilePath.rfind("/")+1:]
        command = "blender -b \"" + remotePath + "/" + fileName + "\" -o //" + self.outputFileName  + " -f " + str(self.frameToRender) +  " -- --cycles-device " + self.cyclesDevice
        print(command)
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        while True:
            if stdout.channel.exit_status_ready():
                break
            else:
                for line in stdout:
                    print(line.strip())
                    completeSubstring = "| Finished"
                    if completeSubstring in line:
                        self.renderComplete = True
                for line in stderr:
                    print(f"Error: {line.strip()}")
            time.sleep(1)
        self.updateButtons()
        
    def viewRemoteRender(self):
        remotePath = "/".join(self.sftp_remote_folder_path)
        
        #remotePath = remotePath[1:]
        fileName = self.outputFileName + f'{int(self.frameToRender):04d}' + ".png"
        remoteFilePath = remotePath + "/" + fileName
        print(remoteFilePath)
        self.sftp_client.get(remoteFilePath, "C:/tmp/" + fileName)
        
        self.imageViewer = ImageViewer()
        self.imageViewer.load_file("C:/tmp/" + fileName)
        self.imageViewer.show()
        
        
    def updateButtons(self):
        if(self.fileTransferred):
            self.renderButton.setDisabled(False)
        else:
            self.renderButton.setDisabled(True)
            
        if(self.remoteMachineConnected):
            self.copyFileButton.setDisabled(False)
            self.remoteDirectoryRefresh.setDisabled(False)
        else:
            self.copyFileButton.setDisabled(True)
            self.remoteDirectoryRefresh.setDisabled(True)
            
        if(self.renderComplete):
            self.viewRenderButton.setDisabled(False)
        else:
            self.viewRenderButton.setDisabled(True)
        
app = QtWidgets.QApplication([])
mainWindow = RemoteConnectionApplication()


mainWindow.show()
app.exec()

