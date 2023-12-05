import sys, os
import pandas as pd
import boto3
from arcgis.gis import GIS
from copy import deepcopy
from datetime import datetime, timedelta
from argparse import ArgumentParser
import logging

from util.environment import Environment

import trap_config


def run_app():
    ago_user, ago_pass, obj_store_user, obj_store_secret, obj_store_host, logger = get_input_parameters()
    report = TrapReport(ago_user=ago_user, ago_pass=ago_pass, obj_store_user=obj_store_user, 
                       obj_store_secret=obj_store_secret, obj_store_host=obj_store_host, logger=logger)
    
    report.list_contents()

    del report


def get_input_parameters():
    """
    Function:
        Sets up parameters and the logger object
    Returns:
        tuple: user entered parameters required for tool execution
    """
    try:
        parser = ArgumentParser(description='This script is used to update the Traps AGOL feature layer based on information entered in the trap check table')
        # parser.add_argument('ago_user', nargs='?', type=str, help='AGOL Username')
        # parser.add_argument('ago_pass', nargs='?', type=str, help='AGOL Password')
        parser.add_argument('--log_level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                            help='Log level')
        parser.add_argument('--log_dir', help='Path to log directory')

        args = parser.parse_args()
        try:
            ago_user = trap_config.AGO_USER
            ago_pass = trap_config.AGO_PASS
            obj_store_user = trap_config.OBJ_STORE_USER
            obj_store_secret = trap_config.OBJ_STORE_SECRET
            obj_store_host = trap_config.OBJ_STORE_HOST
        except:
            ago_user = os.environ['AGO_USER']
            ago_pass = os.environ['AGO_PASS']
            obj_store_user = os.environ['OBJ_STORE_USER']
            obj_store_secret = os.environ['OBJ_STORE_SECRET']
            obj_store_host = os.environ['OBJ_STORE_HOST']

        logger = Environment.setup_logger(args)

        return ago_user, ago_pass, obj_store_user, obj_store_secret, obj_store_host, logger

    except Exception as e:
        logging.error('Unexpected exception. Program terminating: {}'.format(e.message))
        raise Exception('Errors exist')


class TrapReport:
    def __init__(self, ago_user, ago_pass, obj_store_user, obj_store_secret, obj_store_host, logger) -> None:
        self.ago_user = ago_user
        self.ago_pass = ago_pass
        self.obj_store_user = obj_store_user
        self.obj_store_secret = obj_store_secret
        self.obj_store_host = obj_store_host
        self.logger = logger

        self.portal_url = trap_config.MAPHUB
        self.ago_traps = trap_config.TRAPS
        self.ago_fisher = trap_config.FISHER

        self.boto_bucket = 'trapper_data_collection'

        self.logger.info('Connecting to map hub')
        self.gis = GIS(url=self.portal_url, username=self.ago_user, password=self.ago_pass, expiration=9999)
        self.logger.info('Connection successful')

        self.logger.info('Connecting to object storage')
        self.boto_session = boto3.session.Session()
        self.boto_client = self.boto_session.client(service_name='s3', 
                                                    aws_access_key_id=self.obj_store_user, 
                                                    aws_secret_access_key=self.obj_store_secret, 
                                                    endpoint_url=f'https://{self.obj_store_host}')

    def __del__(self) -> None:
        self.logger.info('Disconnecting from maphub')
        del self.gis
        self.logger.info('Closing object storage connection')
        self.boto_client.close()
        del self.boto_client

    def list_contents(self) -> list:
        obj_bucket = self.boto_client.Bucket(self.boto_bucket)
        lst_objects = obj_bucket.objects.all()
        self.logger.info(lst_objects)
        return lst_objects

    
if __name__ == '__main__':
    run_app()
