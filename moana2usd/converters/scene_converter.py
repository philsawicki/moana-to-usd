#!/usr/bin/env python

"""
Moana Island Scene conversion from OBJ and JSON to USD.
"""

import os

from moana2usd.converters.base_converter import ContentConverter

from pxr import Gf, Sdf, Usd, UsdLux
from tqdm import tqdm

from asset_converter import AssetConverter
from camera_converter import CameraConverter
from element_converter import ElementConverter
from light_converter import LightConverter


class SceneConverter(ContentConverter):
    """
    Converter for the Moana Island Scene into USD.
    """

    def __init__(self, fileFormat, sourceDirectoryPath, destinationDirectoryPath, loadTextures=True, omitSmallInstances=False):
        # type: (str, str, str, boolean, boolean) -> SceneConverter
        """
        Initialize the converter using the provided USD file format, dataset
        source directory path and destination folder path.
        """
        super(SceneConverter, self).__init__(fileFormat, sourceDirectoryPath, destinationDirectoryPath)

        self._loadTextures = loadTextures

        self._cameraConverter = CameraConverter(
            fileFormat=fileFormat,
            sourceDirectoryPath=sourceDirectoryPath,
            destinationDirectoryPath=destinationDirectoryPath)
        self._lightConverter = LightConverter(
            fileFormat=fileFormat,
            sourceDirectoryPath=sourceDirectoryPath,
            destinationDirectoryPath=destinationDirectoryPath)
        self._assetConverter = AssetConverter(
            fileFormat=fileFormat,
            sourceDirectoryPath=sourceDirectoryPath,
            destinationDirectoryPath=destinationDirectoryPath,
            loadTextures=loadTextures)
        self._elementConverter = ElementConverter(
            fileFormat=fileFormat,
            sourceDirectoryPath=sourceDirectoryPath,
            destinationDirectoryPath=destinationDirectoryPath,
            omitSmallInstances=omitSmallInstances)

    def convert(self):
        # type: () -> None
        """
        Start the scene conversion process.
        """
        if not os.path.exists(self.DestinationDirectoryPath):
            os.makedirs(self.DestinationDirectoryPath)

            if not os.path.exists(self.PrimitivesDirectory):
                os.makedirs(self.PrimitivesDirectory)

        print('Translating JSON cameras into USD Cameras...')
        self._cameraConverter.convert()
        print('\nTranslating JSON lights into USD Lights...')
        self._lightConverter.convert()
        print('\nTranslating OBJ assets into USD assets. This may take some time...')
        self._assetConverter.convert()
        print('\nInstantiating USD assets. This may take some time...')
        self._elementConverter.convert()

        print('\nGenerating final composition USD stage...')
        self._createSceneStage()

        print('Done!')

    def _createSceneStage(self):
        # type: () -> None
        """
        Create the Main USD Stage that references all other Elements and their
        instances.
        """
        subStageFilePaths = [
            ('cameras', self._cameraConverter.getCameraStageFilePath()),
            ('lights', self._lightConverter.getLightStageFilePath()),
            ('isBayCedarA1', self._elementConverter.getElementStageFilePath('isBayCedarA1')),
            ('isBeach', self._elementConverter.getElementStageFilePath('isBeach')),
            ('isCoastline', self._elementConverter.getElementStageFilePath('isCoastline')),
            ('isCoral', self._elementConverter.getElementStageFilePath('isCoral')),
            ('isDunesA', self._elementConverter.getElementStageFilePath('isDunesA')),
            ('isDunesB', self._elementConverter.getElementStageFilePath('isDunesB')),
            ('isGardeniaA', self._elementConverter.getElementStageFilePath('isGardeniaA')),
            ('isHibiscus', self._elementConverter.getElementStageFilePath('isHibiscus')),
            ('isHibiscusYoung', self._elementConverter.getElementStageFilePath('isHibiscusYoung')),
            ('isIronwoodA1', self._elementConverter.getElementStageFilePath('isIronwoodA1')),
            ('isIronwoodB', self._elementConverter.getElementStageFilePath('isIronwoodB')),
            ('isKava', self._elementConverter.getElementStageFilePath('isKava')),
            ('isLavaRocks', self._elementConverter.getElementStageFilePath('isLavaRocks')),
            ('isMountainA', self._elementConverter.getElementStageFilePath('isMountainA')),
            ('isMountainB', self._elementConverter.getElementStageFilePath('isMountainB')),
            ('isNaupakaA', self._elementConverter.getElementStageFilePath('isNaupakaA')),
            ('isPalmDead', self._elementConverter.getElementStageFilePath('isPalmDead')),
            ('isPalmRig', self._elementConverter.getElementStageFilePath('isPalmRig')),
            ('isPandanusA', self._elementConverter.getElementStageFilePath('isPandanusA')),
            ('osOcean', self._elementConverter.getElementStageFilePath('osOcean'))
        ]

        # List of Elements/Stages to set as "active" by default.
        #
        # NOTE: This is only to facilitate fast previews under development.
        activeElementNames = [
            'cameras',
            # 'lights',
            # 'isBayCedarA1',
            'isBeach',
            'isCoastline',
            # 'isCoral',
            'isDunesA',
            'isDunesB',
            'isGardeniaA',
            'isHibiscus',
            'isHibiscusYoung',
            'isIronwoodA1',
            # 'isIronwoodB',
            'isKava',
            'isLavaRocks',
            'isMountainA',
            # 'isMountainB',
            'isNaupakaA',
            'isPalmDead',
            'isPalmRig',
            'isPandanusA',
            'osOcean'
        ]


        layer = Sdf.Layer.CreateAnonymous(self.USDFileExtension)

        moanaIslandPrimSpecPath = '/MoanaIsland'
        moanaIslandPrimSpec = Sdf.CreatePrimInLayer(layer, moanaIslandPrimSpecPath)
        moanaIslandPrimSpec.specifier = Sdf.SpecifierDef
        layer.defaultPrim = 'MoanaIsland'

        with tqdm(total=len(subStageFilePaths), desc='Assembling USD stage', ncols=self.ProgressBarWidth) as progressBar:
            for elementName, elementStageFilePath in subStageFilePaths:
                relativeElementStagePath = os.path.relpath(elementStageFilePath, self.DestinationDirectoryPath)

                elementPrimSpecPath = moanaIslandPrimSpecPath + '/' + elementName
                elementPrimSpec = Sdf.CreatePrimInLayer(layer, elementPrimSpecPath)
                elementPrimSpec.referenceList.Prepend( Sdf.Reference(relativeElementStagePath.replace('\\', '/')) )

                if elementName not in activeElementNames:
                    elementPrimSpec.active = False

                progressBar.update()

        # Commit the changes and save the scene Stage:
        sceneStageFilePath = os.path.join(self.DestinationDirectoryPath, 'MoanaIsland' + self.USDFileExtension)
        layer.Export(sceneStageFilePath, comment='')
