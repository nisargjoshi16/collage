"""Subject-aware image fitting for collage cells."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

MODEL_PATH = Path(__file__).resolve().parent.parent / "assets" / "models" / "face_detection_yunet_2023mar.onnx"


@dataclass(frozen=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def area(self) -> int:
        return self.width * self.height

    def scaled(self, factor: float) -> Region:
        return Region(
            int(self.x * factor),
            int(self.y * factor),
            max(1, int(self.width * factor)),
            max(1, int(self.height * factor)),
        )

    def expanded(self, pad_x: float = 0.8, pad_top: float = 1.2, pad_bottom: float = 2.0) -> Region:
        px = int(self.width * pad_x)
        pt = int(self.height * pad_top)
        pb = int(self.height * pad_bottom)
        return Region(self.x - px, self.y - pt, self.width + px * 2, self.height + pt + pb)


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(value, maximum))


@lru_cache(maxsize=1)
def _yunet_detector() -> cv2.FaceDetectorYN:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"Face model not found at {MODEL_PATH}. "
            "Download face_detection_yunet_2023mar.onnx into assets/models/."
        )
    return cv2.FaceDetectorYN.create(
        str(MODEL_PATH),
        "",
        (320, 320),
        score_threshold=0.3,
        nms_threshold=0.35,
        top_k=5000,
    )


def detect_faces(image: Image.Image) -> list[Region]:
    rgb = np.array(image.convert("RGB"))
    height, width = rgb.shape[:2]

    detector = _yunet_detector()
    detector.setInputSize((width, height))
    _, faces = detector.detect(rgb)
    if faces is None:
        return []

    regions: list[Region] = []
    min_side = max(36, int(min(width, height) * 0.025))
    for face in faces:
        x, y, w, h, score = face[:5]
        w_i, h_i = int(w), int(h)
        if w_i < min_side or h_i < min_side:
            continue
        if float(score) < 0.55 and w_i * h_i < 2500:
            continue
        if (y + h_i / 2) > height * 0.88:
            continue
        regions.append(Region(int(x), int(y), w_i, h_i))

    return _merge_overlapping_faces(regions)


def _merge_overlapping_faces(faces: list[Region], overlap_threshold: float = 0.4) -> list[Region]:
    if not faces:
        return []

    faces = sorted(faces, key=lambda face: face.area, reverse=True)
    merged: list[Region] = []

    for face in faces:
        if any(_overlap_ratio(face, kept) > overlap_threshold for kept in merged):
            continue
        merged.append(face)

    return merged


def _overlap_ratio(first: Region, second: Region) -> float:
    overlap_w = max(0, min(first.right, second.right) - max(first.x, second.x))
    overlap_h = max(0, min(first.bottom, second.bottom) - max(first.y, second.y))
    overlap_area = overlap_w * overlap_h
    if overlap_area == 0:
        return 0.0
    smaller = min(first.area, second.area)
    return overlap_area / smaller if smaller else 0.0


def subject_region(image: Image.Image, faces: list[Region]) -> Region:
    width, height = image.size
    if faces:
        expanded = [face.expanded() for face in faces]
        left = max(0, min(region.x for region in expanded))
        top = max(0, min(region.y for region in expanded))
        right = min(width, max(region.right for region in expanded))
        bottom = min(height, max(region.bottom for region in expanded))
        return Region(left, top, right - left, bottom - top)

    # Group/event photos usually place people in the upper two-thirds.
    return Region(0, 0, width, int(height * 0.72))


def _region_fits_in_crop(region: Region, left: int, top: int, crop_w: int, crop_h: int) -> bool:
    return (
        region.x >= left
        and region.y >= top
        and region.right <= left + crop_w
        and region.bottom <= top + crop_h
    )


def choose_crop_origin(
    subject: Region,
    new_w: int,
    new_h: int,
    target_w: int,
    target_h: int,
    src_aspect: float,
) -> tuple[int, int]:
    max_left = max(0, new_w - target_w)
    max_top = max(0, new_h - target_h)
    if max_left == 0 and max_top == 0:
        return 0, 0

    left_min = _clamp(subject.right - target_w, 0, max_left)
    left_max = _clamp(subject.x, 0, max_left)
    top_min = _clamp(subject.bottom - target_h, 0, max_top)
    top_max = _clamp(subject.y, 0, max_top)

    if left_min <= left_max:
        focus_x = subject.x + subject.width / 2
        left = _clamp(int(focus_x - target_w / 2), left_min, left_max)
    else:
        left = max_left // 2

    if top_min <= top_max:
        focus_y = subject.y + subject.height / 3
        top = _clamp(int(focus_y - target_h * 0.28), top_min, top_max)
    elif src_aspect < 0.85:
        top = 0
    else:
        top = max_top // 2

    return left, top


def should_use_contain(src_w: int, src_h: int, target_w: int, target_h: int, subject: Region) -> bool:
    src_aspect = src_w / src_h
    tgt_aspect = target_w / target_h

    if src_aspect < tgt_aspect * 0.72:
        cover_scale = max(target_w / src_w, target_h / src_h)
        subject_h = subject.height * cover_scale
        if subject_h > target_h * 1.05:
            return True

    if src_aspect > tgt_aspect * 1.45:
        cover_scale = max(target_w / src_w, target_h / src_h)
        subject_w = subject.width * cover_scale
        if subject_w > target_w * 1.05:
            return True

    return False


def contain_with_blur(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    img = image.convert("RGBA")
    src_w, src_h = img.size

    fit_scale = min(target_w / src_w, target_h / src_h)
    fit_w = max(1, int(src_w * fit_scale))
    fit_h = max(1, int(src_h * fit_scale))
    fitted = img.resize((fit_w, fit_h), Image.Resampling.LANCZOS)

    cover_scale = max(target_w / src_w, target_h / src_h)
    bg_w = max(1, int(src_w * cover_scale))
    bg_h = max(1, int(src_h * cover_scale))
    background = img.resize((bg_w, bg_h), Image.Resampling.LANCZOS)
    left = max(0, (bg_w - target_w) // 2)
    top = max(0, (bg_h - target_h) // 2)
    background = background.crop((left, top, left + target_w, top + target_h))
    background = background.filter(ImageFilter.GaussianBlur(radius=24))

    canvas = Image.new("RGBA", (target_w, target_h))
    canvas.paste(background, (0, 0))
    canvas.paste(fitted, ((target_w - fit_w) // 2, (target_h - fit_h) // 2), fitted)
    return canvas


def smart_cover_image(image: Image.Image, size: tuple[int, int], fit_mode: str = "smart") -> Image.Image:
    target_w, target_h = size
    if target_w <= 0 or target_h <= 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    if fit_mode == "contain":
        return contain_with_blur(image, size)

    img = image.convert("RGBA")
    src_w, src_h = img.size
    src_aspect = src_w / src_h

    faces = detect_faces(img) if fit_mode == "smart" else []
    subject = subject_region(img, faces)

    if fit_mode == "smart" and should_use_contain(src_w, src_h, target_w, target_h, subject):
        return contain_with_blur(image, size)

    scale = max(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    subject_scaled = subject.scaled(scale)

    if fit_mode == "cover":
        left = (new_w - target_w) // 2
        top = (new_h - target_h) // 2
    else:
        left, top = choose_crop_origin(
            subject_scaled,
            new_w,
            new_h,
            target_w,
            target_h,
            src_aspect,
        )

    return resized.crop((left, top, left + target_w, top + target_h))