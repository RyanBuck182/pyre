"""
A package for externally creating code templates for the DiamondFire Minecraft server.

By Amp
7/21/2023
"""

import base64
import gzip
import socket
import time
import json
import os
from difflib import get_close_matches
from typing import Tuple
from dfpyre.items import *

COL_WARN = '\x1b[33m'
COL_RESET = '\x1b[0m'
COL_SUCCESS = '\x1b[32m'
COL_ERROR = '\x1b[31m'

CODEBLOCK_DATA_PATH = os.path.join(os.path.dirname(__file__), 'data/data.json')

VARIABLE_TYPES = {'txt', 'num', 'item', 'loc', 'var', 'snd', 'part', 'pot', 'g_val', 'vec'}
TEMPLATE_STARTERS = {'event', 'entity_event', 'func', 'process'}

TARGETS = {'Selection', 'Default', 'Killer', 'Damager', 'Shooter', 'Victim', 'AllPlayers', 'Projectile', 'AllEntities', 'AllMobs', 'LastEntity'}
TARGET_CODEBLOCKS = {'player_action', 'entity_action', 'if_player', 'if_entity'}
DEFAULT_TARGET = 'Selection'  # ironically not 'Default'


class CodeBlock:
    def __init__(self, name: str, args: Tuple=(), target: str=DEFAULT_TARGET, data={}):
        self.name = name
        self.args = args
        self.target = target
        self.data = data


def _warn(message):
    print(f'{COL_WARN}! WARNING ! {message}{COL_RESET}')


def _warnUnrecognizedName(codeblockType: str, codeblockName: str):
    close = get_close_matches(codeblockName, TAGDATA[codeblockType].keys())
    if close:
        _warn(f'Code block name "{codeblockName}" not recognized. Did you mean "{close[0]}"?')
    else:
        _warn(f'Code block name "{codeblockName}" not recognized. Try spell checking or retyping without spaces.')

def _warnUnrecognizedTarget(target: str):
    close = get_close_matches(target, TARGETS)
    if close:
        _warn(f'Target "{target}" not recognized. Did you mean "{close[0]}"?')
    else:
        _warn(f'Target "{target}" not recognized. Try spell checking or retyping without spaces.')


def _loadCodeblockData():
    tagData = {}
    if os.path.exists(CODEBLOCK_DATA_PATH):
        with open(CODEBLOCK_DATA_PATH, 'r') as f:
            tagData = json.load(f)
    else:
        _warn('data.json not found -- Item tags and error checking will not work.')
        return ({}, set(), set())
    
    del tagData['meta']

    allNames = [x for l in [d.keys() for d in tagData.values()] for x in l]  # flatten list
    return (
        tagData,
        set(tagData['extras'].keys()),
        set(allNames)
    )

TAGDATA, TAGDATA_EXTRAS_KEYS, ALL_CODEBLOCK_NAMES = _loadCodeblockData()

def _addInverted(data, inverted):
    """
    If inverted is true, add 'inverted': 'NOT' to data.
    """
    if inverted:
        data['inverted'] = 'NOT'


def _convertDataTypes(args):
    convertedArgs = []
    for value in args:
        if type(value) in {int, float}:
            convertedArgs.append(num(value))
        elif type(value) is str:
            convertedArgs.append(text(value))
        else:
            convertedArgs.append(value)
    return tuple(convertedArgs)


def _reformatCodeblockTags(tags, codeblockType: str, codeblockName: str):
    """
    Turns data.json tag items into DiamondFire formatted tag items
    """
    reformattedTags = []
    for tagItem in tags:
        newTagItem = {
            'item': {
                'id': 'bl_tag',
                'data': {
                    'option': tagItem['option'],
                    'tag': tagItem['tag'],
                    'action': codeblockName,
                    'block': codeblockType
                }
            },
            'slot': tagItem['slot']
        }
        reformattedTags.append(newTagItem)
    return reformattedTags


def _getCodeblockTags(codeblockType: str, codeblockName: str):
    """
    Get tags for the specified codeblock type and name
    """
    tags = None
    if codeblockType in TAGDATA_EXTRAS_KEYS:
        tags = TAGDATA['extras'][codeblockType]
    else:
        tags = TAGDATA[codeblockType].get(codeblockName)
    return _reformatCodeblockTags(tags, codeblockType, codeblockName)


