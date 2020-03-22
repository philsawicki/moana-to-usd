#!/usr/bin/env python

"""
Light conversion from JSON to USD.
"""

import json
import os

from moana2usd.converters.base_converter import ContentConverter

from pxr import Gf, Usd, UsdLux
from tqdm import tqdm


class LightConverter(ContentConverter):
    """
    Converter for JSON light definitions into USD Lights.
    """

    def convert(self):
        # type: () -> None
        """
        Start the conversion process.
        """
        self._createLights()

    def getLightStageFilePath(self):
        # type: () -> str
        """
        Return the absolute file path of the USD Light Stage.
        """
        return os.path.join(self.PrimitivesDirectory, '_lights' + self.USDFileExtension)

    def _processLightData(self, lightName, jsonData, lightStage):
        # type: (str, dict, pxr.Usd.Stage) -> None
        """
        Create a USD Light from the given JSON light definition.
        """
        lightColor = jsonData.get('color')
        lightHeight = jsonData.get('height', 100.0)
        lightWidth = jsonData.get('width', 100.0)
        lightTranslationMatrix = jsonData.get('translationMatrix')
        # lightLocation = jsonData.get('location')
        # lightRotation = jsonData.get('rotation')
        lightType = jsonData.get('type')
        lightExposure = jsonData.get('exposure', 1.0)

        lightPrimPath = lightStage.GetDefaultPrim().GetPath().AppendChild(lightName)

        if lightType == 'dome':
            usdLight = UsdLux.DomeLight.Define(lightStage, lightPrimPath)
        elif lightType == 'quad':
            usdLight = UsdLux.RectLight.Define(lightStage, lightPrimPath)
            usdLight.CreateWidthAttr().Set(lightWidth)
            usdLight.CreateHeightAttr().Set(lightHeight)
        else:
            print('Warning: Unknown light type "{lightType}" for "{lightName}".'.format(
                lightType=lightType,
                lightName=lightName))
            return

        usdLight.AddTransformOp().Set(Gf.Matrix4d(*lightTranslationMatrix))
        usdLight.CreateExposureAttr().Set(lightExposure)
        if lightColor is not None:
            usdLight.CreateColorAttr().Set(Gf.Vec3f(*lightColor[:3]))

    def _handleLightFile(self, jsonFilePath, lightStage):
        # type: (str, pxr.Usd.Stage) -> None
        """
        Convert all the lights definitions contained in the given JSON file into
        USD lights.
        """
        with open(jsonFilePath, 'r') as f:
            lightData = json.load(f).items()

        with tqdm(total=len(lightData), desc='Processing lights ', ncols=self.ProgressBarWidth) as progressBar:
            for lightName, jsonData in lightData:
                self._processLightData(lightName, jsonData, lightStage)
                progressBar.update()

    def _createLights(self):
        # type: () -> None
        """
        Create a USD Stage containing USD lights, build from the light
        definitions contained in JSON format in the Moana Island Scene dataset.
        """
        lightJSONFiles = [
            os.path.join(self.SourceDirectoryPath, 'json', 'lights', 'lights.json')
        ]

        # Create USD Stage containing only references to lights:
        lightStage = Usd.Stage.CreateInMemory(load=Usd.Stage.LoadNone)

        # Create a root "/lights" Prim under which all other Prims will be
        # attached:
        lightsRootPrim = lightStage.DefinePrim('/lights')
        lightStage.SetDefaultPrim(lightsRootPrim.GetPrim())

        # Create Light Prims:
        for lightJSONFile in lightJSONFiles:
            self._handleLightFile(lightJSONFile, lightStage)

        # Commit the changes and save the Light Stage:
        lightStagePath = self.getLightStageFilePath()
        lightStage.GetRootLayer().Export(lightStagePath, comment='')
