import sys
import logging
from optparse import OptionParser
import json

from PyQt5 import QtWidgets

import porch

logger = logging.getLogger('porch')

def main():

    min_args = 1
    max_args = 1

    usage = 'usage: %prog [options] CFG_FILE]'
    description = 'Run experiment helper.'

    parser = OptionParser(usage=usage, description=description)

    parser.add_option('-v', '--verbose', dest='verbose',
                      metavar='VERBOSELEVEL',
                      type='int', default=0,
                      help='Amount of verbose: '\
                           '0 (NOTSET: quiet, default), '\
                           '50 (CRITICAL), ' \
                           '40 (ERROR), ' \
                           '30 (WARNING), '\
                           '20 (INFO), '\
                           '10 (DEBUG)')

    (options, args) = parser.parse_args()
    logger.setLevel(options.verbose)

    nba = len(args)
    if nba < min_args or (max_args >= 0 and nba > max_args):
        parser.print_help()
        return 1

    fn = args[0] if nba > 0 else None

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')
    with open(sys.argv[1]) as fin:
        configuration = json.load(fin)
    main_window = porch.TaskHelperWindow(configuration)
    main_window.show()
    main_window.flush_right()
    sys.exit(app.exec_())
