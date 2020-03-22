#!/usr/bin/env python

"""
(Limited) unit tests for the OBJ parser.
"""

import os
import unittest

from moana2usd.obj_parser.obj_parser import getOBJStreamForFile


class TestOBJParser(unittest.TestCase):
    """
    Unit tests for the OBJ parser.
    """

    def setUp(self):
        """
        Create a new instance of the OBJ stream before each test.
        """
        objFilePath = os.path.join('test', 'teapot.obj')
        self.objStream = getOBJStreamForFile(objFilePath)

    def testParsingOfVertices(self):
        """
        Validate that the number of vertices parsed matches the one expected.
        """
        self.assertEqual(len(self.objStream.GetVerts()), 1292)

    def testParsingOfUVs(self):
        """
        Validate that the number of UVs parsed matches the one expected.
        """
        self.assertEqual(len(self.objStream.GetUVs()), 0)

    def testParsingOfNormals(self):
        """
        Validate that the number of normals parsed matches the one expected.
        """
        self.assertEqual(len(self.objStream.GetNormals()), 1289)

    def testParsingOfPoints(self):
        """
        Validate that the number of points parsed matches the one expected.
        """
        self.assertEqual(len(self.objStream.GetPoints()), 7392)

    def testParsingOfGroups(self):
        """
        Validate that the current group parsed matches the one expected.
        """
        self.assertEqual(self.objStream.GetCurrentGroup(), 'teapot')

    def testParsingOfMaterials(self):
        """
        Validate that the materials parsed matches the ones expected.
        """
        self.assertEqual(self.objStream.GetMaterialNames(), ['default'])


if __name__ == '__main__':
    unittest.main()
