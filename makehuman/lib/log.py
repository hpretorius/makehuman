#!/usr/bin/python2.7
# -*- coding: utf-8 -*-

"""
Logging.

**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehuman.org/

**Code Home Page:**    https://bitbucket.org/MakeHuman/makehuman/

**Authors:**           Glynn Clements

**Copyright(c):**      MakeHuman Team 2001-2015

**Licensing:**         AGPL3 (http://www.makehuman.org/doc/node/the_makehuman_application.html)

    This file is part of MakeHuman (www.makehuman.org).

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

**Coding Standards:**  See http://www.makehuman.org/node/165

Abstract
--------

Logging component. To be used instead of print statements.
"""

import sys
import os
import logging
import logging.config
import code
from logging import getLogger, getLevelName
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

from core import G
from getpath import getPath, getSysDataPath

NOTICE = 25
MESSAGE = logging.INFO

LEVEL_TO_STR = { DEBUG: "debug",
                 INFO: "info",
                 WARNING: "warning",
                 ERROR: "error",
                 CRITICAL: "critical",
                 NOTICE: "notice"
               }

def logLevelToStr(levelCode):
    if levelCode in LEVEL_TO_STR:
        return LEVEL_TO_STR[levelCode]
    else:
        levels = sorted(LEVEL_TO_STR.keys())
        i = 0
        while i < len(levels) and levelCode < levels[i]:
            i += 1
        i = min(i, len(levels)-1)
        return levels[i]

def _toUnicode(msg, *args):
    """
    Unicode representation of the formatted message.
    String is decoded with the codeset used by the filesystem of the operating
    system.
    """
    try:
        msg_ = msg % args
    except TypeError:
        # Also allow dict with keywords in format string, passed as first arg
        if len(args) == 1 and isinstance(args[0], dict):
            msg_ = msg % args[0]
        else:
            raise

    if isinstance(msg_, unicode):
        return msg_
    elif isinstance(msg_, basestring):
        try:
            return msg_.decode(sys.getdefaultencoding())
        except UnicodeError:
            pass
        try:
            return msg_.decode(sys.getfilesystemencoding())
        except UnicodeError:
            pass
        try:
            import locale
            return msg_.decode(locale.getpreferredencoding())
        except UnicodeError:
            pass

        return msg_.decode('UTF-8', 'replace')
    else:
        return msg_

def debug(msg, *args, **kwargs):
    try:
        logging.debug(msg, *args, **kwargs)
    except UnicodeError:
        msg_ = _toUnicode(msg, args)
        logging.debug(msg_, kwargs)

def warning(msg, *args, **kwargs):
    try:
        logging.warning(msg, *args, **kwargs)
    except UnicodeError:
        msg_ = _toUnicode(msg, args)
        logging.warning(msg_, kwargs)

def error(msg, *args, **kwargs):
    try:
        logging.error(msg, *args, **kwargs)
    except UnicodeError:
        msg_ = _toUnicode(msg, args)
        logging.error(msg_, kwargs)

def message(msg, *args, **kwargs):
    try:
        logging.info(msg, *args, **kwargs)
    except UnicodeError:
        msg_ = _toUnicode(msg, args)
        logging.info(msg_, kwargs)

# We have to make notice() appear to have been defined in the logging module
# so that logging.findCaller() finds its caller, not notice() itself
# This is required for the pathname, filename, module, funcName and lineno
# members of the LogRecord refer to the caller rather than to notice() itself.

_notice_src = r'''
def notice(format, *args, **kwargs):
    logging.log(NOTICE, format, *args, **kwargs)
'''
try:
    exec(code.compile_command(_notice_src, logging.info.func_code.co_filename))
except:
    def notice(format, *args, **kwargs):
        logging.log(NOTICE, format, *args, **kwargs)

logging.addLevelName(NOTICE, "NOTICE")
logging.addLevelName(MESSAGE, "MESSAGE")

def _splitpath(path):
    
    head, tail = os.path.split(path)
    if tail == '':
        return [head]
    return _splitpath(head) + [tail]

class NoiseFilter(logging.Filter):
    def filter(self, record):
        try:
            if record.msg.endswith(':\n%s'):
                record.msg = record.msg[:-4]
                record.args = record.args[:-1]
        except:
            import traceback
            traceback.print_exc()
        return True

class DowngradeFilter(logging.Filter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        try:
            if record.levelno > self.level:
                record.levelno = self.level
                record.levelname = logging.getLevelName(record.levelno)
        except:
            import traceback
            traceback.print_exc()
        return True

_logLevelColors = {
    DEBUG: 'grey',
    NOTICE: 'blue',
    WARNING: 'darkorange',
    ERROR: 'red',
    CRITICAL: 'red'
}

def getLevelColor(logLevel):
    global _logLevelColors
    if logLevel not in _logLevelColors:
        warning("Unknown log level color %s (%s)" % (logLevel, logLevelToStr(logLevel)))
    return _logLevelColors.get(logLevel, 'red')

class SplashLogHandler(logging.Handler):
    def emit(self, record):
        if G.app is not None and G.app.splash is not None:
            G.app.splash.logMessage(self.format(record).split('\n',1)[0] + '\n')

class StatusLogHandler(logging.Handler):
    def emit(self, record):
        if G.app is not None and G.app.statusBar is not None:
            G.app.statusBar.showMessage("%s", self.format(record))

class ApplicationLogHandler(logging.Handler):
    def emit(self, record):
        if G.app is not None and G.app.log_window is not None:
            G.app.addLogMessage(self.format(record), record.levelno)

_logger_notice_src = r'''
def _logger_notice(self, msg, *args, **kwargs):
    self.log(NOTICE, msg, *args, **kwargs)
'''
try:
    exec(code.compile_command(_logger_notice_src, logging.info.func_code.co_filename))
except:
    def _logger_notice(self, format, *args, **kwargs):
        self.log(NOTICE, format, *args, **kwargs)

class Logger(logging.Logger):
    message = logging.Logger.info
    notice = _logger_notice

def init():
    def config():
        userDir = getPath('')
        defaults = dict(mhUserDir = userDir.replace('\\','/'))

        try:
            filename = os.path.join(userDir, "logging.ini")
            if os.path.isfile(filename):
                logging.config.fileConfig(filename, defaults)
                return
        except Exception:
            pass

        try:
            logging.config.fileConfig(getSysDataPath('logging.ini'), defaults)
            return
        except Exception:
            pass

        try:
            logging.basicConfig(level = logging.DEBUG)
            return
        except Exception:
            pass

    logging.setLoggerClass(Logger)

    config()

    # Compatibility test for Python 2.6 logging module
    if hasattr(logging, "captureWarnings") and callable(logging.captureWarnings):
        logging.captureWarnings(True)

    try:
        logging.getLogger('OpenGL.formathandler').addFilter(NoiseFilter())
        logging.getLogger('OpenGL.extensions').addFilter(DowngradeFilter(logging.DEBUG))
    except Exception:
        import traceback
        traceback.print_exc()
