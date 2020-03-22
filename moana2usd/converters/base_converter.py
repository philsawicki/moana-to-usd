#!/usr/bin/env python

"""
Base class for the conversion of content to USD format.
"""

import os


class ContentConverter(object):
    """
    Base content converter class, to be extended by concern-specific subclasses.
    """

    def __init__(self, fileFormat, sourceDirectoryPath, destinationDirectoryPath):
        # type: (str, str, str) -> ContentConverter
        """
        Initialize the converter using the provided USD file format, dataset
        source directory path and destination folder path.
        """
        self._fileFormat = fileFormat
        self._sourceDirectoryPath = sourceDirectoryPath
        self._destinationDirectoryPath = destinationDirectoryPath

    def convert(self):
        # type: () -> None
        """
        Start the conversion process.
        """
        raise NotImplementedError('Should be implemented by subclasses.')

    @property
    def PrimitivesDirectory(self):
        # type: () -> str
        """
        Return the path of the primitives directory, where converted content
        will be written.
        """
        return os.path.join(self.DestinationDirectoryPath, 'primitives')

    @property
    def USDFileExtension(self):
        # type: () -> str
        """
        Return the extension of the file format to use when authoring USD
        content (including the leading '.').
        """
        return '.{fileFormat}'.format(fileFormat=self._fileFormat)

    @property
    def SourceDirectoryPath(self):
        # type: () -> str
        """
        Return the directory path where the Moana Island Scene dataset is
        located.
        """
        return self._sourceDirectoryPath

    @property
    def DestinationDirectoryPath(self):
        # type: () -> str
        """
        Return the directory path where the USD content will be assembled.
        """
        return self._destinationDirectoryPath

    @property
    def ProgressBarWidth(self):
        # type: () -> int
        """
        Return the number of columns to use when drawing progress bars during
        long operations.
        """
        return 110
