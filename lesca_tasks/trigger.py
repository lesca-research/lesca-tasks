import logging

from .logging import logger

NO_TRIGGER = None
TRIGGER_1 = 1
TRIGGER_2 = 2
TRIGGER_3 = 3
TRIGGER_4 = 4
TRIGGER_5 = 5

try:
    import win32com.client

    class DCOMTrigger:
        
        def __init__(self, target):
            self.target = target
            dcom_label = {'oxysoft' : 'Oxysoft.OxyApplication',
                          'labchart' : None}[target]
            try:
                self.app = (win32com.client.gencache.EnsureDispatch(dcom_label))
            except AttributeError:
                print('!DCOM RESET REQUIRED')
            else:
                logger.info('%s trigger init done', self.target)

        def trigger(self, trigger, trigger_letter, comment):
            if trigger is not NO_TRIGGER:
                self.app.WriteEvent(trigger_letter, comment)
                if logger.level >= logging.DEBUG:
                    logger.debug('%s trigger (%s, %s)',
                                 self.target, trigger_letter, comment)
                else:
                    logger.info('%s trigger (%s)', self.target, trigger_letter)
    
    def reset_oxysoft_dcom():
        # Corner case dependencies.
        import os.path as op
        import re
        import sys
        import shutil
        import win32com
        # Remove cache and try again.
        MODULE_LIST = [m.__name__ for m in sys.modules.values()]
        for module in MODULE_LIST:
            if re.match(r'win32com\.gen_py\..+', module):
                del sys.modules[module]
        w32_gen_path = op.abspath(op.join(win32com.__gen_path__, '..'))
        logger.info('Remove w32 cache folder: %s', w32_gen_path)
        shutil.rmtree(w32_gen_path)

        import win32com
        import win32com.client
        (win32com.client.gencache.EnsureDispatch('Oxysoft.OxyApplication'))
        w32gen_fn = op.abspath(op.join(win32com.__gen_path__, '..'))
        if op.exists(w32gen_fn):
            logger.info('Remove w32 cache folder:', w32gen_fn)
            shutil.rmtree(w32gen_fn)

        import win32com.client
        win32com.client.gencache.EnsureDispatch('Oxysoft.OxyApplication')


except ImportError:
    logger.warning('win32 not available, using dummy triggering (print to stdout)')

    class DCOMTrigger:
        def __init__(self, target):
            self.target = target
            logger.info('%s dummy trigger init done', self.target)

        def trigger(self, trigger, trigger_letter, comment):
            if trigger is not NO_TRIGGER:
                if logger.level >= logging.DEBUG:
                    logger.debug('%s dummy trigger (%s, %s)',
                                 self.target, trigger_letter, comment)
                else:
                    logger.info('%s dummy trigger (%s)',
                                self.target, trigger_letter)

    def reset_oxysoft_dcom():
        logger.info('Dummy oxysoft DCOM reset')
