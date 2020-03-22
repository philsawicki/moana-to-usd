#!/usr/bin/env python

"""
Element instancing from JSON to USD.
"""

import json
import os

from moana2usd.converters.base_converter import ContentConverter

from pxr import Gf, Sdf, Usd, UsdGeom, UsdLux
from tqdm import tqdm


class ElementConverter(ContentConverter):
    """
    Converter for JSON Elements into USD Stages.
    """

    def __init__(self, fileFormat, sourceDirectoryPath, destinationDirectoryPath, omitSmallInstances=False):
        # type: (str, str, str, boolean) -> ElementConverter
        """
        Initialize the converter using the provided USD file format, dataset
        source directory path and destination folder path.
        """
        super(ElementConverter, self).__init__(fileFormat, sourceDirectoryPath, destinationDirectoryPath)

        self._omitSmallInstances = omitSmallInstances

        self._ITEM_PB_INDEX = 2
        self._SUBINSTANCE_PB_INDEX = 1
        self._ELEMENT_PB_INDEX = 0

    def convert(self):
        # type: () -> None
        """
        Start the conversion process.
        """
        self._createElements()

    def getElementStageFilePath(self, elementName):
        # type: (str) -> str
        """
        Return the absolute file path of the USD Stage for the given Element.
        """
        return os.path.join(
            self.PrimitivesDirectory,
            '_element_' + elementName + self.USDFileExtension)

    def _getAssetFilePathFromOBJFilePath(self, assetOBJPath):
        # type: (str) -> str
        """
        Return the absolute file path of the USD Stage for the given OBJ asset.
        """
        assetOBJFileName = os.path.basename(assetOBJPath)
        baseName = os.path.splitext(assetOBJFileName)[0]
        return os.path.join(
            self.PrimitivesDirectory,
            baseName + self.USDFileExtension)

    def _getAssetSubInstanceStageFilePath(self, jsonFilename):
        # type: (str) -> str
        """
        Return the absolute file path of the USD Stage containing the
        subinstances for the given Element JSON defintion.
        """
        return os.path.join(
            self.PrimitivesDirectory,
            '_instances_' + self._getFileBasename(jsonFilename) + self.USDFileExtension)

    def _getFileBasename(self, filename):
        # type: (str) -> str
        """
        Return the name of the given file (without extension).
        """
        return os.path.basename(filename).rsplit('.')[0]

    def _subInstanceIsTooSmallToInstance(self, subInstanceName):
        # type: (str) -> boolean
        """
        Check if the given sub-instance name is "too small" to be instantiated,
        which would slow down rendering performance due to the large amount of
        content to load and render.
        """
        return subInstanceName in ['xgGroundCover', 'xgPalmDebris', 'xgFlutes', 'xgDebris']

    def _parseInstanceJSONFile(self, jsonFilename, subInstanceStageFilePath):
        # type: (str, str) -> None
        """
        Create USD Prim instances from the given Element JSON file.
        """
        with open(jsonFilename, 'r') as f:
            jsonData = json.load(f)


        layer = Sdf.Layer.CreateAnonymous(self.USDFileExtension)

        # Leverage the SDF API instead of the USD API in order to batch-create
        # Prims. This avoids fanning out change notifications, which results in
        # O(n2) performance and becomes *slow* when creating a large number of
        # instances -- which is the case here (sometimes upwards of a million
        # instances).
        with Sdf.ChangeBlock():
            instancersPrimSpecPath = '/Instancers'
            instancersPrimSpec = Sdf.CreatePrimInLayer(layer, instancersPrimSpecPath)
            instancersPrimSpec.specifier = Sdf.SpecifierDef
            layer.defaultPrim = 'Instancers'

            for name, instances in jsonData.items():
                pointInstancerPrimSpecPath = instancersPrimSpecPath + '/' + self._getFileBasename(name)
                pointInstancerPrimSpec = Sdf.CreatePrimInLayer(layer, pointInstancerPrimSpecPath)
                pointInstancerPrimSpec.specifier = Sdf.SpecifierDef
                pointInstancerPrimSpec.typeName = 'PointInstancer'

                positionsBuffer = []
                orientationsBuffer = []
                for instanceName, instanceTransform in instances.items():
                    transformMatrix = Gf.Matrix4d(*instanceTransform)
                    positionsBuffer.append(transformMatrix.ExtractTranslation())

                    quaternion = transformMatrix.ExtractRotation().GetQuaternion().GetNormalized()
                    imaginaryComponents = quaternion.GetImaginary()
                    orientationsBuffer.append(
                        Gf.Quath(
                            quaternion.GetReal(),
                            Gf.Vec3h(imaginaryComponents[0], imaginaryComponents[1], imaginaryComponents[2])
                        )
                    )

                positionsAttribute = Sdf.AttributeSpec(
                    pointInstancerPrimSpec,
                    'positions',
                    Sdf.ValueTypeNames.Vector3fArray)
                positionsAttribute.default = positionsBuffer

                orientationsAttribute = Sdf.AttributeSpec(
                    pointInstancerPrimSpec,
                    'orientations',
                    Sdf.ValueTypeNames.QuathArray)
                orientationsAttribute.default = orientationsBuffer

                protoIndicesAttribute = Sdf.AttributeSpec(
                    pointInstancerPrimSpec,
                    'protoIndices',
                    Sdf.ValueTypeNames.IntArray)
                protoIndicesAttribute.default = [0] * len(instances.items())

                meshReferencePrimSpecPath = pointInstancerPrimSpecPath + '/mesh'
                meshReferencePrimSpec = Sdf.CreatePrimInLayer(layer, meshReferencePrimSpecPath)
                meshReferencePrimSpec.specifier = Sdf.SpecifierDef
                meshReferencePrimSpec.typeName = 'Mesh'
                relativeAssetFilePath = './' + os.path.relpath(
                    self._getAssetFilePathFromOBJFilePath(name),
                    self.PrimitivesDirectory
                ).replace('\\', '/')
                meshReferencePrimSpec.referenceList.Prepend( Sdf.Reference(relativeAssetFilePath) )

                relationshipSpec = Sdf.RelationshipSpec(
                    pointInstancerPrimSpec,
                    'prototypes',
                    custom=False)
                relationshipSpec.targetPathList.explicitItems.append(meshReferencePrimSpecPath)

        layer.Export(subInstanceStageFilePath, comment='')

    def _createInstance(self, stage, sdfPath, transform, subInstances, geometryFile):
        # type: (pxr.Usd.Stage, str, List[float], dict, str) -> None
        """
        Create instances for the given geometry instances.
        """
        geoPrim = UsdGeom.Xform.Define(stage, sdfPath)
        geoPrim.AddTransformOp().Set(Gf.Matrix4d(*transform))

        # Create geometry mesh:
        if geometryFile:
            geometryUSDFile = self._getAssetFilePathFromOBJFilePath(geometryFile)
            relativeGeometryUSDFile = os.path.relpath(
                geometryUSDFile,
                self.PrimitivesDirectory)
            geoPrim.GetPrim().GetReferences().AddReference('./' + relativeGeometryUSDFile)

        if subInstances is not None:
            with tqdm(total=len(subInstances.items()), desc='Creating instances', ncols=self.ProgressBarWidth, position=self._SUBINSTANCE_PB_INDEX, leave=None) as progressBar:
                for subInstanceName, subInstanceData in subInstances.items():
                    progressBar.set_description('Instantiating {subInstanceName}'.format(subInstanceName=subInstanceName))

                    if subInstanceData.get('type') == 'archive' and not self._subInstanceIsTooSmallToInstance(subInstanceName):
                        jsonFilename = os.path.join(self.SourceDirectoryPath, subInstanceData.get('jsonFile'))

                        # Get USD Stage name from the JSON file:
                        subInstanceStageFilePath = self._getAssetSubInstanceStageFilePath(jsonFilename)

                        if not os.path.exists(subInstanceStageFilePath):
                            self._parseInstanceJSONFile(jsonFilename, subInstanceStageFilePath)

                        # Reference subDir Stage:
                        subPrim = stage.DefinePrim(sdfPath.AppendChild(subInstanceName))
                        relativeSubInstancesStageFilePath = os.path.relpath(
                            subInstanceStageFilePath,
                            self.PrimitivesDirectory
                        )
                        subPrim.GetReferences().AddReference('./' + relativeSubInstancesStageFilePath)

                    progressBar.update()

    def _processElementData(self, elementData):
        # type: (dict) -> None
        """
        Create instances and subinstances for the given Element data.
        """
        elementName = elementData.get('name')
        # elementMaterialFile = elementData.get('matFile')
        elementOBJFile = elementData.get('geomObjFile')
        elementTransformMatrix = elementData.get('transformMatrix')
        elementInstancedPrimitives = elementData.get('instancedPrimitiveJsonFiles')
        elementInstancedCopies = elementData.get('instancedCopies')

        elementStageFilePath = self.getElementStageFilePath(elementName)
        elementStage = Usd.Stage.CreateNew(elementStageFilePath, load=Usd.Stage.LoadNone)
        rootPrimPath = '/' + elementName
        rootPrim = elementStage.DefinePrim(rootPrimPath, 'Xform')
        elementStage.SetDefaultPrim(rootPrim)

        # Create main Prim:
        self._createInstance(
            stage=elementStage,
            sdfPath=rootPrim.GetPath().AppendChild(elementName),
            transform=elementTransformMatrix,
            subInstances=elementInstancedPrimitives,
            geometryFile=elementOBJFile)

        # Create instanced copies:
        if elementInstancedCopies:
            for instanceName, instanceData in elementInstancedCopies.items():
                self._createInstance(
                    stage=elementStage,
                    sdfPath=rootPrim.GetPath().AppendChild(instanceName),
                    transform=instanceData.get('transformMatrix'),
                    subInstances=instanceData.get('instancedPrimitiveJsonFiles', elementInstancedPrimitives),
                    geometryFile=instanceData.get('geomObjFile', elementOBJFile))

        elementStage.GetRootLayer().Save()

    def _handleElementFile(self, elementJSONFile):
        # type: (str) -> None
        """
        Handle a single Element JSON file.
        """
        with open(elementJSONFile, 'r') as f:
            elementData = json.load(f)
        self._processElementData(elementData)

    def _createElements(self):
        # type: () -> None
        """
        Create instances for all scene Elements.
        """
        elementJSONFiles = [
            ('isBayCedarA1', os.path.join(self.SourceDirectoryPath, 'json', 'isBayCedarA1', 'isBayCedarA1.json')),
            ('isBeach', os.path.join(self.SourceDirectoryPath, 'json', 'isBeach', 'isBeach.json')),
            ('isCoastline', os.path.join(self.SourceDirectoryPath, 'json', 'isCoastline', 'isCoastline.json')),
            ('isCoral', os.path.join(self.SourceDirectoryPath, 'json', 'isCoral', 'isCoral.json')),
            ('isDunesA', os.path.join(self.SourceDirectoryPath, 'json', 'isDunesA', 'isDunesA.json')),
            ('isDunesB', os.path.join(self.SourceDirectoryPath, 'json', 'isDunesB', 'isDunesB.json')),
            ('isGardeniaA', os.path.join(self.SourceDirectoryPath, 'json', 'isGardeniaA', 'isGardeniaA.json')),
            ('isHibiscus', os.path.join(self.SourceDirectoryPath, 'json', 'isHibiscus', 'isHibiscus.json')),
            ('isHibiscusYoung', os.path.join(self.SourceDirectoryPath, 'json', 'isHibiscusYoung', 'isHibiscusYoung.json')),
            ('isIronwoodA1', os.path.join(self.SourceDirectoryPath, 'json', 'isIronwoodA1', 'isIronwoodA1.json')),
            ('isIronwoodB', os.path.join(self.SourceDirectoryPath, 'json', 'isIronwoodB', 'isIronwoodB.json')),
            ('isKava', os.path.join(self.SourceDirectoryPath, 'json', 'isKava', 'isKava.json')),
            ('isLavaRocks', os.path.join(self.SourceDirectoryPath, 'json', 'isLavaRocks', 'isLavaRocks.json')),
            ('isMountainA', os.path.join(self.SourceDirectoryPath, 'json', 'isMountainA', 'isMountainA.json')),
            ('isMountainB', os.path.join(self.SourceDirectoryPath, 'json', 'isMountainB', 'isMountainB.json')),
            ('isNaupakaA', os.path.join(self.SourceDirectoryPath, 'json', 'isNaupakaA', 'isNaupakaA.json')),
            ('isPalmDead', os.path.join(self.SourceDirectoryPath, 'json', 'isPalmDead', 'isPalmDead.json')),
            ('isPalmRig', os.path.join(self.SourceDirectoryPath, 'json', 'isPalmRig', 'isPalmRig.json')),
            ('isPandanusA', os.path.join(self.SourceDirectoryPath, 'json', 'isPandanusA', 'isPandanusA.json')),
            ('osOcean', os.path.join(self.SourceDirectoryPath, 'json', 'osOcean', 'osOcean.json'))
        ]


        with tqdm(total=len(elementJSONFiles), desc='Processing Elements', ncols=self.ProgressBarWidth, position=self._ELEMENT_PB_INDEX, leave=None) as progressBar:
            for elementName, elementJSONFile in elementJSONFiles:
                progressBar.set_description('Processing Element {elementName}'.format(elementName=elementName))
                self._handleElementFile(elementJSONFile)
                progressBar.update()
