#!/usr/bin/env python

"""
(Simple) OBJ parser.
"""

import json
import os


class Point(object):
    """
    Point in the OBJ file format.
    """

    def __init__(self, vertIndex=-1, uvIndex=-1, normalIndex=-1):
        # type: (int, int, int) -> Point
        """
        Build a Point from the OBJ file stream.
        """
        self.vertIndex = vertIndex
        self.uvIndex = uvIndex
        self.normalIndex = normalIndex

class Face(object):
    """
    Face in the OBJ file format.
    """

    def __init__(self, pointsBeginIndex=0, pointsEndIndex=0):
        # type: (int, int) -> Face
        """
        Build a Face from the given start and end Point indices.
        """
        self.pointsBegin = pointsBeginIndex
        self.pointsEnd = pointsEndIndex

    def size(self):
        # type: () -> int
        """
        Return the number of points in the face.
        """
        return self.pointsEnd - self.pointsBegin

class Group(object):
    """
    Group in the OBJ file format.
    """

    def __init__(self, name, faces):
        # type: (str, List[Face]) -> Group
        """
        Build a Mesh Group from the given Faces.
        """
        self.name = name
        self.faces = faces

class OBJStream(object):
    """
    OBJ content stream.
    """

    def __init__(self):
        # type: () -> OBJStream
        """
        Create a new OBJ content stream.
        """
        self._verts = []
        self._uvs = []
        self._normals = []
        self._points = []
        self._groups = []
        self._materialMap = {
            'default': 'default'
        }

    def AddVert(self, vertex):
        # type: (Point) -> None
        """
        Add a Point for a Face.
        """
        self._verts.append(vertex)

    def GetVerts(self):
        # type: () -> List[Point]
        """
        Return the list of Points for the OBJ Stream.
        """
        return self._verts

    def AddUV(self, uv):
        # type: (Tuple[float, float]) -> None
        """
        Add UV coordinates.
        """
        self._uvs.append(uv)

    def GetUVs(self):
        # type: () -> List[Tuple[float, float]]
        """
        Return the list of UV coordinates for the OBJ Stream.
        """
        return self._uvs

    def AddNormal(self, normal):
        # type: (Tuple[float, float, float]) -> None
        """
        Add a Normal.
        """
        self._normals.append(normal)

    def GetNormals(self):
        # type: () -> List[Tuple[float, float, float]]
        """
        Return the list of Normals for the OBJ Stream.
        """
        return self._normals

    def AddPoint(self, point):
        # type: (Point) -> None
        """
        Add a Point.
        """
        self._points.append(point)

    def GetPoints(self):
        # type: () -> List[Point]
        """
        Return the list of Points for the OBJ Stream.
        """
        return self._points

    def AddFace(self, face):
        # type: (Face) -> None
        """
        Add a Face to the current OBJ Stream Group.
        """
        if not self._groups:
            self.AddGroup('default')
        self._groups[-1].faces.append(face)

    def AddGroup(self, groupName):
        # type: (str) -> None
        """
        Add the given Group name if it does not already exist.
        """
        if self.FindGroup(groupName) is None:
            group = Group(groupName, [])
            self._groups.append(group)
            return True
        return False

    def FindGroup(self, groupName):
        # type: (str) -> Group or None
        """
        Return the Group matching the given name.
        """
        for group in self._groups:
            if group.name == groupName:
                return group
        return None

    def GetGroups(self):
        # type: () -> List[Group]
        """
        Return the list of Groups for the OBJ Stream.
        """
        return self._groups

    def AddMaterial(self, groupName, materialName):
        # type: (groupName, materialName) -> None
        """
        Add a Material.
        """
        self._materialMap.update({ groupName: materialName })

    def GetMaterialForGroup(self, groupName):
        # type: (str) -> str
        """
        Return the name of the Material to use for the given Group.
        """
        return self._materialMap.get(groupName, 'default')

    def GetMaterialNames(self):
        # type: () -> List[str]
        """
        Return the list of all Material names for the OBJ Stream.
        """
        return self._materialMap.values()

    def GetCurrentGroup(self):
        # type: () -> str
        """
        Return the name of the current Group for the OBJ Stream.
        """
        return self._groups[-1].name


