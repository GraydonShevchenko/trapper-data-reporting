# -------------------------------------------------------------------------------
# Name:        environment
# Purpose:
#
# Author:      gshevche
#
# Created:     05/02/2020
# Copyright:   (c) gshevche 2020
# Licence:     <your licence>
# -------------------------------------------------------------------------------

import os
import sys
import logging

from datetime import datetime as dt


class Environment:
    """
    ------------------------------------------------------------------------------------------------------------
        CLASS: Contains general environment functions and processes that can be used in python scripts
    ------------------------------------------------------------------------------------------------------------
    """

    def __init__(self):
        pass

    @staticmethod
    def setup_logger(args):
        """
        ------------------------------------------------------------------------------------------------------------
            FUNCTION: Set up the logging object for message output

            Parameters:
                args: system arguments

            Return: logger object
        ------------------------------------------------------------------------------------------------------------
        """
        log_name = 'main_logger'
        logger = logging.getLogger(log_name)
        logger.handlers = []

        log_fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_file_base_name = os.path.basename(sys.argv[0])
        log_file_extension = 'txt'
        timestamp = dt.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file = 'script_log.txt'

        logger.setLevel(args.log_level)

        sh = logging.StreamHandler()
        sh.setLevel(args.log_level)
        sh.setFormatter(log_fmt)
        logger.addHandler(sh)

        if args.log_dir:
            try:
                os.makedirs(args.log_dir)
            except OSError:
                pass

        fh = logging.FileHandler(os.path.join('.', log_file))
        fh.setLevel(args.log_level)
        fh.setFormatter(log_fmt)
        logger.addHandler(fh)

        return logger
