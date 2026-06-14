from pydantic import BaseModel
from typing import Optional
from enum import IntEnum


class PriorityLevel(IntEnum):
    SAFETY = 1
    NAVIGATION = 2
    SOCIAL = 3
    INFORMATIONAL = 4
    BACKGROUND = 5


class DetectedElement(BaseModel):
    label: str
    count: int = 1
    position: Optional[str] = None  # left, right, ahead, behind
    distance: Optional[str] = None  # near, far, approaching
    confidence: float = 1.0


class SceneGraph(BaseModel):
    people: list[DetectedElement] = []
    hazards: list[DetectedElement] = []
    objects: list[DetectedElement] = []
    text_detected: list[str] = []
    path_clear: bool = True
    environment: str = ""  # indoor, outdoor, restaurant, street, office, home, other
    movement_detected: bool = False
    spatial_summary: str = ""