def _buildBlock(codeblock: CodeBlock):
    """
    Builds a properly formatted block from a CodeBlock object.
    """
    finalBlock = codeblock.data.copy()
    codeblockType = codeblock.data.get('block')
    
    # add target if necessary ('Selection' is the default when 'target' is blank)
    if codeblockType in TARGET_CODEBLOCKS and codeblock.target != DEFAULT_TARGET:
        if codeblock.target not in TARGETS:
            _warnUnrecognizedTarget(codeblock.target)
        else:
            finalBlock['target'] = codeblock.target
    
    # add items into args
    finalArgs = [arg.format(slot) for slot, arg in enumerate(codeblock.args) if arg.type in VARIABLE_TYPES]
    
    # check for unrecognized name, add tags
    if codeblockType is not None:  # for brackets
        if codeblock.name not in ALL_CODEBLOCK_NAMES:
            _warnUnrecognizedName(codeblockType, codeblock.name)
        else:
            tags = _getCodeblockTags(codeblockType, codeblock.name)
            if len(finalArgs) + len(tags) > 27:
                finalArgs = finalArgs[:(27-len(tags))]  # trim list if over 27 elements
            finalArgs.extend(tags)  # add tags to end
    
    finalBlock['args'] = {'items': finalArgs}
    return finalBlock


def _dfEncode(jsonString: str) -> str:
    """
    Encodes a stringified json.
    """
    encodedString = gzip.compress(jsonString.encode('utf-8'))
    return base64.b64encode(encodedString).decode('utf-8')


def sendToDf(templateCode: str, name: str='Unnamed Template', author: str='pyre'):
    """
    Sends a template to DiamondFire via recode item api.

    :param str templateCode: The code for the template as a base64 string.
    :param str name: The name of the template.
    :param str author: The author of the template.
    """
    templateData = f"""{{\
Count:1b,\
id:"minecraft:yellow_shulker_box",\
tag:{{\
display:{{\
Name:'{{"extra":[{{"italic":false,"color":"#FF5C00","text":">> "}},{{"italic":false,"color":"#FFC700","text":"{name}"}}],"text":""}}',\
Lore:[
'{{"extra":[{{"italic":false,"color":"gray","text":"This template was generated by "}},{{"italic":false,"color":"gold","text":"pyre"}},{{"italic":false,"color":"gray","text":"."}}],"text":""}}',\
'{{"extra":[{{"italic":false,"color":"gray","text":"https://github.com/Amp63/pyre"}},{{"italic":false,"underlined":false,"strikethrough":false,"obfuscated":false,"color":"gray","text":""}}],"text":""}}'\
]\
}},\
PublicBukkitValues:{{\
"hypercube:codetemplatedata":'{{\
"author":"{author}",\
"name":"{name}",\
"version":1,\
"code":"{templateCode}"\
}}'\
}}\
}}\
}}\
"""
    itemName = 'pyre Template - ' + name
    data = {'type': 'nbt', 'source': itemName, 'data': templateData}

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(('127.0.0.1', 31372))
    except ConnectionRefusedError:
        print(f"""{COL_ERROR}Could not connect to recode item API. Possible problems:
    - Minecraft is not open
    - Recode is not installed (get it here: https://modrinth.com/mod/recode or join the discord here: https://discord.gg/GWxWtcwA2C){COL_RESET}""")
        s.close()
        return
    
    s.send((str(data) + '\n').encode('utf-8'))
    received = json.loads(s.recv(1024).decode())
    status = received['status']
    if status == 'success':
        print(f'{COL_SUCCESS}Template sent to client successfully.{COL_RESET}')
    else:
        error = received['error']
        print(f'{COL_ERROR}Error sending template: {error}{COL_RESET}')
    
    s.close()
    time.sleep(0.5)


