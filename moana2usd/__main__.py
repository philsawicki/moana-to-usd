#!/usr/bin/env python

"""
Convert Disney's Moana Island Scene to USD.
"""

from __future__ import print_function

import argparse
import os

from pxr import Sdf

from moana2usd.converters.scene_converter import SceneConverter


__author__ = r'Philippe Sawicki'
__license__ = r'MIT'
__status__ = r'Development'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert the Moana Island scene to USD.')
    parser.add_argument(
        '--source-dir',
        help='Directory where the Moana Island scene is located.')
    parser.add_argument(
        '--dest-dir',
        help='Output directory where the USD data will be written.')
    parser.add_argument(
        '--format',
        choices=Sdf.FileFormat.FindAllFileFormatExtensions(),
        default=Sdf.FileFormat.FindById('usdc').GetFileExtensions()[0],
        help='File format to output data to.')
    parser.add_argument(
        '--load-textures',
        action='store_true',
        help='Create USD assets with Ptex textures.')
    parser.add_argument(
        '--omit-small-instances',
        action='store_false',
        help='Omit instantiation of small (or numerous) instances.')

    args = parser.parse_args()


    DESTINATION_DIRECTORY_PATH = os.path.abspath(args.dest_dir)
    SOURCE_DIRECTORY_PATH = os.path.abspath(args.source_dir)
    if not os.path.isdir(SOURCE_DIRECTORY_PATH):
        message = 'Could not find directory with Moana Island scene at "{}".'.format(SOURCE_DIRECTORY_PATH)
        raise Exception(message)


    moanaIslandConverter = SceneConverter(
        fileFormat=args.format,
        sourceDirectoryPath=SOURCE_DIRECTORY_PATH,
        destinationDirectoryPath=DESTINATION_DIRECTORY_PATH,
        loadTextures=args.load_textures,
        omitSmallInstances=args.omit_small_instances)
    moanaIslandConverter.convert()
