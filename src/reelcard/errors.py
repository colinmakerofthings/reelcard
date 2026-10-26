"""Exceptions raised by Reelcard's video-processing components."""


class ReelcardError(Exception):
    """Base class for expected Reelcard errors."""


class VideoError(ReelcardError):
    """Base class for video input and processing errors."""


class InvalidVideoError(VideoError):
    """The input path is not a supported video file."""


class VideoToolError(VideoError):
    """An external video tool is unavailable or failed."""


class FrameExtractionError(VideoError):
    """A requested frame could not be extracted."""
