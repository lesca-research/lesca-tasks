from optparse import OptionParser
from .version import __version__

def default_arg_parser(usage, description):
    parser = OptionParser(usage=usage, description=description,
                          version='%%prog %s' % __version__)
    
    parser.add_option('-v', '--verbose', dest='verbose',
                      metavar='VERBOSELEVEL',
                      type='int', default=0,
                      help='Verbose level: '\
                           '0 (NOTSET: quiet, default), '\
                           '50 (CRITICAL), ' \
                           '40 (ERROR), ' \
                           '30 (WARNING), '\
                           '20 (INFO), '\
                           '10 (DEBUG)')

    return parser

def default_task_arg_parser(usage, description):
    parser = default_arg_parser(usage, description)

    parser.add_option('-l', '--language', dest='language',
                      metavar='STR', default='f', choices=['e', 'f'],
                      help='f: French, e: English')
    
    parser.add_option('-u', '--unit-tests', dest='unit_tests',
                      action='store_true', default=False,
                      help='Run unit tests only')

    parser.add_option('-t', '--test', dest='test',
                      action='store_true', default=False,
                      help='Run in test mode (windowed)')    

    return parser
