#!/usr/bin/env python

"""
Camera conversion from JSON to USD.
"""

import os
import json
import math

from moana2usd.converters.base_converter import ContentConverter

from pxr import Gf, Usd, UsdGeom
from tqdm import tqdm



def crossProduct(a, b):
    # type: (List[float], List[float]) -> List[float]
    """
    Compute the cross product between the 2 given vectors.
    """
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    ]

def dotProduct(a, b):
    # type: (List[float], List[float]) -> float
    """
    Compute the dot product of the 2 given vectors.
    """
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

def normalize(a):
    # type: (List[float]) -> float
    """
    Normalize the given vector.
    """
    vectorLength = math.sqrt(dotProduct(a, a))
    return [
        a[0] / vectorLength,
        a[1] / vectorLength,
        a[2] / vectorLength
    ]


class CameraConverter(ContentConverter):
    """
    Converter for JSON camera definitions into USD Cameras.
    """

    def convert(self):
        # type: () -> None
        """
        Start the conversion process.
        """
        self._createCameras()

    def getCameraStageFilePath(self):
        # type: () -> str
        """
        Return the absolute file path of the USD Camera Stage.
        """
        return os.path.join(self.PrimitivesDirectory, '_cameras' + self.USDFileExtension)

    def _processCameraData(self, jsonData, cameraStage):
        # type: (dict, pxr.Usd.Stage) -> None
        """
        Create a USD Camera in the given USD Stage from the given JSON camera
        definition.
        """
        cameraFOV = jsonData.get('fov',)
        cameraName = jsonData.get('name')
        cameraEyePosition = jsonData.get('eye')
        cameraFocalLength = jsonData.get('focalLength')
        # cameraCenterOfInterest = jsonData.get('centerOfInterest')
        # cameraLensRadius = jsonData.get('lensRadius')
        cameraUpVector = normalize(jsonData.get('up'))
        # cameraScreenWindow = jsonData.get('screenwindow')
        cameraRatio = jsonData.get('ratio')
        cameraLook = normalize(jsonData.get('look'))


        # Look at conversion:
        forwardVector = normalize([
            cameraEyePosition[0] - cameraLook[0],
            cameraEyePosition[1] - cameraLook[1],
            cameraEyePosition[2] - cameraLook[2]
        ])
        sideVector = crossProduct(cameraUpVector, forwardVector)
        transformMatrix = [
            sideVector[0],        sideVector[1],        sideVector[2],        0,
            cameraUpVector[0],    cameraUpVector[1],    cameraUpVector[2],    0,
            forwardVector[0],     forwardVector[1],     forwardVector[2],     0,
            cameraEyePosition[0], cameraEyePosition[1], cameraEyePosition[2], 1
        ]


        cameraPrimPath = cameraStage.GetDefaultPrim().GetPath().AppendChild(cameraName)
        usdCamera = UsdGeom.Camera.Define(cameraStage, cameraPrimPath)
        usdCamera.MakeMatrixXform().Set(Gf.Matrix4d(*transformMatrix))
        usdCamera.GetProjectionAttr().Set(UsdGeom.Tokens.perspective)
        if cameraFocalLength is not None:
            usdCamera.GetFocalLengthAttr().Set(cameraFocalLength)

        if cameraRatio is not None and cameraFOV is not None:
            camera = usdCamera.GetCamera(cameraStage.GetStartTimeCode())
            camera.SetPerspectiveFromAspectRatioAndFieldOfView(
                aspectRatio=cameraRatio,
                fieldOfView=cameraFOV,
                direction=Gf.Camera.FOVHorizontal)
            usdCamera.SetFromCamera(camera)

    def _handleCameraFile(self, jsonFilePath, cameraStage):
        # type: (str, pxr.Usd.Stage) -> None
        """
        Create USD Cameras in the given USD Stage from the given JSON camera
        definition file.
        """
        with open(jsonFilePath, 'r') as f:
            jsonData = json.load(f)
        self._processCameraData(jsonData, cameraStage)

    def _createCameras(self):
        # type: () -> None
        """
        Create a USD Stage with USD Cameras from the JSON camera definitions
        files contained in the Moana Island Scene dataset.
        """
        cameraJSONFiles = [
            os.path.join(self.SourceDirectoryPath, 'json', 'cameras', 'beachCam.json'),
            os.path.join(self.SourceDirectoryPath, 'json', 'cameras', 'birdseyeCam.json'),
            os.path.join(self.SourceDirectoryPath, 'json', 'cameras', 'dunesACam.json'),
            os.path.join(self.SourceDirectoryPath, 'json', 'cameras', 'grassCam.json'),
            os.path.join(self.SourceDirectoryPath, 'json', 'cameras', 'palmsCam.json'),
            os.path.join(self.SourceDirectoryPath, 'json', 'cameras', 'rootsCam.json'),
            os.path.join(self.SourceDirectoryPath, 'json', 'cameras', 'shotCam.json')
        ]

        # Create USD Stage containing only references to cameras, along with a
        # root "/cameras" Prim under which all other Prims will be attached:
        cameraStage = Usd.Stage.CreateInMemory(load=Usd.Stage.LoadNone)
        camerasRootPrim = cameraStage.DefinePrim('/cameras')
        cameraStage.SetDefaultPrim(camerasRootPrim.GetPrim())

        # Create Camera Prims:
        with tqdm(total=len(cameraJSONFiles), desc='Processing cameras', ncols=self.ProgressBarWidth) as progressBar:
            for cameraJSONFile in cameraJSONFiles:
                self._handleCameraFile(cameraJSONFile, cameraStage)
                progressBar.update()

        # Commit the changes and save the Camera Stage:
        cameraStagePath = self.getCameraStageFilePath()
        cameraStage.GetRootLayer().Export(cameraStagePath, comment='')
