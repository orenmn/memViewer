import tkinter
import collections

NUM_OF_NIBBLES_IN_A_BYTE = 2


TextWidgsStrsDiff = collections.namedtuple(
    'TextWidgsStrsDiff', ('char1', 'char2', 'charPositionStr'))
Position = collections.namedtuple(
    'Position', ('y', 'x'))



def updateDiffsInTextWidg(textWidg, newTextWidgText):
    for origChar, newChar, positionStr in textWidgsStrsDiffsGenerator(
            textWidg.get('1.0', tkinter.END), newTextWidgText):
        overwriteCharInTextWidg(
            textWidg, positionStr, newChar)


def textWidgsStrsDiffsGenerator(textWidgStr1, textWidgStr2):
    currYPosition = 1
    currXPosition = 0
    for char1, char2 in zip(textWidgStr1, textWidgStr2):
        if '\n' == char1:
            currYPosition += 1
            currXPosition = 0
        else:
            if char1 != char2:
                yield TextWidgsStrsDiff(
                    char1, char2,
                    positionToTkinterPositionStr(
                        Position(currYPosition, currXPosition)))
            currXPosition += 1


def overwriteCharInTextWidg(
        textWidg, charPositionStr, charToWrite):
    textWidg.delete(charPositionStr)
    textWidg.insert(charPositionStr, charToWrite)

'''
def advanceTextWidgCursorPosition(textWidg, textWidgWidth):
    textWidg.mark_set(
        tkinter.INSERT, 
        getTextWidgNextPosition(
            textWidg, textWidgWidth, textWidg.index(tkinter.INSERT)))
'''


def getTextWidgNextPosition(textWidg, textWidgWidth, positionStr):
    yPosition, xPosition = tkinterPositionStrToPosition(positionStr)
    if textWidgWidth == xPosition:
        return positionToTkinterPositionStr(
            Position(yPosition + 1, 0))
    else:
        return positionToTkinterPositionStr(
            Position(yPosition, xPosition + 1))


def tkinterPositionStrToPosition(positionStr):
    return Position(
        *[int(offsetAsStr) for offsetAsStr in positionStr.split('.')])


def positionToTkinterPositionStr(position):
    return '{}.{}'.format(*position)


def memChunksAsHexStrToLittleEndianBytes(memChunksHexStr):
    memChunksAsHexStrsList = memChunksHexStr.split()
    return b''.join(
        (hexStrToLittleEndianBytes(memChunkAsHexStr) for (
            memChunkAsHexStr) in memChunksAsHexStrsList))


def hexStrToLittleEndianBytes(hexStr):
    print(hexStr)
    return bytes.fromhex(hexStr)[::-1]


def isHexStr(potentHexStr):
    try:
        hexStrToInt(potentHexStr)
        return True
    except ValueError:
        return False


def hexStrToInt(hexStr):
    return int(hexStr, 0x10)


def getAddrHexRepr(addr, numOfDigitsInAddr):
    return numToHexStr(addr, numOfDigitsInAddr)


def getBytesTextBinRepr(bytesToConvert, numOfBytesInLine, numOfBytesInChunk):
    if numOfBytesInLine == len(bytesToConvert):
        return getBytesLineBinRepr(bytesToConvert, numOfBytesInChunk)
    return '\n'.join((
        getBytesLineBinRepr(
            bytesToConvert[:numOfBytesInLine], numOfBytesInChunk),
        getBytesTextBinRepr(
            bytesToConvert[numOfBytesInLine:], 
            numOfBytesInLine, numOfBytesInChunk)))


def getBytesLineBinRepr(bytesToConvert, numOfBytesInChunk):
    if numOfBytesInChunk == len(bytesToConvert):
        return littleEndianBytesToNumAsHexStr(bytesToConvert)
    return ' '.join((
        littleEndianBytesToNumAsHexStr(bytesToConvert[:numOfBytesInChunk]),
        getBytesLineBinRepr(
            bytesToConvert[numOfBytesInChunk:], numOfBytesInChunk)))


def littleEndianBytesToNumAsHexStr(bytesToConvert):
    accuBytesAsNum = 0
    for aByte in bytesToConvert[::-1]:
        accuBytesAsNum *= 0x100
        accuBytesAsNum += aByte
    return numToHexStr(
        accuBytesAsNum, len(bytesToConvert) * NUM_OF_NIBBLES_IN_A_BYTE)


def numToHexStr(num, numOfDigitsToFill):
    return hex(num)[2:].zfill(numOfDigitsToFill)


def getBytesTextAsciiRepr(bytesToConvert, numOfBytesInLine):
    if numOfBytesInLine == len(bytesToConvert):
        return getBytesLineAsciiRepr(bytesToConvert)
    return '\n'.join((
        getBytesLineAsciiRepr(bytesToConvert[:numOfBytesInLine]),
        getBytesTextAsciiRepr(
            bytesToConvert[numOfBytesInLine:], numOfBytesInLine)))


def getBytesLineAsciiRepr(bytesToConvert):
    return ''.join(
        (getByteAsciiRepr(currByte) for currByte in bytesToConvert))


def getByteAsciiRepr(byteVal):
    byteAsChar = chr(byteVal)
    if byteAsChar.isprintable() or (' ' == byteAsChar):
        return byteAsChar
    else:
        return '.'


'''
print(getBytesTextBinRepr(b'\0\nasasdfzxcvqwer', 8, 4))
print(getBytesTextAsciiRepr(b'\0\nasasdfzxcvqwer', 8))
'''