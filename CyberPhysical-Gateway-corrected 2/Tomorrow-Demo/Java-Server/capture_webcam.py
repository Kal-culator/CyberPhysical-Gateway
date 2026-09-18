#!/usr/bin/env python3
"""Capture one fresh JPEG on the laptop. Called with an eight-second Java deadline."""
import argparse
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--index', type=int, default=0)
    args = parser.parse_args()
    import cv2

    backend = cv2.CAP_AVFOUNDATION if sys.platform == 'darwin' else cv2.CAP_ANY
    camera = cv2.VideoCapture(args.index, backend)
    try:
        if not camera.isOpened():
            raise RuntimeError('Cannot open laptop webcam. Allow camera access and close other camera apps.')
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        frame = None
        # Discard initial frames while exposure settles.
        for _ in range(8):
            ok, current = camera.read()
            if ok:
                frame = current
            time.sleep(0.08)
        if frame is None:
            raise RuntimeError('Webcam opened but returned no image.')
        if not cv2.imwrite(str(Path(args.output)), frame, [cv2.IMWRITE_JPEG_QUALITY, 85]):
            raise RuntimeError('Could not save webcam JPEG.')
        print('Laptop webcam photo captured.')
    finally:
        camera.release()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'Webcam capture failed: {error}', file=sys.stderr)
        sys.exit(1)
