#!/usr/bin/env python

"""
Asset conversion from OBJ to USD.
"""

import json
import os

from moana2usd.converters.base_converter import ContentConverter
from moana2usd.obj_parser.obj_parser import getOBJStreamForFile, getDisplayColorForMaterial, getDisplayOpacityForMaterial

from pxr import Gf, Kind, Sdf, Usd, UsdGeom, UsdHydra, UsdShade
from tqdm import tqdm


class AssetConverter(ContentConverter):
    """
    Converter for OBJ assets into USD assets.
    """

    def __init__(self, fileFormat, sourceDirectoryPath, destinationDirectoryPath, loadTextures=True):
        # type: (str, str, str, boolean) -> AssetConverter
        """
        Initialize the converter using the provided USD file format, dataset
        source directory path and destination folder path.
        """
        super(AssetConverter, self).__init__(fileFormat, sourceDirectoryPath, destinationDirectoryPath)

        self._loadTextures = loadTextures
        self._geometryPrimName = 'geometry'

    def convert(self):
        # type: () -> None
        """
        Start the conversion process.
        """
        self._createAssets()

    def _getAssetElementName(self, assetOBJPath):
        # type: (str) -> str
        """
        Return the Element name of the given asset's OBJ file path.
        """
        assetOBJFileName = os.path.basename(assetOBJPath)
        return os.path.splitext(assetOBJFileName)[0]

    def _getAssetsStagePath(self, assetOBJPath):
        # type: (str) -> str
        """
        Return the USD Stage file path for the given asset's OBJ file path.
        """
        return os.path.join(
            self.PrimitivesDirectory,
            self._getAssetElementName(assetOBJPath) + self.USDFileExtension)

    def _getMeshPath(self, rootPath, groupName):
        # type: (str, str) -> str
        """
        Return the path of the USD Mesh for the given OBJ group.
        """
        return '{rootPath}/{geometryPrimName}/{groupName}'.format(
            rootPath=rootPath,
            geometryPrimName=self._geometryPrimName,
            groupName=groupName)

    def _getMaterialPath(self, rootPath, materialName):
        # type: (str, str) -> str
        """
        Return the path of the USD Prim for the given material.
        """
        return '{rootPath}/materials/{materialName}'.format(
            rootPath=rootPath,
            materialName=materialName)

    def _getShaderPath(self, materialPath):
        # type: (str) -> str
        """
        Return the path of the USD Shader for the given material.
        """
        return '{materialPath}/previewSurfaceShader'.format(
            materialPath=materialPath)

    def _convertOBJToUSD(self, assetOBJPath, objStream):
        # type: (str, moana2usd.obj_parser.OBJStream) -> None
        """
        Convert the given OBJ stream into a USD asset.
        """
        layer = Sdf.Layer.CreateAnonymous(self.USDFileExtension)

        ## ##
        elementName = os.path.relpath(assetOBJPath, self.SourceDirectoryPath).split('\\')[1]
        rootPath = '/' + elementName
        modelRootPrimSpec = Sdf.CreatePrimInLayer(layer, rootPath)
        modelRootPrimSpec.specifier = Sdf.SpecifierDef
        modelRootPrimSpec.typeName = 'Xform'
        modelRootPrimSpec.kind = Kind.Tokens.component
        layer.defaultPrim = elementName
        ## ##

        usdPoints = objStream.GetVerts()
        objPoints = objStream.GetPoints()


        # Leverage the SDF API instead of the USD API in order to batch-create
        # Prims. This avoids fanning out change notifications, which results in
        # O(n2) performance and becomes *slow* when creating a large number of
        # Prims -- which is the case here (sometimes upwards of a million Prims).
        with Sdf.ChangeBlock():
            meshGeoSpecPath = rootPath + '/' + self._geometryPrimName
            meshGeoSpec = Sdf.CreatePrimInLayer(layer, meshGeoSpecPath)
            meshGeoSpec.specifier = Sdf.SpecifierDef

            for group in objStream.GetGroups():
                if not group.faces:
                    continue

                groupVertexBuffer = []
                objectToGroupVertexBufferMap = {}
                groupVertexIndices = []

                faceVertexCounts = []
                faceVertexIndices = []
                for face in group.faces:
                    faceVertexCounts.append(face.size())
                    for pointIndex in xrange(face.pointsBegin, face.pointsEnd):
                        objPoint = objPoints[pointIndex]

                        # Vertices:
                        vertexIndex = objPoint.vertIndex
                        faceVertexIndices.append(vertexIndex)
                        smallBufferIndex = objectToGroupVertexBufferMap.get(vertexIndex)
                        if smallBufferIndex is None:
                            smallBufferIndex = len(groupVertexBuffer)
                            objectToGroupVertexBufferMap.update({ vertexIndex: smallBufferIndex })
                            groupVertexBuffer.append(usdPoints[vertexIndex])
                        groupVertexIndices.append(smallBufferIndex)


                materialName = objStream.GetMaterialForGroup(group.name)
                baseColor = getDisplayColorForMaterial(assetOBJPath, materialName, self.SourceDirectoryPath)
                alpha = getDisplayOpacityForMaterial(assetOBJPath, materialName, self.SourceDirectoryPath)

                groupExtent = Gf.Range3f()
                for groupVertex in groupVertexBuffer:
                    groupExtent.UnionWith(groupVertex)


                meshPrimSpecPath = self._getMeshPath(rootPath, group.name)
                meshPrimSpec = Sdf.CreatePrimInLayer(layer, meshPrimSpecPath)
                meshPrimSpec.specifier = Sdf.SpecifierDef
                meshPrimSpec.typeName = 'Mesh'
                meshPrimSpec.instanceable = True

                # Add geometry information:
                subdivisionSchemeAttribute = Sdf.AttributeSpec(
                    meshPrimSpec,
                    UsdGeom.Tokens.subdivisionScheme,
                    Sdf.ValueTypeNames.Token,
                    variability=Sdf.VariabilityUniform)
                subdivisionSchemeAttribute.default = UsdGeom.Tokens.catmullClark

                faceVertexCountsAttribute = Sdf.AttributeSpec(
                    meshPrimSpec,
                    UsdGeom.Tokens.faceVertexCounts,
                    Sdf.ValueTypeNames.IntArray)
                faceVertexCountsAttribute.default = faceVertexCounts

                faceVertexIndicesAttribute = Sdf.AttributeSpec(
                    meshPrimSpec,
                    UsdGeom.Tokens.faceVertexIndices,
                    Sdf.ValueTypeNames.IntArray)
                faceVertexIndicesAttribute.default = groupVertexIndices

                pointsAttribute = Sdf.AttributeSpec(
                    meshPrimSpec,
                    UsdGeom.Tokens.points,
                    Sdf.ValueTypeNames.Point3fArray)
                pointsAttribute.default = groupVertexBuffer

                extentAttribute = Sdf.AttributeSpec(
                    meshPrimSpec,
                    UsdGeom.Tokens.extent,
                    Sdf.ValueTypeNames.Float3Array)
                extentAttribute.default = [groupExtent.GetMin(), groupExtent.GetMax()]

                # Add display color:
                if baseColor:
                    displayColorAttribute = Sdf.AttributeSpec(
                        meshPrimSpec,
                        UsdGeom.Tokens.primvarsDisplayColor,
                        Sdf.ValueTypeNames.Color3fArray)
                    displayColorAttribute.default = [Gf.Vec3f(*baseColor[:3])]

                # Add display opacity:
                if alpha:
                    displayOpacityAttribute = Sdf.AttributeSpec(
                        meshPrimSpec,
                        UsdGeom.Tokens.primvarsDisplayOpacity,
                        Sdf.ValueTypeNames.FloatArray)
                    displayOpacityAttribute.default = [alpha]


        # TODO: Change this to only read content from the JSON material file
        # once per asset (it is also read above)
        materialInfo = {}
        materialFilePath = os.path.join(self.SourceDirectoryPath, 'json', elementName, 'materials.json')
        with open(materialFilePath, 'r') as f:
            materialInfo = json.load(f)

        def getMaterialDataForGroup(groupName):
            materialName = objStream.GetMaterialForGroup(groupName)
            return materialInfo.get(materialName)

        stage = Usd.Stage.Open(layer, load=Usd.Stage.LoadNone)

        for group in objStream.GetGroups():
            if not group.faces:
                continue

            # TODO: Avoid duplicating materials and shaders if they share the
            # same properties?
            materialPath = self._getMaterialPath(rootPath, group.name.replace('_geo', '_mat'))
            material = UsdShade.Material.Define(stage, materialPath)

            previewSurfaceShaderPath = self._getShaderPath(materialPath)
            previewSurfaceShader = UsdShade.Shader.Define(stage, previewSurfaceShaderPath)
            previewSurfaceShader.CreateIdAttr('UsdPreviewSurface')

            materialData = getMaterialDataForGroup(group.name)
            if materialData is not None:
                baseColor = materialData.get('baseColor')
                if baseColor is not None and baseColor != [1, 0, 0] and baseColor != [1, 0, 1]:
                    previewSurfaceShader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set( Gf.Vec3f(*baseColor[:3]) )

                    if elementName == 'osOcean':
                        previewSurfaceShader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(0.2)
                    elif len(baseColor) >= 4:
                        previewSurfaceShader.CreateInput('opacity', Sdf.ValueTypeNames.Float).Set(baseColor[3])
                else:
                    baseColor = [1.0, 1.0, 1.0]
                    previewSurfaceShader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).Set( Gf.Vec3f(*baseColor[:3]) )

                roughness = materialData.get('roughness')
                if roughness is not None:
                    previewSurfaceShader.CreateInput('roughness', Sdf.ValueTypeNames.Float).Set(roughness)

                metallic = materialData.get('metallic')
                if metallic is not None:
                    previewSurfaceShader.CreateInput('metallic', Sdf.ValueTypeNames.Float).Set(metallic)

                clearcoat = materialData.get('clearcoat')
                if clearcoat is not None:
                    previewSurfaceShader.CreateInput('clearcoat', Sdf.ValueTypeNames.Float).Set(clearcoat)

                ior = materialData.get('ior')
                if ior is not None:
                    previewSurfaceShader.CreateInput('ior', Sdf.ValueTypeNames.Float).Set(ior)

                clearcoatGloss = materialData.get('clearcoatGloss')
                if clearcoatGloss is not None:
                    clearcoatRoughness = max(1 - clearcoatGloss, 0.01)
                    previewSurfaceShader.CreateInput('clearcoatRoughness', Sdf.ValueTypeNames.Float).Set(clearcoatRoughness)

                if self._loadTextures:
                    # TODO: Use texture path provided in the JSON metadata file
                    # instead of relying on the naming convention.
                    colorMapFilePath = os.path.join(self.SourceDirectoryPath, 'textures', elementName, 'Color', group.name + '.ptx')
                    if os.path.exists(colorMapFilePath):
                        colorMapShaderPath = materialPath + '/colorMap'
                        colorMapShader = UsdShade.Shader.Define(stage, colorMapShaderPath)
                        colorMapShader.CreateIdAttr(UsdHydra.Tokens.HwPtexTexture_1)
                        colorMapShader.CreateInput('file', Sdf.ValueTypeNames.Asset).Set( colorMapFilePath.replace('\\', '/') )
                        colorMapShader.CreateOutput('rgb', Sdf.ValueTypeNames.Color3f)

                        previewSurfaceShader.CreateInput('diffuseColor', Sdf.ValueTypeNames.Color3f).ConnectToSource(colorMapShader, 'rgb')

                    # TODO: This needs to be changed: Need to map a single-channel
                    # "displacement" to a 3-channel "rgb" output?
                    # displacementMapFilePath = os.path.join(self.SourceDirectoryPath, 'textures', elementName, 'Displacement', group.name + '.ptx')
                    # if os.path.exists(displacementMapFilePath):
                    #     displacementMapShaderPath = materialPath + '/displacementMap'
                    #     displacementMapShader = UsdShade.Shader.Define(stage, displacementMapShaderPath)
                    #     displacementMapShader.CreateIdAttr(UsdHydra.Tokens.HwPtexTexture_1)
                    #     displacementMapShader.CreateInput('file', Sdf.ValueTypeNames.Asset).Set( displacementMapFilePath.replace('\\', '/') )
                    #     displacementMapShader.CreateOutput('rgb', Sdf.ValueTypeNames.Color3f)

                    #     previewSurfaceShader.CreateInput('displacement', Sdf.ValueTypeNames.Float).ConnectToSource(displacementMapShader, 'r')


            # Connect the output of the PreviewSurface Shader to the material:
            material.CreateSurfaceOutput().ConnectToSource(previewSurfaceShader, 'surface')
            # material.CreateDisplacementOutput().ConnectToSource(previewSurfaceShader, 'displacement')

            # Bind the material to mesh:
            meshPath = self._getMeshPath(rootPath, group.name)
            mesh = UsdGeom.Mesh(stage.GetPrimAtPath(meshPath))
            UsdShade.MaterialBindingAPI(mesh).Bind(material)

        # Export the resulting USD asset stage:
        assetStagePath = self._getAssetsStagePath(assetOBJPath)
        layer.Export(assetStagePath, comment='')

    def _translateOBJFileIntoUSD(self, assetOBJPath):
        # type: (str) -> None
        """
        Convert the given OBJ file into a USD Mesh with associated USD
        Materials and Shaders.
        """
        objStream = getOBJStreamForFile(assetOBJPath)
        if objStream.GetVerts():
            self._convertOBJToUSD(assetOBJPath, objStream)

    def _createAssets(self):
        # type: () -> None
        """
        Convert the OBJ assets from the Moana Island Scene dataset into USD
        assets.
        """
        assetOBJFiles = [
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBayCedarA1', 'isBayCedarA1.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBayCedarA1', 'isBayCedarA1_bonsaiA.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBayCedarA1', 'isBayCedarA1_bonsaiB.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBayCedarA1', 'isBayCedarA1_bonsaiC.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBayCedarA1', 'archives', 'archivebaycedar0001_mod.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'isBeach.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgFibers_archivepineneedle0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgFibers_archivepineneedle0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgFibers_archivepineneedle0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgFibers_archiveseedpodb_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveCoral0009_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveRock0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveRock0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveRock0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveRock0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveRock0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveRock0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveRock0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgGroundCover_archiveShell0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0004_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0005_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0006_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0007_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0008_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgHibiscus_archiveHibiscusFlower0009_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPalmDebris_archiveLeaflet0123_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPalmDebris_archiveLeaflet0124_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPalmDebris_archiveLeaflet0125_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPalmDebris_archiveLeaflet0126_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPalmDebris_archiveLeaflet0127_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveCoral0009_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveRock0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveRock0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveRock0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveRock0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveRock0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveRock0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgPebbles_archiveRock0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgSeaweed_archiveSeaweed0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgSeaweed_archiveSeaweed0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgSeaweed_archiveSeaweed0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgSeaweed_archiveSeaweed0063_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgSeaweed_archiveSeaweed0064_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgSeaweed_archiveSeaweed0065_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShells_archiveShell0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgShellsSmall_archiveShell0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgStones_archiveRock0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgStones_archiveRock0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgStones_archiveRock0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgStones_archiveRock0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgStones_archiveRock0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgStones_archiveRock0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isBeach', 'archives', 'xgStones_archiveRock0007_geo.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'isCoastline.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgFibers_archivepineneedle0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgFibers_archivepineneedle0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgFibers_archivepineneedle0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgFibers_archiveseedpodb_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgPalmDebris_archiveLeaflet0123_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgPalmDebris_archiveLeaflet0124_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgPalmDebris_archiveLeaflet0125_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgPalmDebris_archiveLeaflet0126_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoastline', 'archives', 'xgPalmDebris_archiveLeaflet0127_geo.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'isCoral.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'isCoral1.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'isCoral2.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'isCoral3.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'isCoral4.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'isCoral5.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgAntlers_archivecoral_antler0009_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgCabbage_archivecoral_cabbage0009_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgFlutes_flutes.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0009_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isCoral', 'archives', 'xgStaghorn_archivecoral_staghorn0010_geo.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'isDunesA.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgDebris_archivepineneedle0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgDebris_archivepineneedle0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgDebris_archivepineneedle0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgDebris_archiveseedpoda_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgDebris_archiveseedpodb_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0004_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0005_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0006_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0007_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0008_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgHibiscusFlower_archiveHibiscusFlower0009_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgMuskFern_fern0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgMuskFern_fern0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgMuskFern_fern0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgMuskFern_fern0004_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesA', 'archives', 'xgMuskFern_fern0005_mod.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'isDunesB.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgPandanus_isPandanusAlo_base.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0001_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0002_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0003_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0004_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0005_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0006_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0007_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0008_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0009_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0010_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0011_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0012_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0013_geo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isDunesB', 'archives', 'xgRoots_archiveroot0014_geo.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'isGardeniaA.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0004_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0005_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0006_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0007_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0008_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardenia0009_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardeniaflw0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardeniaflw0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isGardeniaA', 'archives', 'archivegardeniaflw0003_mod.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isHibiscus', 'isHibiscus.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isHibiscus', 'archives', 'archiveHibiscusFlower0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isHibiscus', 'archives', 'archiveHibiscusLeaf0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isHibiscus', 'archives', 'archiveHibiscusLeaf0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isHibiscus', 'archives', 'archiveHibiscusLeaf0003_mod.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isHibiscusYoung', 'isHibiscusYoung.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isIronwoodA1', 'isIronwoodA1.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isIronwoodA1', 'isIronwoodA1_variantA_lo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isIronwoodA1', 'isIronwoodA1_variantB_lo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isIronwoodA1', 'archives', 'archiveseedpodb_mod.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isIronwoodB', 'isIronwoodB.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isIronwoodB', 'archives', 'archiveseedpodb_mod.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isKava', 'isKava.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isKava', 'archives', 'archive_kava0001_mod.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isLavaRocks', 'isLavaRocks.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isLavaRocks', 'isLavaRocks1.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'isMountainA.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgBreadFruit_archiveBreadFruitBaked.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig1.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig2.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig3.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig4.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig5.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig6.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig7.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig8.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig12.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig13.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig14.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig15.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig16.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgCocoPalms_isPalmRig17.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainA', 'archives', 'xgFoliageC_treeMadronaBaked_canopyOnly_lo.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'isMountainB.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgBreadFruit_archiveBreadFruitBaked.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig1.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig2.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig3.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig6.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig8.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig12.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig13.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig14.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig15.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig16.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgCocoPalms_isPalmRig17.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0001_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0002_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0003_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0004_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0005_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0006_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0007_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0008_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0009_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0010_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0011_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0012_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0013_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFern_fern0014_mod.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFoliageA_treeMadronaBaked_canopyOnly_lo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFoliageAd_treeMadronaBaked_canopyOnly_lo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFoliageB_treeMadronaBaked_canopyOnly_lo.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isMountainB', 'archives', 'xgFoliageC_treeMadronaBaked_canopyOnly_lo.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isNaupakaA', 'isNaupakaA.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isNaupakaA', 'isNaupakaA1.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isNaupakaA', 'isNaupakaA2.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isNaupakaA', 'isNaupakaA3.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isNaupakaA', 'archives', 'xgBonsai_isNaupakaBon_bon_hero_ALL.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmDead', 'isPalmDead.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig2.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig3.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig4.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig5.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig6.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig7.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig8.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig9.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig10.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig11.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig12.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig13.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig14.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig15.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig16.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig17.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig18.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig19.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig20.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig21.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig22.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig23.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig24.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig25.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig26.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig27.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig28.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig29.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig30.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig31.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig32.obj'),
            os.path.join(self.SourceDirectoryPath, 'obj', 'isPalmRig', 'isPalmRig33.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'isPandanusA', 'isPandanusA.obj'),

            os.path.join(self.SourceDirectoryPath, 'obj', 'osOcean', 'osOcean.obj')
        ]


        # Filter out OBJ files that have already been translated to USD (perhaps
        # as a result of a previous run):
        assetsOBJFilesThatDoNotExist = []
        for assetOBJFile in assetOBJFiles:
            translatedUSDFilePath = self._getAssetsStagePath(assetOBJFile)
            if not os.path.exists(translatedUSDFilePath):
                assetsOBJFilesThatDoNotExist.append(assetOBJFile)


        # Translate OBJ files into USD:
        with tqdm(total=len(assetsOBJFilesThatDoNotExist), desc='Translating assets', ncols=self.ProgressBarWidth) as progressBar:
            for assetOBJPath in assetsOBJFilesThatDoNotExist:
                self._translateOBJFileIntoUSD(assetOBJPath)
                progressBar.update()
