"""Utilities to compute and save evaluation metrics.

Authors: Akshay Krishnan
"""
import json
import numpy as np
import os
from dask.delayed import Delayed
from typing import Dict, List, Optional, Tuple

from gtsam import (Point3, Rot3, Pose3)

import gtsfm.utils.geometry_comparisons as comp_utils
from gtsfm.common.sfm_result import SfmResult

# A StatsDict is a dict from string to optional floats or their lists.
StatsDict = Dict[str, Union[Optional[float], List[Optional[float]]]]


def get_errors_statistics(errors: List) -> StatsDict:
    """Computes statistics (min, max, median) on the given list of errors

    Args:
        errors: List of errors for a metric.

    Returns: 
        A dict with keys min_error, max_error, median_error, 
        and errors_list mapping to the respective stats.
    """

    metrics = {}
    valid_errors = [error for error in errors if error is not None]
    metrics["median_error"] = np.median(valid_errors)
    metrics["min_error"] = np.min(valid_errors)
    metrics["max_error"] = np.max(valid_errors)
    metrics["errors_list"] = errors
    return metrics


def compute_rotation_angle_metrics(
        wRi_list: List[Optional[Rot3]],
        gt_wRi_list: List[Optional[Pose3]]) -> StatsDict:
    """Computes statistics for the angle between estimated and GT rotations. 

    Assumes that the estimated and GT rotations have been aligned and do not 
    have a gauge freedom. 

    Args: 
        wRi_list: List of estimated camera rotations. 
        gt_wRi_list: List of ground truth camera rotations. 

    Returns: 
        A statistics dict of the metrics errors in degrees. 
    """
    errors = []
    for (wRi, gt_wRi) in zip(wRi_list, gt_wRi_list):
        angle = np.rad2deg(
            comp_utils.compute_relative_rotation_angle(wRi, gt_wRi))
        errors.append(angle)
    return get_errors_statistics(errors)


def compute_translation_distance_metrics(
        wti_list: List[Optional[Point3]],
        gt_wti_list: List[Optional[Point3]]) -> StatsDict:
    """Computes statistics for the distance between estimated and GT translations. 

    Assumes that the estimated and GT translations have been aligned and do not 
    have a gauge freedom (including scale). 

    Args: 
        wti_list: List of estimated camera translations. 
        gt_wti_list: List of ground truth camera translations. 

    Returns: 
        A statistics dict of the metrics errors in degrees. 
    """
    errors = []
    for (wti, gt_wti) in zip(wti_list, gt_wti_list):
        if wti is None or gt_wti is None:
            errors.append(None)
        else:
            errors.append(np.linalg.norm(wti - gt_wti))
    return get_errors_statistics(errors)


def compute_translation_angle_metrics(
        i2Ui1_dict: Dict[Tuple[int, int], Optional[Unit3]],
        wTi_list: List[Optional[Pose3]]) -> StatsDict:
    """Computes statistics for angle between translations and direction measurements. 

    Args: 
        i2Ui1_dict: List of translation direction measurements. 
        wTi_list: List of estimated camera poses. 

    Returns: 
        A statistics dict of the metrics errors in degrees. 
    """
    angles = []
    for (i1, i2) in i2Ui1_dict:
        i2Ui1 = i2Ui1_dict[(i1, i2)]
        angles.append(
            np.rad2deg(
                comp_utils.compute_translation_to_direction_angle(
                    i2Ui1, wTi[i2], wTi[i1])))
    return get_errors_statistics(angles)


def compute_averaging_metrics(
    i2Ui1_dict: Dict[Tuple[int, int], Unit3],
    wRi_list: List[Optional[Rot3]],
    wti_list: List[Optional[Point3]],
    gt_wTi_list: List[Optional[Pose3]],
) -> Dict[str, StatsDict]:
    """Computes statistics of multiple metrics for the averaging modules. 

    Specifically, computes statistics of: 
        - Rotation angle errors before BA, 
        - Translation distances before BA, 
        - Translation angle to direction measurements, 

    Estimated poses and ground truth poses are first aligned before computing metrics.    

    Args: 
        i2Ui1_dict: Dict from (i1, i2) to unit translation measurement i2Ui1. 
        wRi_list: List of estimated rotations.         
        wti_list: List of estimated translations.
        gt_wTi_list: List of ground truth poses. 

    Returns: 
        Dict from metric name to a StatsDict. 

    Raises: 
        ValueError if lengths of wRi_list, wti_list and gt_wTi_list are not all same. 
    """
    if len(wRi_list) != len(wti_list) or len(wRi_list) != len(gt_wTi_list):
        raise ValueError(
            "Lengths of wRi_list, wti_list and gt_wTi_list should be the same.")

    wTi_list = []
    for (wRi, wti) in zip(wRi_list, wti_list):
        wTi_list.append(Pose3(wRi, wti))
    wTi_aligned_list = comp_utils.align_poses(wTi_list, gt_wTi_list)

    def get_rotations_translations_from_poses(poses):
        rotations = []
        translations = []
        for pose in poses:
            if pose is None:
                rotations.append(None)
                translations.append(None)
                continue
            rotations.append(pose.rotation())
            translations.append(pose.translation())
        return rotations, translations

    wRi_aligned_list, wti_aligned_list = get_rotations_translations_from_poses(
        wTi_aligned_list)
    gt_wRi_list, gt_wti_list = get_rotations_translations_from_poses(
        gt_wTi_list)

    metrics = {}
    metrics['rotation_averaging_angle'] = compute_rotation_angle_metrics(
        wRi_aligned_list, gt_wRi_list)
    metrics[
        'translation_averaging_distance'] = compute_translation_distance_metrics(
            wti_aligned_list, gt_wti_list)
    metrics[
        'translation_to_direction_angle'] = compute_translation_angle_metrics(
            i2Ui1_dict, wTi_aligned_list)
    return metrics


def save_averaging_metrics(
    i2Ui1_dict: Dict[Tuple[int, int], Unit3],
    wRi_list: List[Optional[Rot3]],
    wti_list: List[Optional[Point3]],
    gt_wTi_list: List[Optional[Pose3]],
    output_dir: str,
) -> None:
    """Computes the statistics of multiple metrics and saves them to json. 

    Metrics are written to multiview_optimizer_metrics.json. 

    Args: 
        i2Ui1_dict: Dict from (i1, i2) to unit translation measurement i2Ui1. 
        wRi_list: List of estimated rotations.         
        wti_list: List of estimated translations.
        gt_wTi_list: List of ground truth poses. 
        output_dir: Path to the directory where metrics must be saved. 
    """
    metrics = compute_averaging_metrics(i2Ui1_dict, wRi_list, wti_list,
                                        gt_wTi_list)
    os.makedirs(output_dir, exist_ok=True)
    json_file_path = os.path.join(output_dir,
                                  'multiview_optimizer_metrics.json')

    with open(json_file_path, 'w') as json_file:
        json.dump(metrics, json_file, indent=4)
