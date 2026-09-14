#   ##########################################################
#   By Eugene Ch'ng
#   LinkedIn: https://www.linkedin.com/in/eugenecc/
#   GitHub: https://github.com/drecuk/
#   ----------------------------------------------------------
#   Python OpenCV Sky Image Evaluation and Filtering
#
#   Evaluates images based on the percentage of blue sky
#   detected within the HSV colour space
#
#   Confirmed sky images can then be moved into a specified
#   destination folder
#
#   How to use:
#   evaluate_sky_image(image_path, threshold_pct=85.0)
#   move_confirmed_skies(image_paths_list, dest_folder)
#   ##########################################################

import cv2
import numpy as np
import shutil
import os


#   ##########################################################
#   EVALUATE SKY IMAGE
#   ----------------------------------------------------------
#   Analyses the blue sky content within an image
#   Returns the evaluation result and sky percentage
#
#   Note that this function does not move the image file
#   ##########################################################

def evaluate_sky_image(image_path, threshold_pct=85.0):

    # --------------------------- LOAD IMAGE
    # read the image from file using OpenCV
    img = cv2.imread(image_path)

    # if the image cannot be read, return an empty result
    if img is None:
        return False, 0.0

    # --------------------------- CONVERT COLOUR SPACE
    # convert image from BGR colour space to HSV colour space
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # --------------------------- CREATE SKY FILTER
    # set lower and upper blue colour ranges for sky detection
    lower_blue = np.array([85, 40, 90])
    upper_blue = np.array([135, 255, 255])

    # create a mask containing pixels within the blue sky range
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    # --------------------------- CALCULATE SKY AREA
    # count sky pixels detected within the mask
    sky_pixels = cv2.countNonZero(mask)

    # calculate the total number of pixels in the image
    total_pixels = img.shape[0] * img.shape[1]

    # calculate the percentage of image covered by sky
    sky_percentage = (sky_pixels / total_pixels) * 100

    # --------------------------- EVALUATE RESULT
    # image is considered a sky image when percentage meets the threshold
    is_sky = sky_percentage >= threshold_pct

    return is_sky, sky_percentage


#   ##########################################################
#   MOVE CONFIRMED SKY IMAGES
#   ----------------------------------------------------------
#   Moves a confirmed list of image files into a destination
#   folder and returns the number of files successfully moved
#   ##########################################################

def move_confirmed_skies(image_paths_list, dest_folder):

    # --------------------------- CREATE DESTINATION FOLDER
    # create destination folder if it does not already exist
    os.makedirs(dest_folder, exist_ok=True)

    # initialise successful move counter
    moved_count = 0

    # --------------------------- PROCESS CONFIRMED IMAGES
    # loop through the list of confirmed sky image paths
    for img_path in image_paths_list:

        # make sure the image file still exists
        if os.path.exists(img_path):

            # construct the destination path using the original filename
            dest_path = os.path.join(
                dest_folder,
                os.path.basename(img_path)
            )

            # --------------------------- MOVE IMAGE
            try:
                shutil.move(img_path, dest_path)
                moved_count += 1

            except Exception as e:
                print(f"Error moving {img_path}: {e}")

    # --------------------------- RETURN RESULTS
    return moved_count
