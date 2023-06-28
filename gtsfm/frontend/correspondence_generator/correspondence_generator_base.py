"""Base class for correspondence generators.

Authors: John Lambert
"""
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from dask.distributed import Client
import numpy as np

from gtsfm.common.image import Image
from gtsfm.common.keypoints import Keypoints


class CorrespondenceGeneratorBase:
    """Base class for correspondence generators."""

    @abstractmethod
    def generate_correspondences(
        self,
        client: Client,
        images: List[Image],
        image_pairs: List[Tuple[int, int]],
    ) -> Tuple[List[Keypoints], Dict[Tuple[int, int], np.ndarray]]:
        """Apply the correspondence generator to generate putative correspondences.

        Args:
            client: dask client, used to execute the front-end as futures.
            images: list of all images.
            image_pairs: indices of the pairs of images to estimate two-view pose and correspondences.

        Returns:
            List of keypoints, one entry for each input images.
            Putative correspondence as indices of keypoints, for pairs of images.
        """
