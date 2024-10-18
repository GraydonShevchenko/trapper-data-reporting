import sys, os
import pandas as pd
from arcgis.gis import GIS
from copy import deepcopy
from datetime import datetime, timedelta
from argparse import ArgumentParser
import logging

from util.environment import Environment

import trap_config


def run_app():
    ago_user, ago_pass, logger = get_input_parameters()
    traps = Traps(ago_user=ago_user, ago_pass=ago_pass, logger=logger)
    traps.shift_traps()
    traps.update_trap_status()
    traps.update_attachments()

    del traps


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
        except:
            ago_user = os.environ['AGO_USER']
            ago_pass = os.environ['AGO_PASS']


        logger = Environment.setup_logger(args)

        return ago_user, ago_pass, logger

    except Exception as e:
        logging.error('Unexpected exception. Program terminating: {}'.format(e.message))
        raise Exception('Errors exist')


class Traps:
    def __init__(self, ago_user, ago_pass, logger) -> None:
        self.ago_user = ago_user
        self.ago_pass = ago_pass
        self.logger = logger

        self.portal_url = trap_config.MAPHUB
        self.ago_traps = trap_config.TRAPS
        self.ago_mesogrid = trap_config.MESO_GRID
        self.ago_fisher = trap_config.FISHER

        self.logger.info('Connecting to map hub')
        self.gis = GIS(url=self.portal_url, username=self.ago_user, password=self.ago_pass, expiration=9999)
        self.logger.info('Connection successful')

    def __del__(self) -> None:
        self.logger.info('Disconnecting from maphub')
        del self.gis

    def shift_traps(self):
        """
        Function:
            Shifts the trap points in the AGOL feature layer to the centre of the meso grid if the user indicated to not include coordinates.
        Returns:
            None
        """
        self.logger.info('Shifting any traps that indicated the coordinates should not be included')
        traps_item = self.gis.content.get(self.ago_traps)
        traps_flayer = traps_item.layers[0]
        traps_fset = traps_flayer.query(where='INCLUDE_COORDINATES=\'NO\'')
        if len(traps_fset) > 0:
            self.logger.info(f'Found {len(traps_fset)} trap(s) that did not include coordinates')
            grid_list = traps_fset.sdf['MESO_GRID_ID'].tolist()
            str_list = ','.join([f'\'{a}\'' for a in grid_list])
            sql = f'MesoCell IN ({str_list})'
            mesogrid_item = self.gis.content.get(self.ago_mesogrid)
            mesogrid_flayer = mesogrid_item.layers[0]
            mesogrid_fset = mesogrid_flayer.query(where=sql)
            overlap_rows = pd.merge(left = traps_fset.sdf, right = mesogrid_fset.sdf, how='inner',
                               left_on = 'MESO_GRID_ID', right_on='MesoCell')

            features_for_update = [] #list containing corrected features
            all_features = traps_fset.features
            traps_fset.spatial_reference
            self.logger.info('Updating geometry for traps')
            for trap_set in overlap_rows['SET_UNIQUE_ID']:
                # get the feature to be updated
                original_feature = [f for f in all_features if f.attributes['SET_UNIQUE_ID'] == trap_set][0]
                mesogrid_id = original_feature.attributes['MESO_GRID_ID']
                feature_to_be_updated = deepcopy(original_feature)

                matching_row = mesogrid_fset.sdf.where(mesogrid_fset.sdf.MesoCell == mesogrid_id).dropna()

                input_geometry = {'y':float(matching_row['CENTROID_Y']),
                                   'x': float(matching_row['CENTROID_X'])}
                feature_to_be_updated.geometry = input_geometry

                features_for_update.append(feature_to_be_updated)

            if features_for_update:
                self.logger.info(f'Updating {len(features_for_update)} trap(s)')
                traps_flayer.edit_features(updates=features_for_update)


    def update_trap_status(self) -> None:
        """
        Function:
            Updates the trap status field in the traps feature layer on AGOL based on the trap status in the most recent trap check record
        Returns:
            None
        """
        self.logger.info('Updating traps layer with most recent trap check status')
        traps_item = self.gis.content.get(self.ago_traps)
        traps_flayer = traps_item.layers[0]
        traps_fset = traps_flayer.query()
        features_for_update = [] #list containing corrected features
        all_features = traps_fset.features
        tbl_trap_check = traps_item.tables[0]


        for trap in traps_fset:
            unique_id = trap.attributes['SET_UNIQUE_ID']
            trap_status = trap.attributes['TRAP_STATUS']
            trap_check_subset = tbl_trap_check.query(where=f'SET_UNIQUE_ID=\'{unique_id}\'')
            if len(trap_check_subset) == 0:
                continue
            lst_check_nums = trap_check_subset.sdf['TRAP_CHECK_NUMBER'].tolist()

            latest_check = trap_check_subset.sdf.loc[trap_check_subset.sdf['TRAP_CHECK_NUMBER'] == lst_check_nums[-1]]
            check_status = latest_check.iloc[0]['TRAP_STATUS']
            if trap_status != check_status:
                original_feature = [f for f in all_features if f.attributes['SET_UNIQUE_ID'] == unique_id][0]
                feature_to_be_updated = deepcopy(original_feature)
                feature_to_be_updated.attributes['TRAP_STATUS'] = check_status
                features_for_update.append(feature_to_be_updated)
        if features_for_update:
            self.logger.info(f'Updating {len(features_for_update)} trap(s)')
            traps_flayer.edit_features(updates=features_for_update)


    def update_attachments(self) -> None:
        """
        Function:
            Master function to rename attachments for all required layers in arcgis online
        Returns:
            None
        """
        self.rename_attachments(ago_layer=self.ago_traps, layer_name='traps', fld_unique_id='SET_UNIQUE_ID',
                                fld_picture='PICTURE', photo_prefix='trapsetup')
        
        self.rename_attachments(ago_layer=self.ago_traps, layer_name='trap checks', fld_unique_id='SET_UNIQUE_ID', fld_picture='PICTURE', photo_prefix='trapcheck')

        self.rename_attachments(ago_layer=self.ago_fisher, layer_name='fisher', fld_unique_id='OBJECTID', fld_picture='PICTURE', photo_prefix='fisher')

        

    def rename_attachments(self, ago_layer, layer_name, fld_unique_id, fld_picture, photo_prefix) -> None:
        """
        Function:
            Function used to rename attachments in arcgis online. It downloads each attachment, renames it according to the photo prefix, and replaces the pre-existing photo in the attachments table.
        Returns:
            None
        """
        self.logger.info(f'Renaming photos on the {layer_name} layer')
        ago_item = self.gis.content.get(ago_layer)
        if layer_name != 'trap checks':
            ago_flayer = ago_item.layers[0]
        else:
            ago_flayer = ago_item.tables[0]

        ago_fset = ago_flayer.query()
        all_features = ago_fset.features
        if len(all_features) == 0:
            return
        features_for_update = []
        lst_oids = ago_fset.sdf['OBJECTID'].tolist()
        update_count = 0

        for oid in lst_oids:
            lst_attachments = ago_flayer.attachments.get_list(oid=oid)
            self.logger.debug(lst_attachments)
            if lst_attachments:
                original_feature = [f for f in all_features if f.attributes['OBJECTID'] == oid][0]
                if layer_name == 'trap checks':
                    unique_id = f'{original_feature.attributes[fld_unique_id].split("_")[0]}_' \
                                f'{original_feature.attributes["TRAP_CHECK_NUMBER"]}'
                elif layer_name == 'fisher':
                    unique_id = f'{original_feature.attributes["OBSERVATION_TYPE"]}_' \
                                f'{original_feature.attributes["OBJECTID"]}'
                else:
                    unique_id = original_feature.attributes[fld_unique_id]
                attach_num = 1
                lst_photo_names = []
                try:
                    lst_pictures = original_feature.attributes[fld_picture].split(',')
                except:
                    lst_pictures = []
                self.logger.debug(lst_pictures)
                bl_update = False
                for attach in lst_attachments:
                    self.logger.debug(attach['name'])
                    if attach['name'].startswith(photo_prefix) and attach['name'] in lst_pictures:
                        if attach_num > 5:
                            lst_photo_names = [f'{attach_num} photos taken with photo prefix {unique_id}']
                            self.logger.info(lst_photo_names)
                        else:
                            lst_photo_names.append(attach['name'])
                            continue
                    attach_name = attach['name']
                    file_type = attach_name.split('.')[-1]
                    if file_type in ['avi', 'mp4']:
                        type_name = 'video'
                    else:
                        type_name = 'photo'
                    new_file_name = f'{photo_prefix}_{unique_id.lower()}_{type_name}{attach_num}.{file_type}'
                    if attach_name != new_file_name:
                        self.logger.info(f'Renaming {attach_name} to {new_file_name}')
                        attach_id = attach['id']
                        attach_file = ago_flayer.attachments.download(oid=oid, attachment_id=attach_id)[0]
                        new_attach_file = os.path.join(os.path.dirname(attach_file), new_file_name)
                        os.rename(attach_file, new_attach_file)
                        try:
                            ago_flayer.attachments.update(oid=oid, attachment_id=attach_id, file_path=new_attach_file)
                        except:
                            self.logger.warning('File too big to update, uploading new file and deleting old')
                            ago_flayer.attachments.add(oid=oid, file_path=new_attach_file)
                            ago_flayer.attachments.delete(oid=oid, attachment_id=attach_id)
                            lst_photo_names.append(new_file_name)
                        bl_update = True    
                    attach_num += 1
                    
                    
                if bl_update:
                    update_count += 1
                    feature_to_be_updated = deepcopy(original_feature)
                    feature_to_be_updated.attributes[fld_picture] = ','.join(lst_photo_names)
                    if layer_name == 'fisher':
                        feature_to_be_updated.attributes['EMAIL_MESSAGE'] = ''
                    features_for_update.append(feature_to_be_updated)
        if features_for_update:
            self.logger.info(f'Updating photo names for {update_count} {layer_name}')
            ago_flayer.edit_features(updates=features_for_update)

if __name__ == '__main__':
    run_app()
