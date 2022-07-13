import sys
import logging

from lesca_tasks import trigger, default_arg_parser

logger = logging.getLogger('lesca_tasks')

def main():
    min_args = 0
    max_args = 1

    usage = 'usage: %prog [options] oxysoft|labchart'
    description = 'Send a test trigger to either oxysoft or labchart using DCOM'
    parser = default_arg_parser(usage, description)

    (options, args) = parser.parse_args()
    logger.setLevel(options.verbose)

    nba = len(args)
    if nba < min_args or (max_args >= 0 and nba > max_args):
        parser.print_help()
        sys.exit(1)

    target = args[0]
    if target not in ['oxysoft', 'labchart']:
        parser.print_help()
        sys.exit(1)

    trigger.DCOMTrigger(target).trigger(0, 'T', 'Test')
