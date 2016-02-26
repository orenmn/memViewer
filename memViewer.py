import sys
import collections
import subprocess
import ctypes
import tkinter
import tkinter.messagebox
#from tkinter.font import nametofont

import genUtils


'''
to do:
    - make the cursor stay on the same byte after pressing tab.
    - make the cursor stay on the same nibble/byte after changing chunk type?
'''

USAGE_STR = (
    '''
    ### python 3 ###
    usage: python memViewer.py <watchedProcessId> [<initMemToViewAddr>]

    (watchedProcessId can be determined easily by using the task manager)
    ''')

ByteInTextWidg = collections.namedtuple(
    'ByteInTextWidg', ('val', 'lineNum', 'offsetInLine'))

####### begin configurations constants #######
NUM_OF_MS_BETWEEN_MEM_VIEW_UPDATES = 0x100
NUM_OF_MS_UNTIL_VIEWS_INIT = 0x40
RETURN_TO_VIEW_MODE_KEY_SYMS_SET = {'v', 'V', 'q', 'Q', 'Escape'}
SET_MEM_ADDR_ENTRY_AS_ADDR_TO_VIEW_KEY_SYM = 'Return'
WRITE_MODIFIED_MEM_KEY_SYM = 'Return'
SET_FOCUS_ON_ADDR_ENTRY_KEY_SYMS_SET = {'g', 'G'}
ENTER_READ_MODE_KEY_SYMS_SET = {'r', 'R'}
ENTER_WRITE_MODE_KEY_SYMS_SET = {'w', 'W'}
OPEN_NEW_MEMVIEWER_INSTANCE_KEY_SYMS_SET = {'n', 'N'}
DEFAULT_NUM_OF_CHUNKS_IN_LINE = 0x10
DEFAULT_VIEWER_CHUNK_TYPE_STR = 'bytes'
NEW_CHUNK_TYPE_CHAR_TO_CHUNK_TYPE_STR_DICT = {
    '1': 'bytes',
    '2': 'words',
    '4': 'dwords'}
MAX_ADDR_TO_VIEW = 0xffffffff
####### end configurations constants #######

cOpenProcess = ctypes.windll.kernel32.OpenProcess
cReadProcessMemory = ctypes.windll.kernel32.ReadProcessMemory
cWriteProcessMemory = ctypes.windll.kernel32.WriteProcessMemory
cCloseHandle = ctypes.windll.kernel32.CloseHandle
cGetLastError = ctypes.windll.kernel32.GetLastError

'''
i wasted a lot of time on searching for a way to determine this in real 
time, but i failed.
'''
LINE_HEIGHT_IN_PIXELS = 16 + 1 / 6

NUM_OF_DIGITS_IN_ADDR = 8
'''
for some annoying reason, the default font of an Entry is not a mono font,
so 'd', for example, is too wide to fit there 8 times when the width is set 
to 8.
'''
MEM_ADDR_ENTRY_WIDTH = NUM_OF_DIGITS_IN_ADDR + 3 

