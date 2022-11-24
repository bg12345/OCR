import math
from typing import Tuple, Union
import numpy as np
import cv2
from deskew import determine_skew
from pyzbar.pyzbar import decode,ZBarSymbol


def rotate(image: np.ndarray, angle: float, background: Union[int, Tuple[int, int, int]]):
    old_width, old_height = image.shape[:2]
    angle_radian = math.radians(angle)
    width = abs(np.sin(angle_radian) * old_height) + abs(np.cos(angle_radian) * old_width)
    height = abs(np.sin(angle_radian) * old_width) + abs(np.cos(angle_radian) * old_height)
    image_center = tuple(np.array(image.shape[1::-1]) / 2)
    rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
    rot_mat[1, 2] += (width - old_width) / 2
    rot_mat[0, 2] += (height - old_height) / 2
    return cv2.warpAffine(image, rot_mat, (int(round(height)), int(round(width))), borderValue=background)


def get_preprocessed_file(path,file):
    if file!=None:
      file = np.fromstring(file.read(), np.uint8)
      file = cv2.imdecode(file, cv2.IMREAD_ANYCOLOR)
    else:
        file=cv2.imread(path)
    angle = determine_skew(cv2.cvtColor(file, cv2.COLOR_BGR2GRAY))
    #print(angle)
    if angle != 0.0:
        file = rotate(file, angle, (0, 0, 0))
    file = cv2.resize(file, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    file = cv2.fastNlMeansDenoisingColored(file, None, 10, 10, 7, 15)
    """cv2.imshow("test",file)
    cv2.waitKey(0)
    cv2.destroyAllWindows()"""
    return file


def detection(path):
    im = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    ret, bw_im = cv2.threshold(im, 127, 255, cv2.THRESH_BINARY)
    d = decode(bw_im,symbols=[ZBarSymbol.QRCODE])
    if d:
        return d[0]
    return False