def getDisplayColorForMaterial(assetOBJPath, materialName, sourceDirectoryPath):
    # type: (str, str, str) -> List[float] or None
    """
    Return the display color to use for the given Material Name.
    """
    assetSubDirName = os.path.relpath(assetOBJPath, sourceDirectoryPath).split('\\')[1]
    assetMaterialFilePath = os.path.join(sourceDirectoryPath, 'json', assetSubDirName, 'materials.json')
    if os.path.exists(assetMaterialFilePath):
        with open(assetMaterialFilePath) as f:
            materialJSONData = json.load(f)
        materialData = materialJSONData.get(materialName)
        if materialData:
            baseColor = materialData.get('baseColor')
            if baseColor is not None and baseColor != [1.0, 0.0, 0.0] and baseColor != [1.0, 0.0, 1.0]:
                return baseColor
    return None

def getDisplayOpacityForMaterial(assetOBJPath, materialName, sourceDirectoryPath):
    # type: (str, str, str) -> float or None
    """
    Return the opacity to use for the given Material Name.
    """
    assetSubDirName = os.path.relpath(assetOBJPath, sourceDirectoryPath).split('\\')[1]
    assetMaterialFilePath = os.path.join(sourceDirectoryPath, 'json', assetSubDirName, 'materials.json')
    if os.path.exists(assetMaterialFilePath):
        with open(assetMaterialFilePath) as f:
            materialJSONData = json.load(f)
        materialData = materialJSONData.get(materialName)
        if materialData:
            baseColor = materialData.get('baseColor')
            if baseColor is not None and len(baseColor) >= 4:
                return baseColor[3]
    return None

def getOBJStreamForFile(inputFile):
    # type: (str) -> OBJStream
    """
    Parse the given OBJ file and return its stream representation.
    """
    objStream = OBJStream()

    with open(inputFile, 'rU') as f:
        for line in f:
            line = line.strip()
            if line == '':
                continue

            if line[0] == 'v':
                if line[1] == ' ':
                    vertexCoord = line.replace('v ', '').strip().split()
                    objStream.AddVert(
                        (float(vertexCoord[0]), float(vertexCoord[1]), float(vertexCoord[2]))
                    )
                elif line[1] == 'n':
                    normalCoord = line.replace('vn ', '').strip().split()
                    objStream.AddNormal(
                        (float(normalCoord[0]), float(normalCoord[1]), float(normalCoord[2]))
                    )
                elif line[1] == 't':
                    uvCoord = line.replace('vt ', '').strip().split()
                    objStream.AddUV(
                        (float(uvCoord[0]), float(uvCoord[1]))
                    )
            elif line[0] == 'f':
                pointsBegin = len(objStream.GetPoints())
                pointData = line.replace('f ', '').strip().split()
                for i in pointData:
                    uvIndex = -1
                    nIndex = -1
                    segments = i.split('/')
                    vertIndex = int(segments[0]) - 1 if segments[0] != '' else -1
                    if len(segments) > 1 and segments[1] != '':
                        uvIndex = int(segments[1]) - 1
                    if len(segments) > 2 and segments[2] != '':
                        nIndex = int(segments[2]) - 1
                    objStream.AddPoint(Point(vertIndex, uvIndex, nIndex))
                pointsEnd = len(objStream.GetPoints())
                objStream.AddFace(Face(pointsBegin, pointsEnd))
            elif line[0] == 'g':
                groupName = line.replace('g ', '')
                if groupName == 'g':
                    groupName = 'default'
                objStream.AddGroup(groupName)
            elif line.startswith('usemtl '):
                materialName = line.replace('usemtl ', '').strip()
                if materialName != '':
                    objStream.AddMaterial(objStream.GetCurrentGroup(), materialName)

    return objStream