class DFTemplate:
    """
    Represents a DiamondFire code template.
    """
    def __init__(self, name: str=None):
        self.codeBlocks = []
        self.closebracket = None
        self.name = name


    def _setTemplateName(self, firstBlock):
        if self.name is not None:
            return
        if 'data' in firstBlock:
            self.name = firstBlock['data']
        else:
            self.name = firstBlock['block'] + '_' + firstBlock['action']


    def build(self) -> str:
        """
        Build this template.

        :return: String containing encoded template data.
        """
        templateDictBlocks = [_buildBlock(codeblock) for codeblock in self.codeBlocks]
        templateDict = {'blocks': templateDictBlocks}
        firstBlock = templateDictBlocks[0]
        if firstBlock['block'] not in TEMPLATE_STARTERS:
            _warn('Template does not start with an event, function, or process.')

        self._setTemplateName(firstBlock)

        print(f'{COL_SUCCESS}Template built successfully.{COL_RESET}')

        jsonString = json.dumps(templateDict, separators=(',', ':'))
        return _dfEncode(jsonString)
    

    def buildAndSend(self):
        """
        Builds this template and sends it to DiamondFire automatically.
        """
        templateCode = self.build()
        sendToDf(templateCode, name=self.name)
    

    def clear(self):
        """
        Clears this template's data.
        """
        self.__init__()
    

    def _openbracket(self, btype: str='norm'):
        bracket = CodeBlock('Bracket', data={'id': 'bracket', 'direct': 'open', 'type': btype})
        self.codeBlocks.append(bracket)
        self.closebracket = btype
    

    # command methods
    def playerEvent(self, name: str):
        cmd = CodeBlock(name, data={'id': 'block', 'block': 'event', 'action': name})
        self.codeBlocks.append(cmd)
    

    def entityEvent(self, name: str):
        cmd = CodeBlock(name, data={'id': 'block', 'block': 'entity_event', 'action': name})
        self.codeBlocks.append(cmd)
    

    def function(self, name: str):
        cmd = CodeBlock('function', data={'id': 'block', 'block': 'func', 'data': name})
        self.codeBlocks.append(cmd)
    

    def process(self, name: str):
        cmd = CodeBlock('process', data={'id': 'block', 'block': 'process', 'data': name})
        self.codeBlocks.append(cmd)
    

    def callFunction(self, name: str, parameters={}):
        if parameters:
            for key in parameters.keys():
                self.setVariable('=', var(key, scope='local'), parameters[key])
        
        cmd = CodeBlock('call_func', data={'id': 'block', 'block': 'call_func', 'data': name})
        self.codeBlocks.append(cmd)
    

    def startProcess(self, name: str):
        cmd = CodeBlock('start_process', data={'id': 'block', 'block': 'start_process', 'data': name})
        self.codeBlocks.append(cmd)


    def playerAction(self, name: str, *args, target: str=DEFAULT_TARGET):
        args = _convertDataTypes(args)
        cmd = CodeBlock(name, args, target=target, data={'id': 'block', 'block': 'player_action', 'action': name})
        self.codeBlocks.append(cmd)
    

    def gameAction(self, name: str, *args):
        args = _convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'game_action', 'action': name})
        self.codeBlocks.append(cmd)
    

    def entityAction(self, name: str, *args, target: str=DEFAULT_TARGET):
        args = _convertDataTypes(args)
        cmd = CodeBlock(name, args, target=target, data={'id': 'block', 'block': 'entity_action', 'action': name})
        self.codeBlocks.append(cmd)
    

    def ifPlayer(self, name: str, *args, target: str=DEFAULT_TARGET, inverted: bool=False):
        args = _convertDataTypes(args)
        data = {'id': 'block', 'block': 'if_player', 'action': name}
        _addInverted(data, inverted)
        cmd = CodeBlock(name, args, target=target, data=data)
        self.codeBlocks.append(cmd)
        self._openbracket()
    

    def ifVariable(self, name: str, *args, inverted: bool=False):
        args = _convertDataTypes(args)
        data = {'id': 'block', 'block': 'if_var', 'action': name}
        _addInverted(data, inverted)
        cmd = CodeBlock(name, args, data=data)
        self.codeBlocks.append(cmd)
        self._openbracket()
    

    def ifGame(self, name: str, *args, inverted: bool=False):
        args = _convertDataTypes(args)
        data = {'id': 'block', 'block': 'if_game', 'action': name}
        _addInverted(data, inverted)
        cmd = CodeBlock(name, args, data=data)
        self.codeBlocks.append(cmd)
        self._openbracket()
    

    def ifEntity(self, name: str, *args, target: str=DEFAULT_TARGET, inverted: bool=False):
        args = _convertDataTypes(args)
        data = {'id': 'block', 'block': 'if_entity', 'action': name}
        _addInverted(data, inverted)
        cmd = CodeBlock(name, args, target=target, data=data)
        self.codeBlocks.append(cmd)
        self._openbracket()


    def else_(self):
        cmd = CodeBlock('else', data={'id': 'block', 'block': 'else'})
        self.codeBlocks.append(cmd)
        self._openbracket()
    

    def repeat(self, name: str, *args, subAction: str=None):
        args = _convertDataTypes(args)
        data = {'id': 'block', 'block': 'repeat', 'action': name}
        if subAction is not None:
            data['subAction'] = subAction
        cmd = CodeBlock(name, args, data=data)
        self.codeBlocks.append(cmd)
        self._openbracket('repeat')


    def bracket(self, *args):
        args = _convertDataTypes(args)
        cmd = CodeBlock('Bracket', data={'id': 'bracket', 'direct': 'close', 'type': self.closebracket})
        self.codeBlocks.append(cmd)
    

    def control(self, name: str, *args):
        args = _convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'control', 'action': name})
        self.codeBlocks.append(cmd)
    

    def selectObject(self, name: str, *args):
        args = _convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'select_obj', 'action': name})
        self.codeBlocks.append(cmd)
    

    def setVariable(self, name: str, *args):
        args = _convertDataTypes(args)
        cmd = CodeBlock(name, args, data={'id': 'block', 'block': 'set_var', 'action': name})
        self.codeBlocks.append(cmd)
    

    def return_(self, returndata={}):
        for key in returndata:
            self.setVariable('=', var(key, scope='local'), returndata[key])
        self.control('Return')