NUM_OF_NIBBLES_IN_A_BYTE = 2
NULL = 0
PROCESS_ALL_ACCESS = 0x1F0FFF
DEC_DIGITS_KEY_SYMS_SET = {
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
HEX_DIGITS_KEY_SYMS_SET = DEC_DIGITS_KEY_SYMS_SET | {
    'a', 'b', 'c', 'd', 'e', 'f', 'A', 'B', 'C', 'D', 'E', 'F'}
DELETE_KEY_SYMS_STRS_SET = {'BackSpace', 'Delete'}
NAVIG_KEY_SYMS_STRS_SET = {'Up', 'Down', 'Left', 'Right', 'Home', 'End'}
NAVIG_AND_DELETE_KEY_SYMS_STRS_SET = (
    DELETE_KEY_SYMS_STRS_SET | NAVIG_KEY_SYMS_STRS_SET)
TKINTER_ALT_BITMASK = 0x20000
TKINTER_CTRL_BITMASK = 0x4
TKINTER_SHIFT_BITMASK = 0x1
READ_ONLY_MODES_STRS_SET = {'read', 'view'}
CTRL_C_EVENT_CHAR = '\x03'
CTRL_V_EVENT_CHAR = '\x16'
CTRL_A_EVENT_CHAR = '\x01'
PASSIVE_CTRL_KEY_SHORTCUTS_EVENTS_CHARS = {
    CTRL_C_EVENT_CHAR, CTRL_A_EVENT_CHAR}

VIEWER_CHUNK_TYPE_STR_TO_NUM_OF_BYTES_IN_CHUNK_DICT = {
    'bytes': 1,
    'words': 2,
    'dwords': 4}


WINDOWS_ERROR_CODE_TO_ERROR_NAME_DICT = {
    0x1e7: 'ERROR_INVALID_ADDRESS',
    0x3e6: 'ERROR_NOACCESS',
    0x57: 'ERROR_INVALID_PARAMETER'}

class NotASpecialMemViewerKeyException(Exception):
    pass

class ASpecialGenericKeyToLetTkinterHandleException(Exception):
    pass

class OperationOnWatchedProcessFailException(Exception):
    pass


class MemViewer(object):
    def __init__(self, watchedProcessId, initMemToViewAddr):
        self.watchedProcessId = watchedProcessId

        self.tkRoot = tkinter.Tk()
        self.tkRoot.wm_title('memViewer.py')
        self.tkRoot.bind(
            '<Configure>', self.handleConfigChange)
        self.lastWindowHeight = 0

        self.upperFrame = tkinter.Frame(self.tkRoot)
        self.upperFrame.pack(
            side=tkinter.TOP, expand=False, 
            fill=tkinter.X)

        self.lowerFrame = tkinter.Frame(self.tkRoot)
        self.lowerFrame.pack(
            side=tkinter.TOP, expand=True, 
            fill=tkinter.Y)

        self.viewerModeStrVar = tkinter.StringVar()
        self.viewerModeLabel = tkinter.Label(
            master=self.upperFrame, textvariable=self.viewerModeStrVar)
        self.viewerModeLabel.pack(
            side=tkinter.LEFT, fill=tkinter.X, 
            expand=False)
        self.viewerModeStrVar.set('view')

        self.viewerChunksTypeStrVar = tkinter.StringVar()
        self.viewerChunksTypeLabel = tkinter.Label(
            master=self.upperFrame, textvariable=self.viewerChunksTypeStrVar)
        self.viewerChunksTypeLabel.pack(
            side=tkinter.LEFT, fill=tkinter.X, 
            expand=False)
        self.viewerChunksTypeStrVar.set(DEFAULT_VIEWER_CHUNK_TYPE_STR)

        self.numOfChunksInLine = DEFAULT_NUM_OF_CHUNKS_IN_LINE

        self.memAddrEntry = tkinter.Entry(
            master=self.upperFrame, width=MEM_ADDR_ENTRY_WIDTH)
        self.memAddrEntry.pack(
            side=tkinter.RIGHT, fill=tkinter.X, 
            expand=False)
        self.memAddrEntry.insert(
            tkinter.END, genUtils.numToHexStr(
                initMemToViewAddr, NUM_OF_DIGITS_IN_ADDR))
        self.memAddrEntry.bind(
            '<Key>',
            lambda event: self.handlePressingAKeyInsideMemAddrEntry(event))
        self.memAddrEntry.focus_set()

        self.addrLabel = tkinter.Label(master=self.upperFrame, text='address')
        self.addrLabel.pack(
            side=tkinter.RIGHT, fill=tkinter.X, 
            expand=False)

        self.memLinesAddrsTextWidg = tkinter.Text(
            master=self.lowerFrame, width=NUM_OF_DIGITS_IN_ADDR, 
            state=tkinter.DISABLED)
        self.memLinesAddrsTextWidg.pack(
            side=tkinter.LEFT, fill=tkinter.Y)
        self.memToViewAddrStack = [initMemToViewAddr]
        self.memToViewAddrStackPtrAsInd = 0

        self.memBinReprTextWidg = tkinter.Text(master=self.lowerFrame)
        self.memBinReprTextWidg.pack(
            side=tkinter.LEFT, fill=tkinter.Y)
        self.memBinReprTextWidg.bind(
            '<Key>',
            lambda event: self.handlePressingAKeyInsideMemBinReprTextWidg(
                event))

        self.memAsciiReprTextWidg = tkinter.Text(master=self.lowerFrame)
        self.memAsciiReprTextWidg.pack(
            side=tkinter.LEFT, fill=tkinter.Y)
        self.memAsciiReprTextWidg.bind(
            '<Key>',
            lambda event: self.handlePressingAKeyInsideMemAsciiReprTextWidg(
                event))

        self.updateMemViewsScheduledJobStr = ''



    def __enter__(self):
        self.watchedProcessHandle = cOpenProcess(
            PROCESS_ALL_ACCESS, False, self.watchedProcessId)
        if NULL == self.watchedProcessHandle:
            raise OperationOnWatchedProcessFailException()
        self.tkRoot.after(
            NUM_OF_MS_UNTIL_VIEWS_INIT, 
            self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts)


    def __exit__(self, *args):
        '''
        no idea why __exit__ is given more arguments. whatever...
        '''
        cCloseHandle(self.watchedProcessHandle)


    def handlePressingAKeyInsideMemBinReprTextWidg(self, event):
        '''
        print(event.char, event.keycode, event.type,
            event.char.encode('ascii'), event.keycode, event.keysym)
        print(self.memBinReprTextWidg.index(tkinter.INSERT))
        '''
        if 'write' == self.viewerModeStrVar.get():
            if (event.keysym in HEX_DIGITS_KEY_SYMS_SET) and not (
                    event.state & (
                        (TKINTER_CTRL_BITMASK | TKINTER_ALT_BITMASK))):
                self.memBinReprTextWidg.mark_set(
                    tkinter.INSERT,
                    self.overwriteCharInMemBinReprTextWidg(
                        event.char, 
                        self.memBinReprTextWidg.index(tkinter.INSERT), 
                        sync=True))
                return 'break'

            if CTRL_V_EVENT_CHAR == event.char:
                try:
                    strInClipboard = self.tkRoot.clipboard_get()
                except tkinter.TclError:
                    return 'break'
                if genUtils.isHexStr(strInClipboard):
                    self.memBinReprTextWidg.mark_set(
                        tkinter.INSERT,
                        self.overwriteStrInMemBinReprTextWidg(
                            strInClipboard,
                            self.memBinReprTextWidg.index(tkinter.INSERT),
                            sync=True))
                return 'break'

            if WRITE_MODIFIED_MEM_KEY_SYM == event.keysym:
                self.writeModifiedMemAndReturnToViewMode()
                return 'break'

        elif 'view' == self.viewerModeStrVar.get():
            if ('Up' == event.keysym) and (
                    1 == genUtils.tkinterPositionStrToPosition(
                        self.memBinReprTextWidg.index(tkinter.INSERT)).y):
                self.setMemToViewAddrToPrevLine()
                return 'break'
            if ('Down' == event.keysym) and (
                    self.getNumOfLines() == (
                        genUtils.tkinterPositionStrToPosition(
                            self.memBinReprTextWidg.index(
                                tkinter.INSERT)).y)):
                self.setMemToViewAddrToNextLine()
                return 'break'

        try:
            self.handlePressingASpecialMemViewerKey(event)
            return 'break'
        except NotASpecialMemViewerKeyException:
            return 'break'
        except ASpecialGenericKeyToLetTkinterHandleException:
            return


    def handlePressingAKeyInsideMemAsciiReprTextWidg(self, event):
        if 'write' == self.viewerModeStrVar.get():
            if event.char and (
                    event.char.isprintable() or (
                        ' ' == event.char)) and not (
                    event.state & (
                        (TKINTER_CTRL_BITMASK | TKINTER_ALT_BITMASK))):
                self.memAsciiReprTextWidg.mark_set(
                    tkinter.INSERT,
                    self.overwriteCharInMemAsciiReprTextWidg(
                        event.char, 
                        self.memAsciiReprTextWidg.index(tkinter.INSERT), 
                        sync=True))
                return 'break'

            if WRITE_MODIFIED_MEM_KEY_SYM == event.keysym:
                self.writeModifiedMemAndReturnToViewMode()
                return 'break'

        elif 'view' == self.viewerModeStrVar.get():
            if ('Up' == event.keysym) and (
                    1 == genUtils.tkinterPositionStrToPosition(
                        self.memAsciiReprTextWidg.index(tkinter.INSERT)).y):
                self.setMemToViewAddrToPrevLine()
                return 'break'
            if ('Down' == event.keysym) and (
                    self.getNumOfLines() == (
                        genUtils.tkinterPositionStrToPosition(
                            self.memAsciiReprTextWidg.index(
                                tkinter.INSERT)).y)):
                self.setMemToViewAddrToNextLine()
                return 'break'

        try:
            self.handlePressingASpecialMemViewerKey(event)
            return 'break'
        except NotASpecialMemViewerKeyException:
            return 'break'
        except ASpecialGenericKeyToLetTkinterHandleException:
            return


    def handlePressingAKeyInsideMemAddrEntry(self, event):
        if event.keysym in DELETE_KEY_SYMS_STRS_SET:
            return

        if (event.char in HEX_DIGITS_KEY_SYMS_SET) and not (
                event.state & TKINTER_ALT_BITMASK):
            if NUM_OF_DIGITS_IN_ADDR > len(self.memAddrEntry.get()):
                return
            return 'break'

        if CTRL_V_EVENT_CHAR == event.char:
            try:
                strInClipboard = self.tkRoot.clipboard_get()
            except tkinter.TclError:
                return 'break'
            if genUtils.isHexStr(strInClipboard):
                cursorPosition = self.memAddrEntry.index(
                    tkinter.INSERT)
                maxNumOfCharsToPaste = NUM_OF_DIGITS_IN_ADDR - cursorPosition
                self.memAddrEntry.insert(
                    cursorPosition, strInClipboard[:maxNumOfCharsToPaste])
                self.memAddrEntry.delete(
                    NUM_OF_DIGITS_IN_ADDR, tkinter.END)
            return 'break'

        if SET_MEM_ADDR_ENTRY_AS_ADDR_TO_VIEW_KEY_SYM == event.keysym:
            try:
                newAddr = genUtils.hexStrToInt(
                    self.memAddrEntry.get())
            except ValueError:
                pass
            else:
                if newAddr != self.memToViewAddrStack[
                        self.memToViewAddrStackPtrAsInd]:
                    self.memToViewAddrStackPtrAsInd += 1
                    self.memToViewAddrStack = self.memToViewAddrStack[
                        :self.memToViewAddrStackPtrAsInd]
                    self.memToViewAddrStack.append(newAddr)
                    self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts(
                        anyMode=True)
            return 'break'

        if 'view' == self.viewerModeStrVar.get():
            if 'Up' == event.keysym:
                self.setMemToViewAddrToPrevLine()
                return 'break'
            if 'Down' == event.keysym:
                self.setMemToViewAddrToNextLine()
                return 'break'

        try:
            self.handlePressingASpecialMemViewerKey(event)
            return 'break'
        except NotASpecialMemViewerKeyException:
            return 'break'
        except ASpecialGenericKeyToLetTkinterHandleException:
            return


    def handlePressingASpecialMemViewerKey(self, event):
        if event.state & TKINTER_ALT_BITMASK:
            if 'F4' == event.keysym:
                self.tkRoot.destroy()
                return
            if 'view' == self.viewerModeStrVar.get():
                if event.char in NEW_CHUNK_TYPE_CHAR_TO_CHUNK_TYPE_STR_DICT:
                    self.setViewerChunksType(
                        NEW_CHUNK_TYPE_CHAR_TO_CHUNK_TYPE_STR_DICT[event.char])
                    return
                if ('Left' == event.keysym) and (
                        0 < self.memToViewAddrStackPtrAsInd):
                    self.memToViewAddrStackPtrAsInd -= 1
                    self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts(
                        updateMemAddrEntry=True)
                    return
                if ('Right' == event.keysym) and (
                        len(self.memToViewAddrStack) > (
                            self.memToViewAddrStackPtrAsInd + 1)):
                    self.memToViewAddrStackPtrAsInd += 1
                    self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts(
                        updateMemAddrEntry=True)

        elif event.state & TKINTER_CTRL_BITMASK:
            if (event.char in PASSIVE_CTRL_KEY_SHORTCUTS_EVENTS_CHARS) or (
                    event.keysym in NAVIG_KEY_SYMS_STRS_SET):
                raise ASpecialGenericKeyToLetTkinterHandleException()
            if event.keysym in OPEN_NEW_MEMVIEWER_INSTANCE_KEY_SYMS_SET:
                subprocess.Popen(
                    ['python', sys.argv[0], str(self.watchedProcessId),
                    hex(self.memToViewAddrStack[
                        self.memToViewAddrStackPtrAsInd])])
                return
        else:
            if event.keysym in SET_FOCUS_ON_ADDR_ENTRY_KEY_SYMS_SET:
                self.memAddrEntry.focus_set()
                return
            if event.keysym in ENTER_READ_MODE_KEY_SYMS_SET:
                self.setViewerMode('read')
                return
            if event.keysym in ENTER_WRITE_MODE_KEY_SYMS_SET:
                self.setViewerMode('write')
                return
            if event.keysym in RETURN_TO_VIEW_MODE_KEY_SYMS_SET:
                self.setViewerMode('view')
                return
            if 'Tab' == event.keysym:
                if self.memBinReprTextWidg == event.widget:
                    self.memAsciiReprTextWidg.focus_set()
                else:
                    self.memBinReprTextWidg.focus_set()
                return
            if 'plus' == event.keysym:
                self.incNumOfChunksInLine()
                return
            if 'minus' == event.keysym:
                self.decNumOfChunksInLine()
                return
            if event.keysym in NAVIG_KEY_SYMS_STRS_SET:
                raise ASpecialGenericKeyToLetTkinterHandleException()

        raise NotASpecialMemViewerKeyException()


    def overwriteStrInMemBinReprTextWidg(
            self, strToWrite, positionStr, sync=False):
        '''
        return the positionStr of the char after the last overwritten nibble.
        '''
        currPositionStr = positionStr
        for charToWrite in strToWrite:
            currPositionStr = self.overwriteCharInMemBinReprTextWidg(
                charToWrite, currPositionStr, sync)
    
        return currPositionStr


    def overwriteCharInMemBinReprTextWidg(
            self, charToWrite, positionStr, sync=False):
        '''
        return the positionStr of the char after the overwritten nibble.
        '''
        if self.memBinReprTextWidg.get(positionStr).isspace():
            nibbleToOverwritePositionStr = genUtils.getTextWidgNextPosition(
                self.memBinReprTextWidg, 
                self.getMemBinReprTextWidgWidth(),
                positionStr)
            if self.getNumOfLines() < genUtils.tkinterPositionStrToPosition(
                    nibbleToOverwritePositionStr).y:
                return positionStr
        else:
            nibbleToOverwritePositionStr = positionStr
        genUtils.overwriteCharInTextWidg(
            self.memBinReprTextWidg, nibbleToOverwritePositionStr, 
            charToWrite)
        if sync:
            self.syncAsciiTextWidgWithBinTextWidg(
                nibbleToOverwritePositionStr)
        return genUtils.getTextWidgNextPosition(
            self.memBinReprTextWidg, self.getMemBinReprTextWidgWidth(),
            nibbleToOverwritePositionStr)


    def overwriteStrInMemAsciiReprTextWidg(
            self, strToWrite, positionStr, sync=False):
        '''
        return the positionStr of the char after the last overwritten byte.
        '''
        currPositionStr = positionStr
        for charToWrite in strToWrite:
            currPositionStr = self.overwriteCharInMemAsciiReprTextWidg(
                charToWrite, currPositionStr, sync)
        return currPositionStr


    def overwriteCharInMemAsciiReprTextWidg(
            self, charToWrite, positionStr, sync=False):
        '''
        return the positionStr of the char after the overwritten byte.
        '''
        if '\n' == self.memAsciiReprTextWidg.get(positionStr):
            byteOverwrittenPositionStr = genUtils.getTextWidgNextPosition(
                self.memAsciiReprTextWidg, 
                self.getMemAsciiReprTextWidgWidth(),
                positionStr)
            if self.getNumOfLines() < genUtils.tkinterPositionStrToPosition(
                    byteOverwrittenPositionStr).y:
                return positionStr
        else:
            byteOverwrittenPositionStr = positionStr
        genUtils.overwriteCharInTextWidg(
            self.memAsciiReprTextWidg, byteOverwrittenPositionStr, 
            charToWrite)
        if sync:
            self.syncBinTextWidgWithAsciiTextWidg(byteOverwrittenPositionStr)
        return genUtils.getTextWidgNextPosition(
            self.memAsciiReprTextWidg, 
            self.getMemAsciiReprTextWidgWidth(),
            byteOverwrittenPositionStr)


    def syncBinTextWidgWithAsciiTextWidg(self, changedBytePositionStr):
        changedByte = ByteInTextWidg(
            ord(self.memAsciiReprTextWidg.get(changedBytePositionStr)),
            *genUtils.tkinterPositionStrToPosition(changedBytePositionStr))
        chunkIndInLine = changedByte.offsetInLine // (
            self.getNumOfBytesInChunk())
        indInChunk = changedByte.offsetInLine % (
            self.getNumOfBytesInChunk())
        highNibbleOffsetInChunkRepr = self.getNumOfNibblesInChunk() - (
            indInChunk * 2) - 2
        highNibbleXPosition = chunkIndInLine * (
            self.getNumOfNibblesInChunk() + 1) + highNibbleOffsetInChunkRepr
        self.overwriteStrInMemBinReprTextWidg(
            genUtils.numToHexStr(changedByte.val, NUM_OF_NIBBLES_IN_A_BYTE),
            genUtils.positionToTkinterPositionStr(
                genUtils.Position(changedByte.lineNum, highNibbleXPosition)))

        
    def syncAsciiTextWidgWithBinTextWidg(self, changedNibblePositionStr):
        changedByte = self.getByteInMemBinReprTextWidg(
            changedNibblePositionStr)
        self.overwriteCharInMemAsciiReprTextWidg(
            genUtils.getByteAsciiRepr(changedByte.val),
            genUtils.positionToTkinterPositionStr(
                genUtils.Position(
                    changedByte.lineNum, changedByte.offsetInLine)))


    def getByteInMemBinReprTextWidg(self, nibblePositionStr):
        nibbleYPosition, nibbleXPosition = (
            genUtils.tkinterPositionStrToPosition(
                nibblePositionStr))
        chunkStartXPositionDivisor = self.getNumOfNibblesInChunk() + 1
        nibbleOffsetInChunkRepr = nibbleXPosition % chunkStartXPositionDivisor
        chunkIndInLine = nibbleXPosition // chunkStartXPositionDivisor
        byteIndInChunk = self.getNumOfBytesInChunk() - (
            nibbleOffsetInChunkRepr // 2) - 1
        if 0 == (nibbleOffsetInChunkRepr % 2):
            bytePosition = genUtils.Position(nibbleYPosition, nibbleXPosition)
        else:
            bytePosition = genUtils.Position(
                nibbleYPosition, nibbleXPosition - 1)

        bytePositionStr = genUtils.positionToTkinterPositionStr(
            bytePosition)

        highNibbleChar = self.memBinReprTextWidg.get(bytePositionStr)
        lowNibbleChar = self.memBinReprTextWidg.get(
            genUtils.getTextWidgNextPosition(
                self.memBinReprTextWidg, self.getMemBinReprTextWidgWidth,
                bytePositionStr))
        byteVal = genUtils.hexStrToInt(highNibbleChar + lowNibbleChar)
        byteOffset = (
            chunkIndInLine * self.getNumOfBytesInChunk() + byteIndInChunk)

        return ByteInTextWidg(byteVal, bytePosition.y, byteOffset)


    def incNumOfChunksInLine(self):
        self.numOfChunksInLine += 1
        self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts()


    def decNumOfChunksInLine(self):
        if 1 < self.numOfChunksInLine:
            self.numOfChunksInLine -= 1
        self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts()


    def setViewerChunksType(self, newChunkTypeStr):
        origNumOfBytesInLine = self.getNumOfBytesInLine()
        self.viewerChunksTypeStrVar.set(newChunkTypeStr)
        self.numOfChunksInLine = max(
            origNumOfBytesInLine // self.getNumOfBytesInChunk(),
            1)
        self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts()


    def setViewerMode(self, newModeStr):
        self.readProcessMemAndUpdateBinAndAsciiMemViews(anyMode=True)
        if 'write' == newModeStr:
            self.memBinReprAtEnteringWriteMode = self.memBinReprTextWidg.get(
                '1.0', tkinter.END)
        self.viewerModeStrVar.set(newModeStr)


    def writeModifiedMemAndReturnToViewMode(self):
        memBytesAtEnteringWriteMode = (
            genUtils.memChunksAsHexStrToLittleEndianBytes(
                self.memBinReprAtEnteringWriteMode))
        binMemTextWidgBytes = genUtils.memChunksAsHexStrToLittleEndianBytes(
            self.memBinReprTextWidg.get('1.0', tkinter.END))
        for byteOffset, (origByte, currByte) in enumerate(zip(
                memBytesAtEnteringWriteMode, binMemTextWidgBytes)):
            if origByte != currByte:
                cBytesToWriteBuf = ctypes.create_string_buffer(
                    bytes([currByte]))
                cNumOfBytesWritten = ctypes.c_ulong()
                writeProcessMemoryResultCode = cWriteProcessMemory(
                    self.watchedProcessHandle, 
                    self.memToViewAddrStack[
                        self.memToViewAddrStackPtrAsInd] + byteOffset, 
                    cBytesToWriteBuf, 
                    ctypes.c_ulong(1), ctypes.byref(cNumOfBytesWritten))
                if not writeProcessMemoryResultCode:
                    errorCode = cGetLastError()
                    errorStr = WINDOWS_ERROR_CODE_TO_ERROR_NAME_DICT.get(
                        errorCode, hex(errorCode))
                    tkinter.messagebox.showerror(
                        title='Error',
                        message='Failed to write to process memory.\n'
                            'GetLastError: {}'.format(errorStr))
                    return
        self.setViewerMode('view')


    def readProcessMemAndUpdateBinAndAsciiMemViews(self, anyMode=False):
        if anyMode or ('view' == self.viewerModeStrVar.get()):
            origMemBinReprTextWidgCursorPosition = (
                self.memBinReprTextWidg.index(tkinter.INSERT))
            origMemAsciiReprTextWidgCursorPosition = (
                self.memAsciiReprTextWidg.index(tkinter.INSERT))

            watchedProcessMemBytes = self.readProcessMem(
                self.memToViewAddrStack[self.memToViewAddrStackPtrAsInd],
                self.getNumOfLines() * self.getNumOfBytesInLine())

            genUtils.updateDiffsInTextWidg(
                self.memBinReprTextWidg,
                genUtils.getBytesTextBinRepr(
                    watchedProcessMemBytes,
                    self.getNumOfBytesInLine(),
                    self.getNumOfBytesInChunk()))
            genUtils.updateDiffsInTextWidg(
                self.memAsciiReprTextWidg,
                genUtils.getBytesTextAsciiRepr(
                    watchedProcessMemBytes,
                    self.getNumOfBytesInLine()))

            self.memBinReprTextWidg.mark_set(
                tkinter.INSERT, 
                origMemBinReprTextWidgCursorPosition)
            self.memAsciiReprTextWidg.mark_set(
                tkinter.INSERT, 
                origMemAsciiReprTextWidgCursorPosition)


        if self.updateMemViewsScheduledJobStr:
            self.tkRoot.after_cancel(self.updateMemViewsScheduledJobStr)
        self.updateMemViewsScheduledJobStr = self.tkRoot.after(
            NUM_OF_MS_BETWEEN_MEM_VIEW_UPDATES, 
            self.readProcessMemAndUpdateBinAndAsciiMemViews)


    def readProcessMem(self, memAddrToRead, numOfBytesToRead):
        '''
        if the read failed, a zeroed buffer would be returned.
        '''
        cProcessMemBuf = ctypes.create_string_buffer(numOfBytesToRead)
        cNumOfBytesReadFromProcess = ctypes.c_ulong(0)
        cReadProcessMemory(
            self.watchedProcessHandle, memAddrToRead, cProcessMemBuf, 
            numOfBytesToRead, ctypes.byref(cNumOfBytesReadFromProcess))
        return cProcessMemBuf.raw


    def handleConfigChange(self, event):
        if ('view' == self.viewerModeStrVar.get()) and (
                self.getNumOfLines()) and (
                self.lastWindowHeight != event.height):
            self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts()


    def setMemToViewAddrToPrevLine(self):
        numOfBytesInLine = self.getNumOfBytesInLine()
        if numOfBytesInLine <= self.memToViewAddrStack[
                self.memToViewAddrStackPtrAsInd]:
            self.memToViewAddrStack[self.memToViewAddrStackPtrAsInd] -= (
                numOfBytesInLine)
            self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts()


    def setMemToViewAddrToNextLine(self):
        numOfBytesInLine = self.getNumOfBytesInLine()
        if MAX_ADDR_TO_VIEW >= (
                numOfBytesInLine + self.memToViewAddrStack[
                    self.memToViewAddrStackPtrAsInd]):
            self.memToViewAddrStack[self.memToViewAddrStackPtrAsInd] += (
                numOfBytesInLine)
            self.initMemLinesAddrsAndBinAndAsciiTextWidgsTexts()


    def initMemLinesAddrsAndBinAndAsciiTextWidgsTexts(
            self, anyMode=False, updateMemAddrEntry=False):
        if updateMemAddrEntry:
            self.memAddrEntry.delete(0, tkinter.END)
            self.memAddrEntry.insert(
                0, 
                genUtils.numToHexStr(
                    self.memToViewAddrStack[self.memToViewAddrStackPtrAsInd],
                    NUM_OF_DIGITS_IN_ADDR))
        self.initMemLinesAddrs()
        self.initBinAndAsciiTextWidgsTexts(anyMode)


    def initMemLinesAddrs(self):
        self.memLinesAddrsTextWidg.configure(state=tkinter.NORMAL)
        self.memLinesAddrsTextWidg.delete(1.0, tkinter.END)
        for lineInd in range(self.getNumOfLines()):
            lineMemAddr = self.memToViewAddrStack[
                self.memToViewAddrStackPtrAsInd] + (
                lineInd * self.getNumOfBytesInLine())
            lineMemAddrHexRepr = genUtils.numToHexStr(
                lineMemAddr, NUM_OF_DIGITS_IN_ADDR)
            self.memLinesAddrsTextWidg.insert(
                tkinter.END, lineMemAddrHexRepr)

        self.memLinesAddrsTextWidg.configure(
            state=tkinter.DISABLED)


    def initBinAndAsciiTextWidgsTexts(self, anyMode=False):
        self.memBinReprTextWidg.configure(
            width=self.getMemBinReprTextWidgWidth())
        self.memAsciiReprTextWidg.configure(
            width=self.getMemAsciiReprTextWidgWidth())

        origMemBinReprTextWidgCursorPosition = (
            self.memBinReprTextWidg.index(tkinter.INSERT))
        origMemAsciiReprTextWidgCursorPosition = (
            self.memAsciiReprTextWidg.index(tkinter.INSERT))

        self.memBinReprTextWidg.delete('1.0', tkinter.END)
        self.memAsciiReprTextWidg.delete('1.0', tkinter.END)

        fictiveMemBytes = b'\0' * (
            self.getNumOfLines() * self.getNumOfBytesInLine())
        self.memBinReprTextWidg.insert(
            '1.0', 
            genUtils.getBytesTextBinRepr(
                fictiveMemBytes, self.getNumOfBytesInLine(), 
                self.getNumOfBytesInChunk()))
        self.memAsciiReprTextWidg.insert(
            '1.0',
            genUtils.getBytesTextAsciiRepr(
                fictiveMemBytes, self.getNumOfBytesInLine()))

        self.memBinReprTextWidg.mark_set(
            tkinter.INSERT, 
            origMemBinReprTextWidgCursorPosition)
        self.memAsciiReprTextWidg.mark_set(
            tkinter.INSERT, 
            origMemAsciiReprTextWidgCursorPosition)

        self.readProcessMemAndUpdateBinAndAsciiMemViews(anyMode)


    def getMemBinReprTextWidgWidth(self):
        return (self.getNumOfBytesInLine() * NUM_OF_NIBBLES_IN_A_BYTE) + (
            self.numOfChunksInLine - 1)


    def getMemAsciiReprTextWidgWidth(self):
        return self.getNumOfBytesInLine()


    def getNumOfBytesInLine(self):
        return self.numOfChunksInLine * self.getNumOfBytesInChunk()


    def getNumOfNibblesInChunk(self):
        return 2 * self.getNumOfBytesInChunk()


    def getNumOfBytesInChunk(self):
        return VIEWER_CHUNK_TYPE_STR_TO_NUM_OF_BYTES_IN_CHUNK_DICT[
            self.viewerChunksTypeStrVar.get()]


    def getNumOfLines(self):
        return int(self.memBinReprTextWidg.winfo_height() / (
            LINE_HEIGHT_IN_PIXELS))


def openMemViewer(watchedProcessId, initMemToViewAddr='0'):
    with MemViewer(
            int(watchedProcessId), genUtils.hexStrToInt(initMemToViewAddr)):
        tkinter.mainloop()
    

# keyhandler for each. some handlers might call the same functions when proper.

if '__main__' == __name__:
    cmdArgsList = sys.argv[1:]
    numOfCmdArgs = len(cmdArgsList)
    if 1 <= numOfCmdArgs <= 2:
        openMemViewer(*cmdArgsList)
    else:
        print(USAGE_STR)
        '''
        openMemViewer('5568', '5a8f00')
        '''


# http://stackoverflow.com/questions/24832247/constantly-update-label-widgs-from-entry-widgs-tkinter
# http://stackoverflow.com/questions/12712585/cReadprocessmemory-with-ctypes
